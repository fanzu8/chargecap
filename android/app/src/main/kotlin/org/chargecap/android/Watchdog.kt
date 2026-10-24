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
 * The alarm that outlives the process.
 *
 * A foreground service, START_STICKY and a wake lock keep the reader running
 * while Android lets it.  The one thing that survives even a killed process is
 * a PendingIntent held by AlarmManager, so the service arms a one-shot alarm
 * and RestartReceiver re-arms it after every firing.  When the process is gone,
 * the receiver starts the foreground service again; when it is still alive,
 * the receiver only arms the next check.
 *
 * This is deliberately a one-shot plus re-arm, not setRepeating: the system
 * treats repeating alarms inexactly, and a killed receiver would leave the
 * chain broken.
 */
object Watchdog {
    const val ACTION_RESTART = "org.chargecap.android.WATCHDOG_RESTART"

    private const val REQUEST = 0x5A17

    /**
     * The recovery latency the phone asks for.  Outside Doze an exact
     * AllowWhileIdle alarm honours this; inside Doze Android stretches it to
     * roughly one per 9 minutes, which the foreground service and its wake
     * lock normally keep us out of.  A vendor freezer can still delay it.
     */
    const val DELAY_MS = 5_000L

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
