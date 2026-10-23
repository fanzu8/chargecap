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
import android.os.PowerManager
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
 * The service owns the same three things the activity starts: the sampler, the
 * rules and the voice.  When Android recreates the process after a kill, only
 * the service's onCreate runs -- so the rules are armed from Prefs here, and
 * the first sample arms them silently (turning notifications on, or booting,
 * is not a crossing).
 */
class MonitorService : Service() {
    private lateinit var prefs: Prefs
    private var wake: PowerManager.WakeLock? = null

    /** The switches and lines as the page changes them; the line follows. */
    private val changed =
        SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == null || key.startsWith("notify")) updateNotification()
        }

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        createNotificationChannel(this)

        // the same starts MainActivity makes; every one of them is safe to
        // call twice, and this is the one that survives the activity
        Sleeps.start(prefs)
        Voice.start(this)
        // no page in front unless the activity says otherwise: this is the
        // 3 s reader the rules need, not the 500 ms one a table needs
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

        // A foreground service keeps the process, but not the CPU: with the
        // screen off the phone suspends and the 3 s sampler stops until
        // something wakes it.  A partial wake lock is what makes "通知开关 on"
        // mean "the readings keep coming" -- and why it costs battery; the
        // switch off stops the service and releases it.
        try {
            wake = getSystemService(PowerManager::class.java)
                ?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,
                              "chargecap:notifications")
                ?.apply {
                    setReferenceCounted(false)
                    acquire()
                }
        } catch (e: Exception) {
            wake = null
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // 通知开关 was turned off while we were not running: nothing to keep
        if (!Prefs(this).notify) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onDestroy() {
        wake?.release()
        wake = null
        prefs.unlisten(changed)
        // the switch may have been turned off while the page was gone: stop
        // the reader if nothing else needs it
        Sampling.apply(this, prefs)
        stopForeground(STOP_FOREGROUND_REMOVE)
        // the service is going away: its banners belong to a process that is
        // not here any more, and an update must not leave them in the shade
        cancelAll(this)
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

        fun start(context: Context) {
            ContextCompat.startForegroundService(
                context, Intent(context, MonitorService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, MonitorService::class.java))
        }
    }
}
