package uz.tozagilam.chek;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        if (Cfg.url(c).length() > 0) c.startService(new Intent(c, PollService.class));
    }
}
