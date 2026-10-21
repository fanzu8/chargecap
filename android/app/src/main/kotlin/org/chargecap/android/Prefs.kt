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

import android.content.Context
import android.os.PowerManager

// Where the per-user UI preferences live -- the Android answer to the GTK
// app's ~/.config/chargecap/ui.json: which metrics are plotted, over which
// window, and the language pushed by hand.

class Prefs(context: Context) {
    private val store =
        context.applicationContext.getSharedPreferences("chargecap", Context.MODE_PRIVATE)

    var lang: Lang
        get() = Lang.of(store.getString("lang", null))
        set(value) = store.edit().putString("lang", value.tag).apply()

    /** The background: dark unless the user picks otherwise (the default). */
    var theme: Theme
        get() = Theme.of(store.getString("theme", null))
        set(value) = store.edit().putString("theme", value.tag).apply()

    /** The selected metrics, in METRICS order; empty means "not chosen yet". */
    var metrics: List<String>
        get() = (store.getString("metrics", null) ?: "")
            .split(',')
            .filter { it in METRIC_KEYS }
        set(value) = store.edit()
            .putString("metrics", value.filter { it in METRIC_KEYS }.joinToString(","))
            .apply()

    var windowSecs: Int
        get() = store.getInt("window", 60).takeIf { it in WINDOW_SECS } ?: 60
        set(value) = store.edit().putInt("window", value).apply()

    /** How often the chart stores a sample, in milliseconds. */
    var sampleMs: Int
        get() = sampleMs(store.getInt("sample_ms", DEFAULT_SAMPLE_MS))
        set(value) = store.edit().putInt("sample_ms", value).apply()

    var inhibitSleep: Boolean
        get() = store.getBoolean("inhibit_sleep", false)
        set(value) = store.edit().putBoolean("inhibit_sleep", value).apply()

    /** 实时采集: whether the 高级 page reads the phone at all.  On until asked
     *  not to -- a panel that shows nothing on a fresh install looks broken. */
    var live: Boolean
        get() = store.getBoolean("live", true)
        set(value) = store.edit().putBoolean("live", value).apply()

    /** 图形化: whether the chart keeps the readings it sees.  Off until asked --
     *  a look at the phone is not a consent to record every sample. */
    var record: Boolean
        get() = store.getBoolean("record", false)
        set(value) = store.edit().putBoolean("record", value).apply()

    // ---- 通知 (the table of them is NOTIFICATIONS, in AppState.kt) ---------

    /** Notifications are off until the master switch is turned on. */
    var notify: Boolean
        get() = store.getBoolean("notify", false)
        set(value) = store.edit().putBoolean("notify", value).apply()

    /**
     * One switch per notification, off until asked: a fresh install arms
     * nothing, so turning the master switch on does not start a page of
     * reminders nobody chose.
     */
    fun notifyItem(key: String): Boolean = store.getBoolean("notify_$key", false)

    fun setNotifyItem(key: String, on: Boolean) =
        store.edit().putBoolean("notify_$key", on).apply()

    /**
     * The number a notification fires at: the charge to call it complete
     * (100 %), the charge to call it low (10 %), the temperature to call it hot
     * (45 °C) and cold (-20 °C) -- the defaults come from the table.  They are
     * the notifications' own: the panel's 上限 / 下限 belong to the daemon and
     * never read these.
     */
    fun notifyAt(key: String, fallback: Int): Int =
        store.getInt("notify_${key}_at", fallback)

    fun setNotifyAt(key: String, value: Int) =
        store.edit().putInt("notify_${key}_at", value).apply()

    /**
     * One notification's three answers, read back as one value: how it arrives,
     * how often it says it, and how long it waits between those times.
     *
     * They are one answer on purpose.  The page draws them as three chips and
     * the reminder reads all three at every repeat, so storing them apart
     * would be three memories that can disagree -- a kind of one and a count
     * of another.  The three keys are kept because a phone may already hold
     * them (the row has written them under these names since 间隔 arrived).
     */
    fun notifyAnswer(n: Notification): Answer = Answer.of(
        n,
        store.getString("notify_${n.key}_kind", null),
        store.getInt("notify_${n.key}_times", 1),
        store.getInt("notify_${n.key}_gap", DEFAULT_GAP),
    )

