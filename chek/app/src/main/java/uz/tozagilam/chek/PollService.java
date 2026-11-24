package uz.tozagilam.chek;

import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.IBinder;
import android.os.PowerManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

/** CRM'dan yangi chek buyurtmalarini tekshirib turadi va printerda chiqaradi. */
public class PollService extends Service {
    private static volatile boolean running;
    private Thread th;
    private PowerManager.WakeLock wl;

    @Override public IBinder onBind(Intent i) { return null; }

    @Override
    public int onStartCommand(Intent i, int f, int id) {
        if (!running) {
            running = true;
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "tozachek");
            try { wl.acquire(); } catch (Throwable t) { }
            th = new Thread(new Runnable() { public void run() { loop(); } });
            th.start();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        try { if (wl != null && wl.isHeld()) wl.release(); } catch (Throwable t) { }
        super.onDestroy();
    }

    static String get(String u) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(u).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(15000);
        int code = c.getResponseCode();
        if (code == 204) return "";
        if (code != 200) throw new Exception("HTTP " + code);
        BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String l;
        while ((l = r.readLine()) != null) sb.append(l).append('\n');
        r.close();
        return sb.toString();
    }

    private void loop() {
        while (running) {
            long wait = 3000;
            try {
                String base = Cfg.url(this), key = URLEncoder.encode(Cfg.key(this), "UTF-8");
                if (base.length() == 0) { Cfg.status(this, "server manzili kiritilmagan"); wait = 5000; }
                else {
                    String body = get(base + "/next?k=" + key);
                    if (body.length() == 0) Cfg.status(this, "ulangan, chek kutilmoqda");
                    else {
                        JSONObject j = new JSONObject(body);
                        String id = j.getString("id");
                        Cfg.status(this, "chek chiqarilmoqda: " + id);
                        String err = Printer.print(this, j.getJSONArray("lines"));
                        if (err == null) {
                            get(base + "/ok?k=" + key + "&id=" + URLEncoder.encode(id, "UTF-8"));
                            Cfg.status(this, "chek chiqdi: " + id);
                        } else {
                            get(base + "/fail?k=" + key + "&id=" + URLEncoder.encode(id, "UTF-8") + "&e=" + URLEncoder.encode(err, "UTF-8"));
                            Cfg.status(this, "XATO: " + err);
                            wait = 10000;
                        }
                        wait = Math.min(wait, 500);
                        if (err != null) wait = 10000;
                    }
                }
            } catch (Throwable t) {
                Cfg.status(this, "ulanmadi: " + t);
                wait = 8000;
            }
            try { Thread.sleep(wait); } catch (InterruptedException e) { return; }
        }
    }
}
