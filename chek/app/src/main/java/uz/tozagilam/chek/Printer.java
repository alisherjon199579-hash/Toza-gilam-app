package uz.tozagilam.chek;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Color;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.EncodeHintType;
import com.google.zxing.common.BitMatrix;
import com.google.zxing.qrcode.QRCodeWriter;
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;

import org.json.JSONArray;
import org.json.JSONObject;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Terminalning ichki printeri (Basewin SDK, com.basewin.printdemo kutubxonasi orqali). */
public class Printer {
    private static Object printer;
    private static ClassLoader cl;

    private static synchronized void init(Context ctx) throws Exception {
        if (printer != null) return;
        Context pc = ctx.createPackageContext("com.basewin.printdemo",
                Context.CONTEXT_INCLUDE_CODE | Context.CONTEXT_IGNORE_SECURITY);
        cl = pc.getClassLoader();
        Class<?> smC = cl.loadClass("com.basewin.services.ServiceManager");
        Object sm = smC.getMethod("getInstence").invoke(null);
        smC.getMethod("init", Context.class).invoke(sm, ctx.getApplicationContext());
        Object p = null;
        for (int i = 0; i < 10 && p == null; i++) {
            Thread.sleep(500);
            p = smC.getMethod("getPrinter").invoke(sm);
        }
        if (p == null) throw new Exception("printer xizmati topilmadi");
        printer = p;
    }

