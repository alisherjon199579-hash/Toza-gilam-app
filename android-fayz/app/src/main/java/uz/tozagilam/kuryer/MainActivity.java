package uz.tozagilam.kuryer;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.DialogInterface;
import android.content.IntentFilter;
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
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** CRM'ni ilova ichida ochadi va joylashuv xizmatini ishga tushiradi. */
public class MainActivity extends Activity {
    private static final int REQ_PERMS = 1;
    private static final int REQ_FILE = 2;
    private static final int REQ_MIC = 3;

    private PermissionRequest micRequest; // chatda ovozli xabar yozish uchun

    /** Ilova oynasi tirikmi: tirik bo'lsa xabarlarni shu oyna kuzatadi, bo'lmasa xizmat. */
    static volatile boolean alive;
    /** Foydalanuvchi hozir ilovaga qarab turibdimi. */
    static volatile boolean resumed;

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
        web.addJavascriptInterface(new Notifier.Bridge(this, false), "TozaGilamApp");
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
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                view.evaluateJavascript(Notifier.JS, null);
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
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        boolean wantsMic = false;
                        for (String r : request.getResources()) {
                            if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(r)) {
                                wantsMic = true;
                            }
                        }
                        if (!wantsMic) {
                            request.deny();
                        } else if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                            request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                        } else {
                            micRequest = request;
                            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
                        }
                    }
                });
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
        handleIntent(getIntent());
    }

    /** Ilova har safar ekranga chiqqanda yangi versiya bor-yo'qligini tekshiradi. */
    private void checkUpdate() {
        Updater.check(this, true, new Runnable() {
            @Override
            public void run() {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        offerUpdate();
                    }
                });
            }
        });
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent);
    }

    /** Yangilanish bildirishnomasi bosilganda darhol yuklashni boshlaydi. */
    private void handleIntent(Intent intent) {
        if (intent != null && intent.getBooleanExtra(Updater.EXTRA_UPDATE, false)) {
            intent.removeExtra(Updater.EXTRA_UPDATE);
            startUpdate();
        }
    }

    private boolean offered;

    private void offerUpdate() {
        if (offered || isFinishing() || !Updater.available()) {
            return;
        }
        if (!resumed) {
            Updater.notifyUpdate(getApplicationContext());
            return;
        }
        offered = true;
        new AlertDialog.Builder(this)
                .setTitle("Yangi versiya tayyor")
                .setMessage("Ilovaning yangi versiyasi chiqdi. Hozir yangilaysizmi?")
                .setPositiveButton("Yangilash", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface d, int w) {
                        startUpdate();
                    }
                })
                .setNegativeButton("Keyinroq", null)
                .show();
    }

    private BroadcastReceiver dlReceiver;
    private long dlId = -1;

    /** Yangi APK'ni yuklab, o'rnatish oynasini ochadi. */
    private void startUpdate() {
        if (Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
            Toast.makeText(this, "Avval shu ilovaga o'rnatishga ruxsat bering, keyin qaytib «Yangilash»ni bosing", Toast.LENGTH_LONG).show();
            offered = false;
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName())));
            } catch (Exception ignored) {
            }
            return;
        }
        if (dlId != -1) {
            Toast.makeText(this, "Yuklanmoqda…", Toast.LENGTH_SHORT).show();
            return;
        }
        try {
            final DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
            File dir = getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS);
            if (dir != null) {
                new File(dir, "fayz-gilam.apk").delete();
            }
            DownloadManager.Request rq = new DownloadManager.Request(Uri.parse(Updater.APK_URL))
                    .setTitle("Fayz Gilam yangilanishi")
                    .setMimeType("application/vnd.android.package-archive")
                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
                    .setDestinationInExternalFilesDir(this, android.os.Environment.DIRECTORY_DOWNLOADS, "fayz-gilam.apk");
            if (dlReceiver == null) {
                dlReceiver = new BroadcastReceiver() {
                    @Override
                    public void onReceive(Context c, Intent i) {
                        if (i.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1) != dlId) {
                            return;
                        }
                        long id = dlId;
                        dlId = -1;
                        Uri apk = dm.getUriForDownloadedFile(id);
                        if (apk == null) {
                            Toast.makeText(MainActivity.this, "Yuklab bo'lmadi. Internetni tekshirib, qayta urinib ko'ring", Toast.LENGTH_LONG).show();
                            return;
                        }
                        try {
                            startActivity(new Intent(Intent.ACTION_VIEW)
                                    .setDataAndType(apk, "application/vnd.android.package-archive")
                                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK));
                        } catch (Exception e) {
                            openInBrowser();
                        }
                    }
                };
                IntentFilter f = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
                if (Build.VERSION.SDK_INT >= 33) {
                    registerReceiver(dlReceiver, f, Context.RECEIVER_EXPORTED);
                } else {
                    registerReceiver(dlReceiver, f);
                }
            }
            dlId = dm.enqueue(rq);
            Toast.makeText(this, "Yangi versiya yuklanmoqda…", Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            dlId = -1;
            openInBrowser();
        }
    }

    private void openInBrowser() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(Updater.APK_URL)));
        } catch (Exception ignored) {
        }
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
        if (requestCode == REQ_MIC && micRequest != null) {
            PermissionRequest r = micRequest;
            micRequest = null;
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                r.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            } else {
                r.deny();
            }
            return;
        }
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
        resumed = true;
        checkUpdate();
        ui.removeCallbacks(syncBar);
        ui.postDelayed(syncBar, 800);
    }

    @Override
    protected void onPause() {
        super.onPause();
        resumed = false;
        ui.removeCallbacks(syncBar);
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onDestroy() {
        alive = false;
        ui.removeCallbacks(syncBar);
        if (dlReceiver != null) {
            try {
                unregisterReceiver(dlReceiver);
            } catch (Exception ignored) {
            }
        }
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
