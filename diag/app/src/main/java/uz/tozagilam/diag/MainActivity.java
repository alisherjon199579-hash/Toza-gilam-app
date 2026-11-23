package uz.tozagilam.diag;

import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.graphics.Typeface;
import android.view.View;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

public class MainActivity extends Activity {

    private final Map<String, String> sections = new LinkedHashMap<String, String>();
    private TextView tv;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private static final Pattern HOT = Pattern.compile(
            "(?i)print|prn|fiscal|kkm|kassa|kass|pay|pos|peak|smart|uz|bank|card|humo|device|sdk|hardware|module|thermal|escpos");
    private static final Pattern BORING = Pattern.compile(
            "^(com\\.android\\.|android$|android\\.|com\\.google\\.|com\\.qualcomm|org\\.codeaurora|com\\.qti|com\\.quicinc|com\\.svox|com\\.mediatek|org\\.chromium|com\\.sprd).*");

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        HorizontalScrollView hs = new HorizontalScrollView(this);
        LinearLayout bar = new LinearLayout(this);
        hs.addView(bar);
        root.addView(hs);
        String[] names = {"1 Ilovalar", "2 Qurilma", "3 Xizmatlar", "4 USB/BT", "5 Ulanish sinovi", "6 Chek sinovi", "Nusxa", "Faylga"};
        for (final String n : names) {
            Button bt = new Button(this);
            bt.setText(n);
            bt.setTextSize(12);
            bt.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) { click(n); }
            });
            bar.addView(bt);
        }
        ScrollView sv = new ScrollView(this);
        tv = new TextView(this);
        tv.setTypeface(Typeface.MONOSPACE);
        tv.setTextSize(11);
        tv.setPadding(8, 8, 8, 8);
        tv.setTextIsSelectable(true);
        sv.addView(tv);
        root.addView(sv, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(root);
        tv.setText("Tayyorlanmoqda…");
        new Thread(new Runnable() {
            public void run() {
                try { build(); } catch (Throwable t) { sections.put("Xato", "build: " + t); }
                ui.post(new Runnable() { public void run() { click("2 Qurilma"); } });
            }
        }).start();
    }

    private void click(String n) {
        if (n.startsWith("1")) show("Ilovalar");
        else if (n.startsWith("2")) show("Qurilma");
        else if (n.startsWith("3")) show("Xizmatlar");
        else if (n.startsWith("4")) show("USB/BT");
        else if (n.startsWith("5")) bindTest();
        else if (n.startsWith("6")) serialTest();
        else if (n.equals("Nusxa")) copyAll();
        else if (n.equals("Faylga")) saveAll();
    }

    private void show(String k) {
        String s = sections.get(k);
        tv.setText(s == null ? "(bo'sh)" : s);
    }

    private String all() {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, String> e : sections.entrySet())
            sb.append("===== ").append(e.getKey()).append(" =====\n").append(e.getValue()).append("\n\n");
        return sb.toString();
    }

    private void copyAll() {
        try {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("diag", all()));
            tv.setText("Hammasi nusxalandi (" + all().length() + " belgi).");
        } catch (Throwable t) { tv.setText("Nusxa olinmadi: " + t); }
    }

    private void saveAll() {
        try {
            File f = new File(Environment.getExternalStorageDirectory(), "diag-printer.txt");
            FileOutputStream o = new FileOutputStream(f);
            o.write(all().getBytes("UTF-8"));
            o.close();
            tv.setText("Saqlandi: " + f.getAbsolutePath());
        } catch (Throwable t) { tv.setText("Saqlanmadi: " + t); }
    }

    private void put(String k, StringBuilder sb) { sections.put(k, sb.toString()); }

    private void build() {
        PackageManager pm = getPackageManager();
        // ---- Qurilma
        StringBuilder q = new StringBuilder();
        q.append("Model: ").append(Build.MANUFACTURER).append(" / ").append(Build.MODEL).append(" / ").append(Build.DEVICE).append("\n");
        q.append("Android: ").append(Build.VERSION.RELEASE).append(" (API ").append(Build.VERSION.SDK_INT).append(")\n");
        q.append("Fingerprint: ").append(Build.FINGERPRINT).append("\n");
        q.append("Hardware: ").append(Build.HARDWARE).append("  ABI: ").append(Build.CPU_ABI).append("\n\n");
        q.append("-- getprop (printerga oid) --\n");
        for (String l : run(new String[]{"getprop"}))
            if (Pattern.compile("(?i)print|prn|pos|fiscal|kkm|peak|smart|sdk|vendor|ro\\.product\\.(name|brand)|ro\\.build\\.display").matcher(l).find()) q.append(l).append("\n");
        q.append("\n-- /dev (tty*, usb, print) --\n");
        File dev = new File("/dev");
        String[] dl = dev.list();
        if (dl != null) {
            Arrays.sort(dl);
            for (String d : dl) {
                if (d.startsWith("tty") && !d.matches("tty\\d*") || d.matches("(?i).*(print|prn|lp\\d|usb|spi|i2c|nfc|ttyS\\d|mt?d?|smd\\d).*")) {
                    File f = new File(dev, d);
                    if (d.startsWith("tty") && d.matches("tty\\d+")) continue;
                    q.append(d).append(" ").append(f.canRead() ? "r" : "-").append(f.canWrite() ? "w" : "-").append("\n");
                }
            }
        }
        q.append("\n-- /system/app, priv-app (nomlar) --\n");
        for (String dir : new String[]{"/system/app", "/system/priv-app", "/system/vendor/app", "/vendor/app", "/data/app"}) {
            String[] a = new File(dir).list();
            if (a == null) { q.append(dir).append(": ko'rinmaydi\n"); continue; }
            Arrays.sort(a);
            StringBuilder s = new StringBuilder();
            for (String x : a) if (!BORING.matcher(x.toLowerCase()).matches() && !x.toLowerCase().startsWith("com.android") ) s.append(x).append(", ");
            q.append(dir).append(" (").append(a.length).append("): ").append(s).append("\n");
        }
        q.append("\n-- Kutubxona fayllari (print/pos/sdk) --\n");
        for (String dir : new String[]{"/system/lib", "/system/framework", "/system/vendor/lib", "/vendor/lib", "/system/etc/permissions"}) {
            String[] a = new File(dir).list();
            if (a == null) continue;
            Arrays.sort(a);
            StringBuilder s = new StringBuilder();
            for (String x : a) if (Pattern.compile("(?i)print|prn|pos|escpos|thermal|peak|smartpeak|fiscal|serial|pboc|psam|emv|nfc_").matcher(x).find()) s.append(x).append(", ");
            if (s.length() > 0) q.append(dir).append(": ").append(s).append("\n");
        }
        put("Qurilma", q);
        // ---- Ilovalar
        StringBuilder ap = new StringBuilder();
        List<PackageInfo> pis = pm.getInstalledPackages(0);
        Collections.sort(pis, new java.util.Comparator<PackageInfo>() {
            public int compare(PackageInfo a, PackageInfo b2) { return a.packageName.compareTo(b2.packageName); }
        });
        int total = 0;
        for (PackageInfo pi : pis) {
            total++;
            if (BORING.matcher(pi.packageName).matches()) continue;
            ApplicationInfo ai = pi.applicationInfo;
            String label = "";
            try { label = String.valueOf(pm.getApplicationLabel(ai)); } catch (Throwable t) { }
            boolean sys = (ai.flags & ApplicationInfo.FLAG_SYSTEM) != 0;
            ap.append(sys ? "[S] " : "[U] ").append(pi.packageName).append("  ").append(label).append("  v").append(pi.versionName).append("\n   ").append(ai.sourceDir).append("\n");
        }
        ap.insert(0, "Jami paketlar: " + total + " ([S]=tizim, [U]=o'rnatilgan). Oddiy Android paketlari ko'rsatilmagan.\n\n");
        put("Ilovalar", ap);
        // ---- Xizmatlar
        StringBuilder sv = new StringBuilder();
        for (PackageInfo pi : pis) {
            if (BORING.matcher(pi.packageName).matches()) continue;
            try {
                PackageInfo full = pm.getPackageInfo(pi.packageName, PackageManager.GET_SERVICES | PackageManager.GET_ACTIVITIES | PackageManager.GET_RECEIVERS);
                boolean hot = HOT.matcher(pi.packageName).find();
                StringBuilder one = new StringBuilder();
                if (full.services != null) for (ServiceInfo s : full.services) {
                    if (hot || HOT.matcher(s.name).find())
                        one.append("  SVC ").append(s.name).append(s.exported ? " [exported]" : "").append(s.permission != null ? " perm=" + s.permission : "").append("\n");
                }
                if (hot && full.activities != null) {
                    int c = 0;
                    for (android.content.pm.ActivityInfo a : full.activities) { if (c++ < 8) one.append("  ACT ").append(a.name).append("\n"); }
                }
                if (one.length() > 0) sv.append(pi.packageName).append("\n").append(one);
            } catch (Throwable t) { }
        }
        put("Xizmatlar", sv);
        // ---- USB / Bluetooth
        StringBuilder ub = new StringBuilder();
        try {
            UsbManager um = (UsbManager) getSystemService(Context.USB_SERVICE);
            HashMap<String, UsbDevice> m = um.getDeviceList();
            ub.append("USB qurilmalar: ").append(m.size()).append("\n");
            for (UsbDevice d : m.values()) ub.append(" ").append(d.getDeviceName()).append(" vid=").append(Integer.toHexString(d.getVendorId())).append(" pid=").append(Integer.toHexString(d.getProductId())).append(" class=").append(d.getDeviceClass()).append("\n");
        } catch (Throwable t) { ub.append("USB: ").append(t).append("\n"); }
        try {
            BluetoothAdapter ad = BluetoothAdapter.getDefaultAdapter();
            if (ad == null) ub.append("Bluetooth yo'q\n");
            else {
                ub.append("Bluetooth: ").append(ad.isEnabled() ? "yoqilgan" : "o'chiq").append("\n");
                if (ad.isEnabled()) for (BluetoothDevice d : ad.getBondedDevices()) ub.append(" ").append(d.getName()).append(" ").append(d.getAddress()).append("\n");
            }
        } catch (Throwable t) { ub.append("BT: ").append(t).append("\n"); }
        put("USB/BT", ub);
    }

    private List<String> run(String[] cmd) {
        List<String> out = new ArrayList<String>();
        try {
            Process p = Runtime.getRuntime().exec(cmd);
            BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()));
            String l;
            while ((l = r.readLine()) != null) out.add(l);
        } catch (Throwable t) { out.add("xato: " + t); }
        return out;
    }

    // ---- Xizmatlarga ulanib, AIDL interfeys nomini aniqlash
    private final List<ComponentName> queue = new ArrayList<ComponentName>();
    private StringBuilder bindOut;
    private ServiceConnection cur;
    private boolean bound;

    private void bindTest() {
        bindOut = new StringBuilder();
        queue.clear();
        PackageManager pm = getPackageManager();
        for (PackageInfo pi : pm.getInstalledPackages(0)) {
            if (BORING.matcher(pi.packageName).matches() || pi.packageName.equals(getPackageName())) continue;
            try {
                PackageInfo full = pm.getPackageInfo(pi.packageName, PackageManager.GET_SERVICES);
                if (full.services == null) continue;
                boolean hot = HOT.matcher(pi.packageName).find();
                for (ServiceInfo s : full.services)
                    if (s.exported && (hot || HOT.matcher(s.name).find())) queue.add(new ComponentName(s.packageName, s.name));
            } catch (Throwable t) { }
        }
        bindOut.append("Sinaladigan xizmatlar: ").append(queue.size()).append("\n\n");
        tv.setText(bindOut);
        nextBind();
    }

    private void nextBind() {
        if (queue.isEmpty()) {
            bindOut.append("\nTugadi.");
            sections.put("Ulanish sinovi", bindOut.toString());
            tv.setText(bindOut);
            return;
        }
        final ComponentName cn = queue.remove(0);
        bound = false;
        cur = new ServiceConnection() {
            public void onServiceConnected(ComponentName n, IBinder s) {
                if (bound) return;
                bound = true;
                String d;
                try { d = s.getInterfaceDescriptor(); } catch (Throwable t) { d = "? " + t; }
                bindOut.append("OK  ").append(n.flattenToShortString()).append("\n    AIDL: ").append(d).append("\n");
                tv.setText(bindOut);
                try { unbindService(this); } catch (Throwable t) { }
                ui.post(new Runnable() { public void run() { nextBind(); } });
            }
            public void onServiceDisconnected(ComponentName n) { }
        };
        boolean ok = false;
        try { ok = bindService(new Intent().setComponent(cn), cur, Context.BIND_AUTO_CREATE); } catch (Throwable t) { bindOut.append("--  ").append(cn.flattenToShortString()).append(" xato: ").append(t).append("\n"); }
        if (!ok) { try { unbindService(cur); } catch (Throwable t) { } bound = true; ui.post(new Runnable() { public void run() { nextBind(); } }); return; }
        final ServiceConnection mine = cur;
        ui.postDelayed(new Runnable() {
            public void run() {
                if (mine == cur && !bound) {
                    bound = true;
                    bindOut.append("--  ").append(cn.flattenToShortString()).append(" javob bermadi\n");
                    try { unbindService(mine); } catch (Throwable t) { }
                    nextBind();
                }
            }
        }, 2500);
    }

    // ---- Yozish mumkin bo'lgan seriya portlariga ESC/POS yuborib ko'rish
    private void serialTest() {
        StringBuilder o = new StringBuilder();
        String[] cands = {"/dev/ttyHSL0", "/dev/ttyHSL1", "/dev/ttyHSL2", "/dev/ttyHS0", "/dev/ttyHS1", "/dev/ttyHS2", "/dev/ttyHS3",
                "/dev/ttyMSM0", "/dev/ttyMSM1", "/dev/ttyMSM2", "/dev/ttyS0", "/dev/ttyS1", "/dev/ttyS2", "/dev/ttyS3",
                "/dev/ttyUSB0", "/dev/printer", "/dev/usb/lp0", "/dev/ttyGS0", "/dev/ttyACM0", "/dev/ttyHSL3"};
        byte[] data;
        try { data = ("\u001b@Toza Gilam printer sinovi\n1234567890\n\n\n\n").getBytes("US-ASCII"); } catch (Throwable t) { data = new byte[0]; }
        int n = 0;
        for (String p : cands) {
            File f = new File(p);
            if (!f.exists()) continue;
            n++;
            if (!f.canWrite()) { o.append(p).append(": bor, yozib bo'lmaydi (ruxsat yo'q)\n"); continue; }
            try {
                FileOutputStream fo = new FileOutputStream(f);
                fo.write(data);
                fo.flush();
                fo.close();
                o.append(p).append(": YOZILDI — printerdan qog'oz chiqdimi?\n");
            } catch (Throwable t) { o.append(p).append(": xato ").append(t).append("\n"); }
        }
        if (n == 0) o.append("Tanish seriya portlari topilmadi.\n");
        o.append("\nQog'oz chiqsa, qaysi qator yozilganini ayting.");
        sections.put("Chek sinovi", o.toString());
        tv.setText(o);
    }
}