    fun setNotifyAnswer(n: Notification, answer: Answer) {
        store.edit()
            .putString("notify_${n.key}_kind", answer.kind.tag)
            .putInt("notify_${n.key}_times", answer.times)
            .putInt("notify_${n.key}_gap", answer.gap)
            .apply()
    }

    // ---- 休眠记录 (the record is Sleeps, in Sleep.kt) -----------------------

    /** 禁止休眠's last turn-on, the anchor the sleep count starts from. */
    var sleepAnchor: Long
        get() = store.getLong("sleep_anchor", 0)
        set(value) = store.edit().putLong("sleep_anchor", value).apply()

    /** The elapsedRealtime of the last write: a smaller one is a reboot. */
    var sleepElapsed: Long
        get() = store.getLong("sleep_elapsed", 0)
        set(value) = store.edit().putLong("sleep_elapsed", value).apply()

    var sleepCount: Int
        get() = store.getInt("sleep_count", 0)
        set(value) = store.edit().putInt("sleep_count", value).apply()

    /** The kept sleeps, "at:secs" joined by ;, newest first. */
    var sleepNaps: String
        get() = store.getString("sleep_naps", "") ?: ""
        set(value) = store.edit().putString("sleep_naps", value).apply()
}

/**
 * How a notification arrives, the page's own choice: a banner or a voice.
 * A voice is the default -- the phone says what happened rather than lighting
 * up its shade -- and an unknown tag, 语音 + 横幅 included, falls back to it,
 * the same shape as Theme.
 */
enum class NotifyKind(val tag: String) {
    BANNER("banner"), VOICE("voice");

    companion object {
        fun of(tag: String?): NotifyKind = entries.firstOrNull { it.tag == tag } ?: VOICE
    }
}

/**
 * One notification's three answers, as they are set right now: how it arrives
 * ([kind]), how many times it says its piece ([times]; 0 is the notification's
 * own endless one) and how long it waits between those times ([gap], seconds).
 *
 * They travel together because they are one answer: the row draws them as
 * three chips, a rule carries them into the notifier, and the reminder reads
 * them again at every repeat.  A value that is no longer offered (a count the
 * table dropped, an interval that is not in [GAPS]) is not a setting the user
 * can make -- it falls back to [FRESH]'s own, never to a guess.
 */
data class Answer(val kind: NotifyKind, val times: Int, val gap: Int) {
    companion object {
        /** A fresh install: a voice, said once, two seconds between repeats. */
        val FRESH = Answer(NotifyKind.VOICE, 1, DEFAULT_GAP)

        /** The counts the page can make, and the endless 0 where it offers one.
         *  Anything else is not an answer this notification can hold. */
        fun of(n: Notification, kind: String?, times: Int, gap: Int): Answer =
            Answer(
                NotifyKind.of(kind),
                if (n.times().any { it.first == times }) times else FRESH.times,
                if (GAPS.any { it.second == gap }) gap else FRESH.gap,
            )
    }

    /** The same answer with a count this notification really offers. */
    fun inside(n: Notification): Answer =
        if (n.times().any { it.first == times }) this else copy(times = FRESH.times)
}

/**
 * The Android answer to the daemon's `systemd-inhibit --what=sleep`: a partial
 * wake lock, held for as long as the switch is on, so the device does not go
 * to sleep and the network stays up.  The system releases it with the process,
 * so it can never outlive the app.
 */
class SleepInhibitor(context: Context) {
    private val power =
        context.applicationContext.getSystemService(Context.POWER_SERVICE) as PowerManager
    private var lock: PowerManager.WakeLock? = null

    val active: Boolean get() = lock?.isHeld == true

    fun acquire() {
        if (active) return
        lock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "chargecap:sleep")
            .also { it.acquire() }
    }

    fun release() {
        val held = lock ?: return
        lock = null
        if (held.isHeld) held.release()
    }
}
