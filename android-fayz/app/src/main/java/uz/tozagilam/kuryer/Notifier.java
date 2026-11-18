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
     * Sahifaga qo'yiladigan ko'prik. Uch ish qiladi:
     * 1) WebView'da yo'q bo'lgan brauzer bildirishnomasini (Notification) telefon bildirishnomasiga ulaydi;
     * 2) sahifa ekranda ko'rinmay turganda ham o'zini "ko'rinib turibdi" deb hisoblaydi,
     *    aks holda CRM fonda yangi xabarlarni tekshirmay qo'yadi;
     * 3) sahifa ichidagi xabar tasmasi (#ntf) paydo bo'lganda ham telefon bildirishnomasi chiqaradi.
     */
    static final String JS = "(function(){if(window.__tgApp)return;window.__tgApp=1;"
            + "function N(t,o){try{TozaGilamApp.notify(String(t||''),String((o&&o.body)||''),String((o&&o.tag)||''))}catch(e){}}"
            + "N.permission='granted';"
            + "N.requestPermission=function(cb){if(typeof cb==='function')cb('granted');return Promise.resolve('granted')};"
            + "try{window.Notification=N}catch(e){}"
            + "var vis={hidden:false,visibilityState:'visible',webkitHidden:false,webkitVisibilityState:'visible'};"
            + "Object.keys(vis).forEach(function(k){var g={configurable:true,get:function(){return vis[k]}};"
            + "try{Object.defineProperty(Document.prototype,k,g)}catch(e){}try{Object.defineProperty(document,k,g)}catch(e){}});"
            + "try{document.hasFocus=function(){return true}}catch(e){}"
            + "function watch(){var el=document.getElementById('ntf');if(!el||el.__tgW)return;el.__tgW=1;"
            + "new MutationObserver(function(ms){ms.forEach(function(m){for(var i=0;i<m.addedNodes.length;i++){var n=m.addedNodes[i];"
            + "if(n.nodeType!==1)continue;var s=n.querySelector?n.querySelector('small'):null;var b=s?s.textContent:'';"
            + "var t=n.textContent||'';if(b)t=t.replace(b,'');"
            + "try{TozaGilamApp.banner(String(t).trim(),String(b).trim())}catch(e){}}})}).observe(el,{childList:true})}"
            + "watch();setInterval(watch,3000);})()";

    static final class Bridge {
        private final Context app;
        private final boolean headless;

        Bridge(Context c, boolean headless) {
            app = c.getApplicationContext();
            this.headless = headless;
        }

        /** Foydalanuvchi hozir ilovaga qarab turibdimi (chat "o'qildi" belgisi shunga qarab qo'yiladi). */
        @JavascriptInterface
        public boolean visible() {
            return !headless && MainActivity.resumed;
        }

        /** Sahifadagi xabar tasmasi: foydalanuvchi ilovaga qarab turgan bo'lsa, takrorlash shart emas. */
        @JavascriptInterface
        public void banner(String title, String body) {
            if (!headless && MainActivity.resumed) {
                return;
            }
            show(app, title, body, "");
        }

        @JavascriptInterface
        public void notify(String title, String body, String tag) {
            show(app, title, body, tag);
        }
    }

    private static String lastKey = "";
    private static long lastAt;

    static synchronized void show(Context ctx, String title, String body, String tag) {
        // Bitta xabar ikki yo'ldan kelishi mumkin: 15 soniya ichidagi takrorini o'tkazib yuboramiz
        String key = title + "|" + body;
        long nowMs = System.currentTimeMillis();
        if (key.equals(lastKey) && nowMs - lastAt < 15_000) {
            return;
        }
        lastKey = key;
        lastAt = nowMs;
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
                .setContentTitle(title == null || title.isEmpty() ? "Fayz Gilam" : title)
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
