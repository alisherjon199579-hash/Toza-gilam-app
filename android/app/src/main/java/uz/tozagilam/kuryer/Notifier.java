package uz.tozagilam.kuryer;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Build;
import android.webkit.JavascriptInterface;

/** CRM xabarlarini telefon bildirishnomasi qilib chiqaradi (baland ovoz bilan). */
final class Notifier {
    private static final String CHANNEL = "xabar_v2";
    private static final long[] VIBRATE = {0, 500, 250, 500, 250, 500};

    /**
     * WebView'da brauzer bildirishnomalari (Notification) yo'q. CRM sahifasi ularni chaqirganda
     * telefonning o'z bildirishnomasi chiqishi uchun sahifaga shu ko'prik qo'yiladi.
     */
    static final String JS = "(function(){if(window.__tgNotif)return;window.__tgNotif=1;"
            + "function N(t,o){try{TozaGilamApp.notify(String(t||''),String((o&&o.body)||''),String((o&&o.tag)||''))}catch(e){}}"
            + "N.permission='granted';"
            + "N.requestPermission=function(cb){if(typeof cb==='function')cb('granted');return Promise.resolve('granted')};"
            + "try{window.Notification=N}catch(e){}})()";

    static final class Bridge {
        private final Context app;

        Bridge(Context c) {
            app = c.getApplicationContext();
        }

        @JavascriptInterface
        public void notify(String title, String body, String tag) {
            show(app, title, body, tag);
        }
    }

    static void show(Context ctx, String title, String body, String tag) {
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) {
            return;
        }
        Uri sound = Uri.parse("android.resource://" + ctx.getPackageName() + "/" + R.raw.xabar);
        // Budilnik ovoz kanali: bildirishnoma ovozi past bo'lsa ham baland eshitiladi
        AudioAttributes attrs = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build();
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            nm.deleteNotificationChannel("news");
            NotificationChannel ch = new NotificationChannel(CHANNEL, "CRM xabarlari", NotificationManager.IMPORTANCE_HIGH);
            ch.setSound(sound, attrs);
            ch.enableVibration(true);
            ch.setVibrationPattern(VIBRATE);
            ch.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
            nm.createNotificationChannel(ch);
            b = new Notification.Builder(ctx, CHANNEL);
        } else {
            b = new Notification.Builder(ctx).setPriority(Notification.PRIORITY_MAX)
                    .setSound(sound, attrs).setVibrate(VIBRATE);
        }
        PendingIntent open = PendingIntent.getActivity(ctx, 2, new Intent(ctx, MainActivity.class),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        b.setSmallIcon(R.drawable.ic_stat)
                .setColor(ctx.getColor(R.color.brand))
                .setContentTitle(title == null || title.isEmpty() ? "Toza Gilam" : title)
                .setContentText(body)
                .setStyle(new Notification.BigTextStyle().bigText(body))
                .setContentIntent(open)
                .setAutoCancel(true);
        int id = 100 + (tag == null || tag.isEmpty() ? (int) (System.currentTimeMillis() % 100000) : (tag.hashCode() & 0xffff));
        try {
            nm.notify(id, b.build());
        } catch (Exception ignored) {
        }
    }

    private Notifier() {
    }
}