    /** Qora-oq QR rasm (termal printer uchun) */
    static Bitmap qr(String text, int px) throws Exception {
        EnumMap<EncodeHintType, Object> h = new EnumMap<EncodeHintType, Object>(EncodeHintType.class);
        h.put(EncodeHintType.MARGIN, 1);
        h.put(EncodeHintType.ERROR_CORRECTION, ErrorCorrectionLevel.L);
        BitMatrix m = new QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, px, px, h);
        int w = m.getWidth(), ht = m.getHeight();
        int[] pix = new int[w * ht];
        for (int y = 0; y < ht; y++)
            for (int x = 0; x < w; x++)
                pix[y * w + x] = m.get(x, y) ? Color.BLACK : Color.WHITE;
        Bitmap b = Bitmap.createBitmap(w, ht, Bitmap.Config.ARGB_8888);
        b.setPixels(pix, 0, w, 0, 0, w, ht);
        return b;
    }

    static Bitmap variant(String text, int mode) throws Exception {
        Bitmap b = qr(text, 240);
        int w = b.getWidth(), h = b.getHeight();
        if (mode == 1) { // RGB_565
            Bitmap c = Bitmap.createBitmap(w, h, Bitmap.Config.RGB_565);
            new android.graphics.Canvas(c).drawBitmap(b, 0, 0, null);
            return c;
        }
        if (mode == 2) { // teskari ranglar
            int[] p = new int[w * h]; b.getPixels(p, 0, w, 0, 0, w, h);
            for (int i = 0; i < p.length; i++) p[i] = (p[i] == Color.BLACK) ? Color.WHITE : Color.BLACK;
            Bitmap c = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888); c.setPixels(p, 0, w, 0, 0, w, h); return c;
        }
        if (mode == 3) { // PNG orqali qayta o'qilgan
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            b.compress(Bitmap.CompressFormat.PNG, 100, bo);
            byte[] d = bo.toByteArray();
            return android.graphics.BitmapFactory.decodeByteArray(d, 0, d.length);
        }
        if (mode == 4) { // butun qog'oz kengligi 384 px, oq fon
            Bitmap c = Bitmap.createBitmap(384, h + 8, Bitmap.Config.ARGB_8888);
            android.graphics.Canvas cv = new android.graphics.Canvas(c);
            cv.drawColor(Color.WHITE); cv.drawBitmap(b, (384 - w) / 2, 4, null);
            return c;
        }
        return b;
    }

    /** lines: [{"t":"matn","s":2,"p":"center","b":1}, ...]. Muvaffaqiyatli bo'lsa null, aks holda xato matni. */
    public static synchronized String print(Context ctx, JSONArray lines) {
        try {
            JSONArray cur = new JSONArray();
            java.util.List<JSONArray> parts = new ArrayList<JSONArray>();
            for (int i = 0; i < lines.length(); i++) {
                JSONObject l = lines.getJSONObject(i);
                if (l.has("q") || l.has("d")) continue; // bu printer rasm chiqarmaydi
                cur.put(l);
            }
            if (cur.length() > 0) parts.add(cur);
            for (int i = 0; i < parts.size(); i++) {
                JSONObject f0 = parts.get(i).getJSONObject(0);
                boolean img = f0.has("q") || f0.has("d");
                String e = printPart(ctx, parts.get(i), i == parts.size() - 1 ? 3 : 0, img ? 2000 : 1000, img ? 2 : 1);
                if (e != null) return e;
                try { Thread.sleep(300); } catch (Exception x) { }
            }
            return null;
        } catch (Throwable t) { return String.valueOf(t); }
    }

    static String printPart(Context ctx, JSONArray lines, int feed, int gray, int space) {
        try {
            init(ctx);
            JSONArray arr = new JSONArray();
            List<Bitmap> bmps = new ArrayList<Bitmap>();
            for (int i = 0; i < lines.length(); i++) {
                JSONObject l = lines.getJSONObject(i);
                JSONObject o = new JSONObject();
                if (l.has("d")) {
                    o.put("content-type", "two-dimension");
                    o.put("content", l.getString("d"));
                    o.put("size", String.valueOf(l.optInt("s", 6)));
                    o.put("position", l.optString("p", "center"));
                    arr.put(o);
                    continue;
                }
                if (l.has("q")) {
                    o.put("content-type", "jpg");
                    o.put("position", l.optString("p", "center"));
                    arr.put(o);
                    bmps.add(variant(l.getString("q"), l.optInt("m", 0)));
                    continue;
                }
                o.put("content-type", "txt");
                o.put("content", l.optString("t", ""));
                o.put("size", String.valueOf(l.optInt("s", 2)));
                o.put("position", l.optString("p", "left"));
                o.put("offset", "0");
                o.put("bold", String.valueOf(l.optInt("b", 0)));
                o.put("italic", "0");
                o.put("height", "-1");
                arr.put(o);
            }
            JSONObject root = new JSONObject();
            root.put("spos", arr);
            Class<?> pcl = printer.getClass();
            try { pcl.getMethod("setPrintGray", int.class).invoke(printer, gray); } catch (Throwable t) { }
            try { pcl.getMethod("setLineSpace", int.class).invoke(printer, space); } catch (Throwable t) { }
            try { pcl.getMethod("printBottomFeedLine", int.class).invoke(printer, feed); } catch (Throwable t) { }
            Method pm = null;
            for (Method m : pcl.getMethods())
                if (m.getName().equals("print") && m.getParameterTypes().length == 3) { pm = m; break; }
            if (pm == null) return "print metodi topilmadi";
            final CountDownLatch done = new CountDownLatch(1);
            final String[] err = new String[1];
            Object lis = Proxy.newProxyInstance(cl, new Class<?>[]{pm.getParameterTypes()[2]}, new InvocationHandler() {
                public Object invoke(Object proxy, Method method, Object[] args) {
                    String n = method.getName();
                    if (n.equals("onFinish")) done.countDown();
                    else if (n.equals("onError")) {
                        err[0] = "printer xatosi " + (args != null && args.length > 0 ? args[0] : "") + " " + (args != null && args.length > 1 ? args[1] : "");
                        done.countDown();
                    }
                    return null;
                }
            });
            pm.invoke(printer, root.toString(), bmps.isEmpty() ? null : bmps.toArray(new Bitmap[0]), lis);
            if (!done.await(40, TimeUnit.SECONDS)) return "printer javob bermadi";
            return err[0];
        } catch (Throwable t) {
            printer = null;
            Throwable c = t;
            while (c.getCause() != null) c = c.getCause();
            return String.valueOf(c);
        }
    }
}
