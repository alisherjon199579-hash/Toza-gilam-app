package uz.tozagilam.kuryer;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Yangi versiyani tekshiradi. GitHub'dagi "apk" relizining nomida versiya raqami bor
 * ("Toza Gilam ilovasi (1.0.N)"); N ilovaning versionCode'idan katta bo'lsa, yangilanish bor.
 */
final class Updater {
    static final String EXTRA_UPDATE = "update";
    static final String APK_URL = "https://github.com/alisherjon199579-hash/Toza-gilam-app/releases/download/apk/toza-gilam.apk";
    private static final String API_URL = "https://api.github.com/repos/alisherjon199579-hash/Toza-gilam-app/releases/tags/apk";
    private static final Pattern VER = Pattern.compile("\"name\"\\s*:\\s*\"[^\"]*\\(1\\.0\\.(\\d+)\\)");
    private static final long EVERY_MS = 2 * 3600_000L;

    /** Oxirgi tekshiruvda topilgan versiya raqami (0 - hali noma'lum). */
    static volatile int latest;

    static boolean available() {
        return latest > BuildConfig.VERSION_CODE;
    }

    /** Fon oqimida tekshiradi. force=false bo'lsa, 2 soatda bir martadan ko'p emas. */
    static void check(final Context ctx, boolean force, final Runnable onNewVersion) {
        final Context app = ctx.getApplicationContext();
        final SharedPreferences p = app.getSharedPreferences("app", Context.MODE_PRIVATE);
        long now = System.currentTimeMillis();
        if (!force && now - p.getLong("upd_checked", 0) < EVERY_MS) {
            return;
        }
        p.edit().putLong("upd_checked", now).apply();
        new Thread(new Runnable() {
            @Override
            public void run() {
                int v = fetch();
                if (v <= 0) {
                    p.edit().putLong("upd_checked", 0).apply(); // internet bo'lmagan: keyingi safar yana uriniladi
                    return;
                }
                latest = v;
                if (!available()) {
                    return;
                }
                if (onNewVersion != null) {
                    onNewVersion.run();
                } else {
                    notifyUpdate(app);
                }
            }
        }).start();
    }

    private static int fetch() {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(API_URL).openConnection();
            c.setConnectTimeout(15_000);
            c.setReadTimeout(15_000);
            c.setRequestProperty("Accept", "application/vnd.github+json");
            c.setRequestProperty("User-Agent", "TozaGilamApp");
            if (c.getResponseCode() != 200) {
                return 0;
            }
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            try (InputStream in = c.getInputStream()) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0 && out.size() < 400_000) {
                    out.write(buf, 0, n);
                }
            }
            Matcher m = VER.matcher(out.toString("UTF-8"));
            return m.find() ? Integer.parseInt(m.group(1)) : 0;
        } catch (Exception e) {
            return 0;
        } finally {
            if (c != null) {
                c.disconnect();
            }
        }
    }

    static void notifyUpdate(Context app) {
        NotificationManager nm = (NotificationManager) app.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) {
            return;
        }
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel("update", "Ilova yangilanishi", NotificationManager.IMPORTANCE_HIGH));
        }
        PendingIntent open = PendingIntent.getActivity(app, 3,
                new Intent(app, MainActivity.class).putExtra(EXTRA_UPDATE, true).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(app, "update")
                : new Notification.Builder(app).setPriority(Notification.PRIORITY_HIGH).setDefaults(Notification.DEFAULT_ALL);
        b.setSmallIcon(R.drawable.ic_stat)
                .setColor(app.getColor(R.color.brand))
                .setContentTitle("Toza Gilam: yangi versiya tayyor")
                .setContentText("Yangilash uchun shu yerni bosing")
                .setContentIntent(open)
                .setAutoCancel(true);
        try {
            nm.notify(50, b.build());
        } catch (Exception ignored) {
        }
    }

    private Updater() {
    }
}
