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
 * A phone that has just booted: if 通知开关 was on, bring the monitor back.
 *
 * The activity is the only place that can turn the switch on, so the answer is
 * in Prefs; without this the service would wait for someone to open the app,
 * and a phone in a pocket would be silent until they did.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // a boot and an update both stop the old process; the switch says
        // whether the monitor should come back
        if (intent.action != Intent.ACTION_BOOT_COMPLETED &&
            intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        if (Prefs(context).notify) MonitorService.start(context)
    }
}
