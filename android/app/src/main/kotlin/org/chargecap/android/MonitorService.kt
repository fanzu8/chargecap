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

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat

/**
 * 通知开关 on: the process that reads the battery while the app is off screen.
 *
 * Android does not let an ordinary background process keep sampling: Doze, app
 * standby and the vendor's freezer will stop it, however many autostart and
 * battery-whitelist switches are turned on.  A foreground service is the one
 * supported way to say "this is still doing something" -- and the price is the
 * small ongoing notification it must show, the same kind music players and
 * navigation apps use.
 *
 * The service owns the same two things the activity starts: the rules and the
 * voice.  When Android recreates the process after a kill, only the service's
 * onCreate runs -- so the rules are armed from Prefs here, and the first real
 * sample arms them silently (turning notifications on, or booting, is not a
 * crossing).
 *
 * It deliberately does not hold a wake lock.  The 30 s Watchdog alarm wakes
 * the process for one reading and then lets the CPU sleep; 禁止休眠 is the
 * explicit opt-in that keeps a lock (chargecap:sleep) and the 3 s reader.
 */
class MonitorService : Service() {
    private lateinit var prefs: Prefs

    /** The switches and lines as the page changes them; the line follows. */
    private val changed =
        SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == null || key.startsWith("notify")) updateNotification()
        }

    override fun onCreate() {
        super.onCreate()
        running = true
        prefs = Prefs(this)
        createNotificationChannel(this)

        // the same starts MainActivity makes; every one of them is safe to
        // call twice, and this is the one that survives the activity
        Sleeps.start(prefs)
        Voice.start(this)
        // 禁止休眠 is the only continuous lock: restore it here because the
        // service may be the only component left after a kill or a reboot
        if (prefs.inhibitSleep) SleepInhibitor.get(this).acquire()
        // no page in front unless the activity says otherwise: only 禁止休眠
        // starts the continuous 3 s reader; otherwise the 30 s alarm samples
        Sampling.apply(this, prefs)
        armRules(prefs)
        startNotifier(this)

        val note = notification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(ONGOING_ID, note,
                            ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(ONGOING_ID, note)
        }
        prefs.listen(changed)

        // The service was just started (boot, update, the switch, or an alarm
        // whose process had died): take the first reading now, so the rules
        // have something to arm against without waiting 30 s.
        if (!prefs.inhibitSleep && !(Sampling.visible && prefs.live)) {
            Monitor.sampleOnce(this)
        }

        // the one thing that survives this process: a one-shot alarm that
        // samples once if we are alive and starts the service if we are not
        Watchdog.arm(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // 通知开关 was turned off while we were not running: nothing to keep
        if (!Prefs(this).notify) {
            Watchdog.cancel(this)
            stopSelf()
            return START_NOT_STICKY
        }
        running = true
        Watchdog.arm(this)
        return START_STICKY
    }

    /** The task was swiped away; keep the alarm chain alive. */
    override fun onTaskRemoved(rootIntent: Intent?) {
        if (Prefs(this).notify) Watchdog.arm(this)
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        running = false
        prefs.unlisten(changed)
        // the switch may have been turned off while the page was gone: stop
        // the reader if nothing else needs it
        Sampling.apply(this, prefs)
        stopForeground(STOP_FOREGROUND_REMOVE)
        // the service is going away: its banners belong to a process that is
        // not here any more, and an update must not leave them in the shade
        cancelAll(this)
        // onDestroy is not guaranteed after SIGKILL, but when it runs the alarm
        // is the last thing this process can leave behind
        if (Prefs(this).notify) Watchdog.arm(this)
        else Watchdog.cancel(this)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    /** The rules, rebuilt from Prefs: the activity may not exist at all. */
    private fun armRules(prefs: Prefs) {
        val rules = if (!prefs.notify) emptyList()
        else NOTIFICATIONS.filter { prefs.notifyItem(it.key) }
            .map { Rule(it, prefs.notifyAt(it.key, it.default),
                        prefs.notifyAnswer(it)) }
        NotifyRules.arm(rules)
    }

    /** What the line says: why the service is there, and what it watches. */
    private fun notification(): Notification {
        val open = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val lines = NOTIFICATIONS.filter { prefs.notifyItem(it.key) }.map { n ->
            if (n.numbered) {
                "${n.title()} ${prefs.notifyAt(n.key, n.default)}${n.unit.trim()}"
            } else {
                n.title()
            }
        }
        val body = if (lines.isEmpty()) tr("没有打开的通知项")
                   else lines.joinToString("\n")
        val summary = if (lines.isEmpty()) tr("没有打开的通知项")
                      else lines.joinToString(" · ")
        return NotificationCompat.Builder(this, MONITOR_CHANNEL)
            .setSmallIcon(R.drawable.ic_notify_logo)
            .setColor(0xFF22C55E.toInt())
            .setContentTitle(tr("由于通知需要，后台运行中"))
            .setContentText(summary)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setOngoing(true)
            .setSilent(true)
            .setShowWhen(false)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(open)
            .build()
    }

    private fun updateNotification() {
        getSystemService(NotificationManager::class.java)
            ?.notify(ONGOING_ID, notification())
    }

    companion object {
        const val ONGOING_ID = 1

        /** Read by RestartReceiver: a dead process starts here at false. */
        @Volatile
        var running = false
            private set

        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context, Intent(context, MonitorService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, MonitorService::class.java))
        }
    }
}
