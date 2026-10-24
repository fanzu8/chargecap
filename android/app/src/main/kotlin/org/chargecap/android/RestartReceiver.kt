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
 * The other end of Watchdog: the process may have been killed since the alarm
 * was armed, so this receiver is often the only code of ours that runs.
 *
 * A live service gets one sample from this alarm; a dead one is first started
 * (an exact alarm is one of the few background starts Android still permits,
 * and onCreate takes that first sample).  Then the next alarm is armed and
 * the CPU is left to sleep; there is no wake lock to hold between them.
 */
class RestartReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Watchdog.ACTION_RESTART) return
        val app = context.applicationContext
        val prefs = Prefs(app)
        if (!prefs.notify) {
            Watchdog.cancel(app)
            return
        }
        if (!MonitorService.running) {
            try {
                MonitorService.start(app)
            } catch (t: Throwable) {
                // the alarm remains armed and will try again
            }
        } else if (!prefs.inhibitSleep && !(Sampling.visible && prefs.live)) {
            // the service is alive but idle: this alarm is the reader
            Monitor.sampleOnce(app)
        }
        Watchdog.arm(app)
    }
}
