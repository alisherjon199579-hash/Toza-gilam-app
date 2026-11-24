package uz.tozagilam.chek;

import android.content.Context;

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

    /** lines: [{"t":"matn","s":2,"p":"center","b":1}, ...]. Muvaffaqiyatli bo'lsa null, aks holda xato matni. */
    public static synchronized String print(Context ctx, JSONArray lines) {
        try {
            init(ctx);
            JSONArray arr = new JSONArray();
            for (int i = 0; i < lines.length(); i++) {
                JSONObject l = lines.getJSONObject(i);
                JSONObject o = new JSONObject();
                if (l.has("q")) {
                    o.put("content-type", "two-dimension");
                    o.put("content", l.getString("q"));
                    o.put("size", String.valueOf(l.optInt("s", 6)));
                    o.put("position", l.optString("p", "center"));
                    arr.put(o);
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
            try { pcl.getMethod("setPrintGray", int.class).invoke(printer, 1000); } catch (Throwable t) { }
            try { pcl.getMethod("setLineSpace", int.class).invoke(printer, 1); } catch (Throwable t) { }
            try { pcl.getMethod("printBottomFeedLine", int.class).invoke(printer, 3); } catch (Throwable t) { }
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
            pm.invoke(printer, root.toString(), null, lis);
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
