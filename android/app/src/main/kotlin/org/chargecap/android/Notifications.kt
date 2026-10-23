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

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// The Android half of a notification: the one channel everything posts on, the
// banner itself, and the wire from the monitor's samples to it.
//
// The decisions are not here -- which notification fires, and when, is Rules.kt
// -- and the words are the notification's own (AppState.kt), so this file is
// only "how Android says it": a channel, a banner, and a voice beside it.
//
// Android 8 keeps every notification a channel's, and the system's 通知 page
// hangs 横幅, 声音 and 震动 off that channel -- which is why the channel exists
// from the first launch, long before anything is posted: 设置's 通知横幅与声音
// row would otherwise lead to "此应用未发布任何通知" and nothing to switch.
// Importance high is what a banner and a sound mean.

/** The channel id, stored by Android for good: a posted notification keeps it. */
const val NOTIFY_CHANNEL = "chargecap"

/** The low, silent channel of the ongoing background notification. */
const val MONITOR_CHANNEL = "chargecap-monitor"

/** The app's own reader of the monitor's flow, with the process rather than
 *  with a page. */
private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
private var watching: Job? = null

/**
 * How often a threshold is judged, in milliseconds.
 *
 * The display reads at 500 ms because a number on screen should look live;
 * a battery's temperature, voltage and current do not need that for a
 * reminder -- three seconds is the same rate the postmarketOS daemon publishes
 * at, and it turns 6 judgments a second into one every third second.  A
 * crossing between two judgments is seen at the next one, so a plug or a
 * temperature spike is noticed within three seconds.
 */
private const val JUDGE_MS = 3000L

/** The reminder each notification is in the middle of, by its key. */
private val reminders = mutableMapOf<String, Job>()

/** Create the channel if it is not there yet. */
fun createNotificationChannel(context: Context) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
    val manager = context.getSystemService(NotificationManager::class.java) ?: return
    val channel = NotificationChannel(
        NOTIFY_CHANNEL,
        tr("充电提醒"),
        NotificationManager.IMPORTANCE_HIGH,
    ).apply {
        description = tr("电量、温度、电压、电流或功率越过你设的线时提醒")
    }
    manager.createNotificationChannel(channel)

    // the service's own line: low importance, no sound, no badge -- it is a
    // statement that monitoring is on, not a message to read
    val monitor = NotificationChannel(
        MONITOR_CHANNEL,
        tr("后台运行"),
        NotificationManager.IMPORTANCE_LOW,
    ).apply {
        description = tr("通知开关打开时保持后台运行")
        setShowBadge(false)
        setSound(null, null)
        enableVibration(false)
    }
    manager.createNotificationChannel(monitor)
}

/**
 * Start the rules: the monitor's samples in, banners and voices out.
 *
 * The samples are the monitor's own flow, read here as well as by the chart --
 * one reading, two listeners -- and this one runs with the process, so it keeps
 * watching with the screen off.
 */
fun startNotifier(context: Context) {
    if (watching?.isActive == true) return
    val app = context.applicationContext
    watching = scope.launch {
        var judgedAt = 0L
        Monitor.state.collect { sample ->
            val now = SystemClock.elapsedRealtime()
            // the first sample arms the rules at once; after that, every
            // JUDGE_MS -- the readings in between are for the panel
            if (judgedAt == 0L || now - judgedAt >= JUDGE_MS) {
                judgedAt = now
                NotifyRules.sample(sample) { rule -> remind(app, rule) }
            }
        }
    }
}

/**
 * One notification, all of it: its banner or its voice, then the same again
 * [Rule.gapSecs] later while the count has repeats left.
 *
 * The count belongs to the whole notification rather than to the voice alone --
 * a banner repeats too, and says the same sentence each time -- and 0 of them
 * means the notification's own endless one: repeat until the reading it waits
 * for says the reminder has done its job (the plug in for 电量过低, the cable
 * out for 充电完成).  A new reminder for the same key takes over rather than
 * stacking up behind the old one.
 *
 * A repeat is only news while the reading is still past the line: if the gap
 * was long enough for the battery to come back -- the phone cooled down, the
 * charge came up -- the count ends there instead of saying a thing that is no
 * longer true.  The rule is read again at each repeat rather than carried from
 * the first, so the same holds when the line itself has moved, or the
 * notification has been switched off, while the count was running.
 */
private fun remind(context: Context, rule: Rule) {
    val key = rule.n.key
    reminders.remove(key)?.cancel()
    reminders[key] = scope.launch {
        var said = 0
        while (true) {
            // what is set now, not what was set when it first fired: a line
            // moved or a switch thrown mid-count takes effect from here
            val live = NotifyRules.rules.firstOrNull { it.n.key == key }
                ?: return@launch
            // a banner is posted again rather than a second one added: the
            // notification keeps its slot, and the system alerts again.
            // Arriving is one or the other, never both, so the two are exclusive
            if (live.kind == NotifyKind.BANNER) {
                post(context, live)
            } else {
                // the repeats wait for the first to finish; a new reminder is
                // news, its echo is not
                Voice.say(live.says(), queue = said > 0)
            }
            said++
            // nothing says when it is over: say it once and let it go
            if (live.times == 0 && live.n.until == null) return@launch
            if (live.times != 0 && said >= live.times) return@launch
            delay(live.gapSecs * 1000L)
            // the gap was long enough for the reading to come back: what is
            // left of the count is no longer true, so it ends here
            val now = NotifyRules.rules.firstOrNull { it.n.key == key }
                ?: return@launch
            if (!now.crossed(Monitor.state.value)) return@launch
            if (now.times == 0 && now.n.until?.done(Monitor.state.value) == true) {
                return@launch
            }
        }
    }
}

/** Nothing more repeats: 通知开关 went off, so the page's gate is shut. */
fun stopReminders() {
    reminders.values.forEach { it.cancel() }
    reminders.clear()
}

/**
 * Drop every banner, and the ongoing line too.  A notification is state for
 * the process that posted it: after 通知开关 goes off, or an update replaces
 * that process, leaving the old ones in the shade is exactly the leftover this
 * app should not have.  Uninstall and the system's own package cleanup remove
 * the channels and the data; this is the part the app can do while it lives.
 */
fun cancelAll(context: Context) {
    context.getSystemService(NotificationManager::class.java)?.cancelAll()
}

/**
 * One banner: the app's icon, the channel 设置 points at, and the sentence the
 * rule says.  Tapping it opens the app; posting again under the same key
 * replaces the last one rather than stacking them up.
 */
fun post(context: Context, rule: Rule) {
    // Android 13 keeps the permission in the user's hands; without it there is
    // simply nothing to show
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
        PackageManager.PERMISSION_GRANTED
    ) return

    val manager = context.getSystemService(NotificationManager::class.java) ?: return
    val open = PendingIntent.getActivity(
        context,
        0,
        Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )
    val banner = NotificationCompat.Builder(context, NOTIFY_CHANNEL)
        .setSmallIcon(R.drawable.ic_notify_logo)
        // Android only lets the small icon be a mask; this is the one colour
        // it will take, so give it chargecap's green rather than the default
        .setColor(0xFF22C55E.toInt())
        .setContentTitle(tr("充电提醒"))
        .setContentText(rule.says())
        .setPriority(NotificationCompat.PRIORITY_HIGH)
        .setContentIntent(open)
        .setAutoCancel(true)
        .build()

    // one slot per notification, keyed by the notification's own key
    manager.notify(rule.n.key, 1, banner)
}
