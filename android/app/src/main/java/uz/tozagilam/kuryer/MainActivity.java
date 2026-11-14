package uz.tozagilam.kuryer;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** CRM'ni ilova ichida ochadi va joylashuv xizmatini ishga tushiradi. */
public class MainActivity extends Activity {
    private static final int REQ_PERMS = 1;
    private static final int REQ_FILE = 2;

    /** Ilova oynasi tirikmi: tirik bo'lsa xabarlarni shu oyna kuzatadi, bo'lmasa xizmat. */
    static volatile boolean alive;

    private WebView web;
    private ValueCallback<Uri[]> fileCallback;
    private final Handler ui = new Handler(Looper.getMainLooper());

    /** Sahifaning eng tepasidagi rangni topadi: holat paneli shu rangga bo'yaladi. */
    private static final String TOP_COLOR_JS = "(function(){try{var e=document.elementFromPoint(innerWidth/2,1);"
            + "while(e){var c=getComputedStyle(e).backgroundColor;"
            + "if(c&&c!=='transparent'&&!/,\\s*0\\)$/.test(c))return c;e=e.parentElement}}catch(x){}return ''})()";
    private static final Pattern RGB = Pattern.compile("(\\d+)\\D+(\\d+)\\D+(\\d+)");

    private final Runnable syncBar = new Runnable() {
        @Override
        public void run() {
            web.evaluateJavascript(TOP_COLOR_JS, new ValueCallback<String>() {
                @Override
                public void onReceiveValue(String v) {
                    applyBarColor(v);
                }
            });
            ui.postDelayed(this, 2000);
        }
    };

    private void applyBarColor(String css) {
        if (css == null) {
            return;
        }
        Matcher m = RGB.matcher(css);
        if (!m.find()) {
            return;
        }
        int r = Integer.parseInt(m.group(1)), g = Integer.parseInt(m.group(2)), b = Integer.parseInt(m.group(3));
        if (r > 255 || g > 255 || b > 255) {
            return;
        }
        getWindow().setStatusBarColor(Color.rgb(r, g, b));
        boolean light = (r * 299 + g * 587 + b * 114) / 1000 > 160;
        View d = getWindow().getDecorView();
        int f = d.getSystemUiVisibility();
        d.setSystemUiVisibility(light ? f | View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR : f & ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
    }

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        alive = true;
        web = new WebView(this);
        web.setVisibility(View.INVISIBLE); // sahifa yuklanguncha gilamli ekran ko'rinib turadi
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setGeolocationEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        web.addJavascriptInterface(new Notifier.Bridge(this), "TozaGilamApp");
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);

        final String host = Uri.parse(BuildConfig.BASE_URL).getHost();

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                String scheme = u.getScheme() == null ? "" : u.getScheme();
                boolean http = scheme.equals("http") || scheme.equals("https");
                if (http && host != null && host.equalsIgnoreCase(u.getHost())) {
                    return false; // CRM sahifalari ilova ichida ochiladi
                }
                // Xarita, telefon, Telegram va boshqa havolalar tashqi ilovada ochiladi
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (Exception ignored) {
                }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    String html = "<html><body style='font-family:sans-serif;text-align:center;padding:48px 24px'>"
                            + "<h2>Internet yo'q</h2><p>Aloqani tekshirib, qayta urinib ko'ring.</p>"
                            + "<a href='" + BuildConfig.BASE_URL + "' style='display:inline-block;padding:14px 28px;"
                            + "background:#0F766E;color:#fff;border-radius:12px;text-decoration:none'>Qayta urinish</a>"
                            + "</body></html>";
                    view.loadDataWithBaseURL(BuildConfig.BASE_URL, html, "text/html", "utf-8", null);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
                view.setVisibility(View.VISIBLE);
                view.evaluateJavascript(Notifier.JS, null);
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
                callback.invoke(origin, hasLocation(), false);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) {
                    fileCallback.onReceiveValue(null);
                }
                fileCallback = callback;
                try {
                    startActivityForResult(params.createIntent(), REQ_FILE);
                } catch (Exception e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(BuildConfig.BASE_URL);
        }

        askPermissions();
    }

    private boolean hasLocation() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
    }

    private void askPermissions() {
        List<String> need = new ArrayList<>();
        if (!hasLocation()) {
            need.add(Manifest.permission.ACCESS_FINE_LOCATION);
            need.add(Manifest.permission.ACCESS_COARSE_LOCATION);
        }
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            need.add(Manifest.permission.POST_NOTIFICATIONS);
        }
        if (need.isEmpty()) {
            startTracking();
        } else {
            requestPermissions(need.toArray(new String[0]), REQ_PERMS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        if (requestCode == REQ_PERMS && hasLocation()) {
            startTracking();
        }
    }

    private void startTracking() {
        Intent i = new Intent(this, TrackService.class);
        try {
            if (Build.VERSION.SDK_INT >= 26) {
                startForegroundService(i);
            } else {
                startService(i);
            }
        } catch (Exception ignored) {
        }
        askBatteryOnce();
    }

    /** Telefon ilovani fonda o'chirib qo'ymasligi uchun bir marta ruxsat so'raladi. */
    @SuppressLint("BatteryLife")
    private void askBatteryOnce() {
        SharedPreferences p = getSharedPreferences("app", Context.MODE_PRIVATE);
        if (p.getBoolean("battery_asked", false)) {
            return;
        }
        p.edit().putBoolean("battery_asked", true).apply();
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null && !pm.isIgnoringBatteryOptimizations(getPackageName())) {
            try {
                startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                        Uri.parse("package:" + getPackageName())));
            } catch (Exception ignored) {
            }
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_FILE && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onResume() {
        super.onResume();
        ui.removeCallbacks(syncBar);
        ui.postDelayed(syncBar, 800);
    }

    @Override
    protected void onPause() {
        super.onPause();
        ui.removeCallbacks(syncBar);
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onDestroy() {
        alive = false;
        ui.removeCallbacks(syncBar);
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
