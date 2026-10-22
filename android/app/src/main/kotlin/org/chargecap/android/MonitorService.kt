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
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

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
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var watching: Job? = null

    override fun onCreate() {
        super.onCreate()
        val prefs = Prefs(this)
        createNotificationChannel(this)

        // the same starts MainActivity makes; every one of them is safe to
        // call twice, and this is the one that survives the activity
        Sleeps.start(prefs)
        Voice.start(this)
        Monitor.recording = prefs.record
        Monitor.start(this, prefs.sampleMs.toLong())
        armRules(prefs)
        startNotifier(this)

        val first = notification(Monitor.state.value)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(ONGOING_ID, first,
                            ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(ONGOING_ID, first)
        }

        // keep the notification honest, but do not turn it into a ticker: a
        // line of text is enough to show the service is alive, and every post
        // is a wake-up the system counts.  A minute between changes is plenty;
        // the readings are shown to say "still here", not to be stared at.
        watching = scope.launch {
            var text = ""
            var at = 0L
            Monitor.state.collect { sample ->
                val now = SystemClock.elapsedRealtime()
                val next = ongoingText(sample)
                if (next != text && (at == 0L || now - at >= 60_000)) {
                    at = now
                    text = next
                    getSystemService(NotificationManager::class.java)
                        ?.notify(ONGOING_ID, notification(sample))
                }
            }
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
        watching?.cancel()
        scope.cancel()
        stopForeground(STOP_FOREGROUND_REMOVE)
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

    private fun ongoingText(s: Snapshot): String {
        val capacity = s.capacity?.let { "$it%" } ?: "—"
        val temp = s.tempC?.let { String.format("%.1f °C", it) } ?: "—"
        val state = if (s.charging) tr("充电中") else tr("未充电")
        return "$capacity · $temp · $state"
    }

    private fun notification(s: Snapshot): Notification {
        val open = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return NotificationCompat.Builder(this, MONITOR_CHANNEL)
            .setSmallIcon(R.drawable.ic_notify)
            .setContentTitle(tr("正在后台监控"))
            .setContentText(ongoingText(s))
            .setOngoing(true)
            .setSilent(true)
            .setShowWhen(false)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(open)
            .build()
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
