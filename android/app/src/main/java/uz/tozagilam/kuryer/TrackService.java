package uz.tozagilam.kuryer;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.webkit.CookieManager;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Fonda ishlaydi: dostavchik joylashuvini CRM serveriga yuborib turadi.
 * CRM'ga kirilgan hisob (cookie) bilan POST /api/app/loc ga {lat,lng,acc} yuboradi.
 * Javoblar: 200 - qabul qilindi, 401 - tizimga kirilmagan, 403 - bu hisob dostavchik emas.
 */
public class TrackService extends Service {
    static final String ACTION_STOP = "uz.tozagilam.kuryer.STOP";
    private static final String CHANNEL = "track";
    private static final int NOTIF_ID = 1;
    private static final long SEND_EVERY_MS = 15_000;   // harakatda: har 15 soniyada
    private static final long BEAT_EVERY_MS = 60_000;   // to'xtab turganda: har daqiqada

    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService net = Executors.newSingleThreadExecutor();
    private LocationManager lm;
    private Location last;
    private long lastSent;
    private String status = "";
    private boolean running;

    private final LocationListener listener = new LocationListener() {
        @Override
        public void onLocationChanged(Location loc) {
            if (loc == null) {
                return;
            }
            // Aniqroq yoki yangiroq nuqtani saqlaymiz
            if (last == null || loc.getTime() - last.getTime() > 30_000 || loc.getAccuracy() <= last.getAccuracy() * 1.5f) {
                last = loc;
            }
            if (System.currentTimeMillis() - lastSent >= SEND_EVERY_MS) {
                send();
            }
        }

        @Override
        public void onStatusChanged(String provider, int s, Bundle extras) {
        }

        @Override
        public void onProviderEnabled(String provider) {
        }

        @Override
        public void onProviderDisabled(String provider) {
        }
    };

    private final Runnable beat = new Runnable() {
        @Override
        public void run() {
            if (!running) {
                return;
            }
            if (System.currentTimeMillis() - lastSent >= BEAT_EVERY_MS - 1000) {
                send();
            }
            main.postDelayed(this, BEAT_EVERY_MS);
        }
    };

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            shutdown();
            return START_NOT_STICKY;
        }
        if (!hasLocation()) {
            stopSelf();
            return START_NOT_STICKY;
        }
        try {
            Notification n = buildNotification("Joylashuv yuborilmoqda");
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
            } else {
                startForeground(NOTIF_ID, n);
            }
        } catch (Exception e) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!running) {
            running = true;
            startUpdates();
            main.postDelayed(beat, 5_000);
        }
        return START_STICKY;
    }

    private boolean hasLocation() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    @SuppressLint("MissingPermission")
    private void startUpdates() {
        lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
        if (lm == null) {
            return;
        }
        for (String provider : new String[]{LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER}) {
            try {
                if (lm.getAllProviders().contains(provider)) {
                    lm.requestLocationUpdates(provider, 10_000, 10f, listener, Looper.getMainLooper());
                    Location l = lm.getLastKnownLocation(provider);
                    if (l != null && (last == null || l.getTime() > last.getTime())) {
                        last = l;
                    }
                }
            } catch (Exception ignored) {
            }
        }
    }

    private void send() {
        final Location loc = last;
        if (loc == null) {
            setStatus("Joylashuv aniqlanmoqda… GPS yoqilganini tekshiring");
            return;
        }
        if (System.currentTimeMillis() - loc.getTime() > 10 * 60_000) {
            setStatus("Joylashuv eskirgan. GPS yoqilganini tekshiring");
            return;
        }
        lastSent = System.currentTimeMillis();
        final String cookie = CookieManager.getInstance().getCookie(BuildConfig.BASE_URL);
        final String body = String.format(Locale.US, "{\"lat\":%.6f,\"lng\":%.6f,\"acc\":%.0f}",
                loc.getLatitude(), loc.getLongitude(), loc.getAccuracy());
        net.execute(new Runnable() {
            @Override
            public void run() {
                final int code = post(cookie, body);
                main.post(new Runnable() {
                    @Override
                    public void run() {
                        onResult(code);
                    }
                });
            }
        });
    }

    private int post(String cookie, String body) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(BuildConfig.BASE_URL + "/api/app/loc").openConnection();
            c.setConnectTimeout(15_000);
            c.setReadTimeout(15_000);
            c.setRequestMethod("POST");
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            if (cookie != null) {
                c.setRequestProperty("Cookie", cookie);
            }
            byte[] data = body.getBytes(StandardCharsets.UTF_8);
            c.setFixedLengthStreamingMode(data.length);
            try (OutputStream os = c.getOutputStream()) {
                os.write(data);
            }
            return c.getResponseCode();
        } catch (Exception e) {
            return -1;
        } finally {
            if (c != null) {
                c.disconnect();
            }
        }
    }

    private void onResult(int code) {
        if (!running) {
            return;
        }
        if (code == 200) {
            setStatus("Joylashuv yuborilmoqda");
        } else if (code == 401) {
            setStatus("Ilovani ochib, CRM'ga kiring");
        } else if (code == 403) {
            // Rahbar yoki boshqa xodim: joylashuv kerak emas
            shutdown();
        } else if (code == -1) {
            setStatus("Internet yo'q, qayta urinilmoqda");
        } else {
            setStatus("Server javob bermadi (" + code + ")");
        }
    }

    private void setStatus(String s) {
        if (s.equals(status)) {
            return;
        }
        status = s;
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) {
            try {
                nm.notify(NOTIF_ID, buildNotification(s));
            } catch (Exception ignored) {
            }
        }
    }

    private Notification buildNotification(String text) {
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26 && nm != null) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "Joylashuv", NotificationManager.IMPORTANCE_LOW);
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        }
        int flags = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), flags);
        PendingIntent stop = PendingIntent.getService(this, 1,
                new Intent(this, TrackService.class).setAction(ACTION_STOP), flags);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL)
                : new Notification.Builder(this);
        b.setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("Toza Gilam")
                .setContentText(text)
                .setContentIntent(open)
                .setColor(getColor(R.color.brand))
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .addAction(new Notification.Action.Builder(null, "To'xtatish", stop).build());
        return b.build();
    }

    private void shutdown() {
        running = false;
        main.removeCallbacks(beat);
        if (lm != null) {
            try {
                lm.removeUpdates(listener);
            } catch (Exception ignored) {
            }
        }
        if (Build.VERSION.SDK_INT >= 24) {
            stopForeground(STOP_FOREGROUND_REMOVE);
        } else {
            stopForeground(true);
        }
        stopSelf();
    }

    @Override
    public void onDestroy() {
        running = false;
        main.removeCallbacks(beat);
        if (lm != null) {
            try {
                lm.removeUpdates(listener);
            } catch (Exception ignored) {
            }
        }
        net.shutdown();
        super.onDestroy();
    }
}
