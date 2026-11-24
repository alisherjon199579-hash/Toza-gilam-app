package uz.tozagilam.chek;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

public class MainActivity extends Activity {
    private TextView st;
    private EditText url, key;
    private final Handler h = new Handler();

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 24);
        TextView t = new TextView(this);
        t.setText("Toza Gilam Chek v4 (QR alohida)\nCRM'da \"Yetkazildi\" bosilganda chek shu terminaldan chiqadi.");
        t.setTextSize(16);
        root.addView(t);
        url = new EditText(this);
        url.setHint("Server manzili (http://...)");
        url.setText(Cfg.url(this));
        url.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        root.addView(url);
        key = new EditText(this);
        key.setHint("Kalit");
        key.setText(Cfg.key(this));
        root.addView(key);
        Button save = new Button(this);
        save.setText("Saqlash va ishga tushirish");
        save.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                Cfg.save(MainActivity.this, url.getText().toString(), key.getText().toString());
                startService(new Intent(MainActivity.this, PollService.class));
            }
        });
        root.addView(save);
        Button test = new Button(this);
        test.setText("Sinov chek (QR bilan)");
        test.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                new Thread(new Runnable() { public void run() {
                    try {
                        JSONArray a = new JSONArray();
                        a.put(new JSONObject().put("t", "TOZA GILAM").put("s", 3).put("p", "center").put("b", 1));
                        a.put(new JSONObject().put("t", "Sinov cheki - printer ishlayapti").put("s", 2).put("p", "center"));
                        a.put(new JSONObject().put("q", "https://www.instagram.com/gilam_yuvish_korxonasii").put("s", 6).put("p", "center"));
                        a.put(new JSONObject().put("t", "@gilam_yuvish_korxonasii").put("s", 2).put("p", "center"));
                        String e = Printer.print(MainActivity.this, a);
                        Cfg.status(MainActivity.this, e == null ? "sinov chek chiqdi" : "XATO: " + e);
                    } catch (Throwable e) { Cfg.status(MainActivity.this, "XATO: " + e); }
                } }).start();
            }
        });
        root.addView(test);
        st = new TextView(this);
        st.setTextSize(15);
        st.setPadding(0, 24, 0, 0);
        root.addView(st);
        setContentView(root);
        if (Cfg.url(this).length() > 0) startService(new Intent(this, PollService.class));
    }

    private final Runnable tick = new Runnable() {
        public void run() {
            st.setText("Holat: " + Cfg.status(MainActivity.this));
            h.postDelayed(this, 1000);
        }
    };

    @Override protected void onResume() { super.onResume(); h.post(tick); }
    @Override protected void onPause() { super.onPause(); h.removeCallbacks(tick); }
}
