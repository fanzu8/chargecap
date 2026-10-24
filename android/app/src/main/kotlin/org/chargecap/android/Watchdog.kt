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

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.SystemClock

/**
 * The 30 s sampling alarm, and the last thing that outlives the process.
 *
 * A foreground service keeps the process, but without a wake lock the CPU may
 * sleep between alarms.  AlarmManager's PendingIntent survives a killed
 * process, so every firing is one reading: when the service is alive
 * RestartReceiver takes a single sample; when it is not, the receiver starts
 * the service and the service's onCreate takes that first sample.  Either way
 * the next alarm is armed from the receiver, and the CPU can sleep until it.
 *
 * This is deliberately a one-shot plus re-arm, not setRepeating: the system
 * treats repeating alarms inexactly, and a killed receiver would leave the
 * chain broken.
 */
object Watchdog {
    const val ACTION_RESTART = "org.chargecap.android.WATCHDOG_RESTART"

    private const val REQUEST = 0x5A17

    /**
     * One background reading every 30 s.  Outside Doze an exact
     * AllowWhileIdle alarm honours this; inside Doze Android stretches it to
     * roughly one per 9 minutes.  The app's battery-optimization whitelist
     * relaxes that on some ROMs; a vendor freezer can still delay it.
     */
    const val DELAY_MS = 30_000L

    private fun pending(context: Context): PendingIntent =
        PendingIntent.getBroadcast(
            context,
            REQUEST,
            Intent(context, RestartReceiver::class.java).setAction(ACTION_RESTART),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

    /**
     * Arm the next check, replacing any pending one.  Exact when the platform
     * lets us; otherwise the inexact variant still wakes the receiver, just
     * later -- the settings page has the door to grant exact alarms.
     */
    fun arm(context: Context, delayMs: Long = DELAY_MS) {
        val app = context.applicationContext
        val manager = app.getSystemService(AlarmManager::class.java) ?: return
        val at = SystemClock.elapsedRealtime() + delayMs.coerceAtLeast(1_000L)
        val pending = pending(app)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
                !manager.canScheduleExactAlarms()
            ) {
                manager.setAndAllowWhileIdle(
                    AlarmManager.ELAPSED_REALTIME_WAKEUP, at, pending)
            } else {
                manager.setExactAndAllowWhileIdle(
                    AlarmManager.ELAPSED_REALTIME_WAKEUP, at, pending)
            }
        } catch (t: Throwable) {
            // a vendor that rejects exact alarms still gets the slower wake-up
            try {
                manager.setAndAllowWhileIdle(
                    AlarmManager.ELAPSED_REALTIME_WAKEUP, at, pending)
            } catch (_: Throwable) {
                // nothing else to do; the next service start will retry
            }
        }
    }

    /** 通知开关 off, or the service was stopped on purpose: no more wake-ups. */
    fun cancel(context: Context) {
        val app = context.applicationContext
        val manager = app.getSystemService(AlarmManager::class.java) ?: return
        val pending = pending(app)
        manager.cancel(pending)
        pending.cancel()
    }
}
