package uz.tozagilam.chek;

import android.content.Context;
import android.content.SharedPreferences;

public class Cfg {
    static SharedPreferences sp(Context c) { return c.getSharedPreferences("cfg", Context.MODE_PRIVATE); }
    static String url(Context c) { return sp(c).getString("url", ""); }
    static String key(Context c) { return sp(c).getString("key", ""); }
    static void save(Context c, String u, String k) {
        u = u.trim();
        while (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        sp(c).edit().putString("url", u).putString("key", k.trim()).commit();
    }
    static void status(Context c, String s) { sp(c).edit().putString("status", s).putLong("statusAt", System.currentTimeMillis()).commit(); }
    static String status(Context c) { return sp(c).getString("status", "-"); }
}
