// ---------------------------------------------------------------------------
// chargecap - keep an always-plugged-in phone inside a charge window
//
// Licence: General Pleasure League (GPL) 1.0
//          https://github.com/fanzu8/General-Pleasure-League
//
//          You are the general of your own life, the master of your own fate:
//          no restrictions, no compulsions - use it, change it, share it, and
//          let pleasure be your primary guide.  Just be happy.
// ---------------------------------------------------------------------------

package org.chargecap.android

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * The plug and the cable are the one pair of readings Android broadcasts
 * instead of making the app wait for the 30 s alarm: take the reading now so
 * 电源连接 / 电源断开 can be said while it is news.
 *
 * With 禁止休眠 on the 3 s reader already covers this; a page in front has its
 * 500 ms reader.  The alarm remains the fallback when the service had to be
 * started and Android refuses a background foreground-service start.
 */
class PowerReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_POWER_CONNECTED &&
            intent.action != Intent.ACTION_POWER_DISCONNECTED) return
        val app = context.applicationContext
        val prefs = Prefs(app)
        if (!prefs.notify) return
        if (!MonitorService.running) {
            try {
                MonitorService.start(app)
            } catch (t: Throwable) {
                // the 30 s alarm will start it; the plug notification waits
            }
        } else if (!prefs.inhibitSleep && !(Sampling.visible && prefs.live)) {
            Monitor.sampleOnce(app)
        }
    }
}
