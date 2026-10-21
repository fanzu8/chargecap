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

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.flow.StateFlow
import kotlin.math.abs

// The three layers the UI stands on, kept apart on purpose:
//
//   Prefs    remembers -- one property or one key per stored value, and nothing
//            else below the UI touches the file (Prefs.kt).
//   Monitor  reads     -- the battery round happens in one place and publishes
//            one Snapshot at a time (Battery.kt).
//   AppState is what a page sees: the stored values as Compose state, each one
//            read-only to the page and written through a setter that also
//            reaches Prefs, plus the monitor's flow handed on untouched.
//
// A page therefore takes an AppState and nothing else: a new switch is one
// value and one setter here plus a row on the page, a new notification is one
// line in NOTIFICATIONS, and a new reading is a field on Snapshot plus a row in
// the status table.  Neither page learns where any of it comes from.

/** Which screen is showing: 通知, the page the app opens on; 高级, the panel the
 *  GTK app draws; or 设置, one step in from either of them. */
enum class Page { NOTIFY, OTHER, SETTINGS }

/**
 * One notification, all of it on one line.
 *
 * 通知 draws a row per entry; Prefs keeps a switch, a number, a way of arriving
 * and how often it speaks under each key; Rules.kt reads the same table.  So a new
 * notification is one line here and nothing else -- no new state, no new row,
 * no key to remember anywhere.  [title] and [label] are lambdas because the
 * words are translated while the UI is being built, not once at class load.
 */
data class Notification(
    /** the key its answers are stored under */
    val key: String,
    /** 充电完成 */
    val title: () -> String,
    /** 达 / 低于 / 高于: how its number reads */
    val label: () -> String,
    /** the unit of that number */
    val unit: String,
    /** where the number starts */
    val default: Int,
    /** how far one press of its stepper moves it */
    val step: Int,
    /** ... and how far it may go */
    val low: Int,
    val high: Int,
    /**
     * Whether it has a number at all.  The four about the plug and the
     * charging state have none -- they are on or they are not -- so their row
     * is a title, a switch and the answers under it, with nothing to step.
     */
    val numbered: Boolean = true,
    /** A line this one has to stay above, by key: 充电完成 over 电量过低. */
    val above: String? = null,
    /**
     * The word on the count's last chip and the reading that stops it, for the
     * notifications where "keep saying it" means something: 电量过低 waits for
     * the plug to go in, 充电完成 waits for it to come out.  Null where there is
     * nothing to wait for, and then the count stops at 10次.
     */
    val until: Until? = null,
    /**
     * How far past its line a sample is, in this one's own unit: negative means
     * it has not reached it.  The rule is then the same shape as the row -- one
     * number, one comparison -- and a reading the phone does not publish is
     * far away rather than a false alarm.
     */
    val distance: (Snapshot, Int) -> Float,
    /** the row's own word, where it is shorter than the name: 电源连接 is just
     *  连接 under the 电源 heading.  The sentence it says keeps [title]. */
    val short: () -> String = title,
) {
    /** The number as the row shows it: "100%" or "45 °C". */
    fun value(reading: Int): String = "$reading$unit"

    /** A number kept inside the range this notification allows. */
    fun inside(reading: Int): Int = reading.coerceIn(low, high)

    /** The sentence the banner and the voice both use: "充电完成 55%", or for
     *  a state, the state itself. */
    fun says(reading: Int): String =
        if (numbered) "${title()} ${value(reading)}" else title()
}

/**
 * The thirteen 通知 offers, in the order the page shows them.
 *
 * Every one starts the same way: off, a voice, said once -- and at 1次 there is
 * no gap, so 间隔 shows 0 and nothing can change it.  The numbers are the ones a
 * phone is usually watched at, and they are the notification's own: the panel's
 * 上限 / 下限 stay the daemon's.
 */
val NOTIFICATIONS = listOf(
    Notification(
        "done", { tr("充电完成") }, { tr("达") }, "%", 100, 1, 0, 100,
        // full means plugged in and there: an unplugged phone is never done,
        // and unplugging is what lets it be said again on the next charge
        above = "low",
        // ... and until the power goes off, saying it is the reminder to do so
        until = Until({ tr("直到电源断开") }, { s -> !s.plugged }),
        distance = { s, at -> if (s.plugged) (s.capacity ?: -1).toFloat() - at else -1000f },
    ),
    Notification(
        "low", { tr("电量过低") }, { tr("低于") }, "%", 10, 1, 0, 100,
        // until the plug goes in: the low charge is fixed by charging
        until = Until({ tr("直到开始充电") }, { s -> s.charging }),
        distance = { s, at -> at - (s.capacity ?: Int.MAX_VALUE).toFloat() },
    ),
    // the plug and the charging state: on or off, so the distance is +1 and
    // -1 and the notification fires on the change rather than on a number
    Notification(
        "plugged", { tr("电源连接") }, { tr("达") }, "", 0, 1, 0, 0,
        short = { tr("连接") },
        numbered = false,
        distance = { s, _ -> if (s.plugged) 1f else -1f },
    ),
    Notification(
        "unplugged", { tr("电源断开") }, { tr("达") }, "", 0, 1, 0, 0,
        short = { tr("断开") },
        numbered = false,
        distance = { s, _ -> if (s.plugged) -1f else 1f },
    ),
    Notification(
        "charging", { tr("充电中") }, { tr("达") }, "", 0, 1, 0, 0,
        numbered = false,
        distance = { s, _ -> if (s.charging) 1f else -1f },
    ),
    Notification(
        "idle", { tr("未充电") }, { tr("达") }, "", 0, 1, 0, 0,
        numbered = false,
        distance = { s, _ -> if (s.charging) -1f else 1f },
    ),
    Notification(
        "hot", { tr("温度过高") }, { tr("高于") }, " °C", 45, 1, -60, 100,
        short = { tr("过高") },
        distance = { s, at -> ((s.tempC ?: -273.0) - at).toFloat() },
    ),
    Notification(
        "cold", { tr("温度过低") }, { tr("低于") }, " °C", -20, 1, -60, 100,
        short = { tr("过低") },
        distance = { s, at -> at - (s.tempC ?: 100.0).toFloat() },
    ),
    Notification(
        "vhigh", { tr("电压过高") }, { tr("高于") }, " mV", 4300, 100, 3000, 5000,
        short = { tr("过高") },
        // the gauge's reading is in volts; the row speaks millivolts, so every
        // notification about it is a whole number like the others
        distance = { s, at -> s.voltageV?.let { (it * 1000.0).toFloat() - at } ?: -1000f },
    ),
    Notification(
        "vlow", { tr("电压过低") }, { tr("低于") }, " mV", 3400, 100, 2500, 4500,
        short = { tr("过低") },
        distance = { s, at -> s.voltageV?.let { at - (it * 1000.0).toFloat() } ?: -1000f },
    ),
    Notification(
        "iin", { tr("充电电流过高") }, { tr("高于") }, " mA", 3000, 100, 0, 10000,
        short = { tr("充电过高") },
        // the reading is signed: positive while charging, so only a phone on
        // the charger can cross this one
        distance = { s, at -> s.currentA?.let { (it * 1000.0).toFloat() - at } ?: -1000f },
    ),
    Notification(
        "drain", { tr("放电电流过高") }, { tr("高于") }, " mA", 1000, 100, 0, 5000,
        short = { tr("放电过高") },
        // ... and the other way round: it is the size of a discharge that is
        // compared, so a phone on the charger goes quiet
        distance = { s, at -> s.currentA?.let { -(it * 1000.0).toFloat() - at } ?: -1000f },
    ),
    Notification(
        "power", { tr("功率过高") }, { tr("高于") }, " W", 20, 1, 0, 100,
        short = { tr("过高") },
        // either direction counts: charging hard is the phone working, and
        // draining hard is it working too
        distance = { s, at -> s.powerW?.let { (abs(it)).toFloat() - at } ?: -1000f },
    ),
)

/**
 * A count that only stops when the reading says so: the words on the chip, and
 * the snapshot that means the reminder has done its job.
 */
data class Until(val label: () -> String, val done: (Snapshot) -> Boolean)

/**
 * How many times a voice says it, and 0 for the notification's own endless one
 * ([Notification.until]) when it has one.  Silence is not a count -- a voice
 * that fires once is a voice that fires -- so the shortest is 1次.
 */
val TIMES: List<Pair<Int, () -> String>> = listOf(
    1 to { tr("1次") },
    2 to { tr("2次") },
    3 to { tr("3次") },
    5 to { tr("5次") },
    10 to { tr("10次") },
)

/** The counts this one offers: the plain ones, then its own (0) if it has one. */
fun Notification.times(): List<Pair<Int, () -> String>> =
    TIMES + listOfNotNull(until?.let { 0 to it.label })

/** How a count reads on the chip. */
fun Notification.timesLabel(count: Int): String =
    times().firstOrNull { it.first == count }?.second?.invoke() ?: TIMES.first().second()

/**
 * How long a notification waits between repeats -- the 间隔 beside 次数.  It
 * means nothing at 1次, so the page only draws it once there is a repeat to
 * space out.
 *
 * From a second to five minutes: the short ones are for a banner you want to
 * see again while you are looking at the phone, the long ones for a reminder
 * that should not become an alarm.  The labels are units rather than words, so
 * they read the same in both languages.
 */
val GAPS: List<Pair<String, Int>> = listOf(
    "1s" to 1, "2s" to 2, "3s" to 3, "5s" to 5, "10s" to 10,
    "15s" to 15, "20s" to 20, "30s" to 30, "1min" to 60, "2min" to 120,
    "5min" to 300,
)

/** The gap a fresh install waits: two seconds, long enough to hear one and
 *  the next as two. */
const val DEFAULT_GAP = 2

/** How a gap reads on the chip. */
fun gapLabel(secs: Int): String =
    GAPS.firstOrNull { it.second == secs }?.first ?: "2s"

/**
 * Everything the two pages read and write, in one holder.
 *
 * Every value is a `val` to the pages and a setter here: the setter is the only
 * way in, and it is where Prefs is written -- so a page never has to know
 * whether something is remembered, published or both.
 */
@Stable
class AppState(
    private val prefs: Prefs,
    private val inhibitor: SleepInhibitor,
) {
    // ---- the header: the theme, the language, which page is showing ---------

    private var themeState by mutableStateOf(prefs.theme)
    val theme: Theme
        get() = themeState

    fun setTheme(picked: Theme) {
        themeState = picked
        prefs.theme = picked
    }

    private var langState by mutableStateOf(prefs.lang)
    val lang: Lang
        get() = langState

    fun setLang(picked: Lang) {
        langState = picked
        Strings.lang = picked
        prefs.lang = picked
    }

    var page by mutableStateOf(Page.NOTIFY)
        private set

    /** The page 设置 was opened from, so its ‹ 返回 goes back there. */
    private var back = Page.NOTIFY

    /** Go to a page -- remembering where 设置 was opened from. */
    fun show(target: Page) {
        if (target == Page.SETTINGS) back = page
        page = target
    }

    /** The phone's own back: 设置 to the page that opened it, 高级 to 通知. */
    fun leave() {
        page = if (page == Page.SETTINGS) back else Page.NOTIFY
    }

    // ---- 通知 ---------------------------------------------------------------

    private var notifyState by mutableStateOf(prefs.notify)

    /** The master switch: off until it is turned on. */
    val notify: Boolean
        get() = notifyState

    fun setNotify(on: Boolean) {
        notifyState = on
        prefs.notify = on
        arm()
        // switched off is silent at once: a reminder that was still being said
        // -- and still repeating -- does not get to finish its count
        if (!on) {
            stopReminders()
            Voice.stop()
        }
    }

    /** One switch per notification, off until asked: a fresh install arms
     *  nothing, and turning the master switch on does not start a page of
     *  reminders nobody chose. */
    private val items = mutableStateMapOf<String, Boolean>().apply {
        NOTIFICATIONS.forEach { put(it.key, prefs.notifyItem(it.key)) }
    }

    /**
     * One answer per notification -- kind, count and gap in one value -- read
     * from Prefs once, at start-up.  They are not three maps on purpose: the
     * page's chips and the reminder's loop both take the whole answer, so no
     * one can read a stale kind beside a fresh count.
     */
    private val answers = mutableStateMapOf<String, Answer>().apply {
        NOTIFICATIONS.forEach { put(it.key, prefs.notifyAnswer(it)) }
    }

    /** The number each one fires at.  The notifications' own set: the panel's
     *  上限 / 下限 belong to the daemon and are never read here. */
    private val numbers = mutableStateMapOf<String, Int>().apply {
        NOTIFICATIONS.forEach { put(it.key, prefs.notifyAt(it.key, it.default)) }
    }

    /**
     * The rules as the notifier reads them: what is switched on, at its number,
     * in the way it is set to arrive.  The master switch is the gate -- off
     * leaves the notifier nothing to watch -- and every setter below hands them
     * over again.
     *
     * [again] is the difference between the two kinds of change: a switch
     * changes which lines exist, so the notifier starts over and takes what is
     * already past them as read -- turning something on is not itself news; a
     * number moved with a stepper only moves where one line is, and must not
     * turn eight steps into eight banners.
     */
    private fun arm(again: Boolean = true) {
        val now = if (!notify) emptyList()
        else NOTIFICATIONS.filter { itemOn(it) }
            .map { Rule(it, at(it), answerOf(it)) }
        if (again) NotifyRules.arm(now) else NotifyRules.retune(now)
    }

    init {
        arm()
    }

    fun itemOn(n: Notification): Boolean = items[n.key] == true

    fun setItem(n: Notification, on: Boolean) {
        items[n.key] = on
        prefs.setNotifyItem(n.key, on)
        arm()
    }

    /** One notification's three answers, as the chips left them. */
    fun answerOf(n: Notification): Answer = answers[n.key] ?: Answer.FRESH

    /**
     * Set one of the three answers -- the chip hands back the whole answer,
     * changed in one field -- and keep the rules in step.
     *
     * The trap: a kind is a way of arriving, not a line, and the page lets it
     * be chosen while the reading already sits past the line (setup before
     * switching on).  That change re-arms the rules so the next sample says
     * it; a count or a gap only reshapes a repeat, so it retunes and leaves
     * what has been said said -- eight steps of 次数 must not be eight
     * banners.
     */
    fun setAnswer(n: Notification, answer: Answer) {
        val kindMoved = answer.kind != answerOf(n).kind
        answers[n.key] = answer.inside(n)
        prefs.setNotifyAnswer(n, answers.getValue(n.key))
        arm(again = kindMoved)
    }

    fun at(n: Notification): Int = numbers[n.key] ?: n.default

    /**
     * Where the number may land: inside the notification's own range, and clear
     * of any line it has to stay above -- 充电完成 over 电量过低, since two lines
     * that cross are two notifications arguing with each other.  Typed numbers
     * and stepped ones both come through here, so the check is in one place.
     */
    private fun keepApart(n: Notification, reading: Int): Int {
        val other = n.above?.let { key -> NOTIFICATIONS.firstOrNull { it.key == key } }
        val floor = other?.let { at(it) + 1 }
        // ... and the same line pushes back the other way
        val ceiling = NOTIFICATIONS.firstOrNull { it.above == n.key }?.let { at(it) - 1 }
        val lo = maxOf(n.low, floor ?: n.low)
        val hi = minOf(n.high, ceiling ?: n.high)
        return if (lo <= hi) reading.coerceIn(lo, hi) else hi
    }

    /** Where the number landed: the row shows this, not what was typed. */
    fun setAt(n: Notification, reading: Int): Int {
        val inside = keepApart(n, reading)
        numbers[n.key] = inside
        prefs.setNotifyAt(n.key, inside)
        arm(again = false)
        return inside
    }

    /** One press of a threshold's stepper: moved, and kept inside its range. */
    fun step(n: Notification, direction: Int) = setAt(n, at(n) + direction * n.step)


    // ---- 高级: the panel's own switches -------------------------------------

    private var inhibitState by mutableStateOf(prefs.inhibitSleep)

    /** 禁止休眠: the wake lock, held for as long as the switch is on. */
    val inhibit: Boolean
        get() = inhibitState

    fun setInhibit(on: Boolean) {
        inhibitState = on
        prefs.inhibitSleep = on
        if (on) inhibitor.acquire() else inhibitor.release()
        // 禁止休眠's turn-on is the moment 休眠记录 counts from: the
        // record answers "did it hold while I asked?", so it starts when the
        // asking does -- nothing to do with 通知开关
        if (on) Sleeps.restart()
    }

    private var metricsState by mutableStateOf(prefs.metrics.ifEmpty { DEFAULT_METRICS })

    /** The metrics the chart plots. */
    val metrics: List<String>
        get() = metricsState

    fun toggleMetric(key: String) {
        // kept in METRICS order, so the Y axes never jump around
        metricsState = if (key in metricsState) metricsState - key
        else METRIC_KEYS.filter { it in metricsState || it == key }
        prefs.metrics = metricsState
    }

    private var windowState by mutableStateOf(prefs.windowSecs)
    val windowSecs: Int
        get() = windowState

    fun setWindow(secs: Int) {
        windowState = secs
        prefs.windowSecs = secs
    }

    /** 实时采集: whether the page reads the phone at all. */
    private var liveState by mutableStateOf(prefs.live)

    val live: Boolean
        get() = liveState

    fun setLive(on: Boolean) {
        liveState = on
        prefs.live = on
        // no reads, no chart: 图形化 goes off with the table it draws from
        // rather than staying on over blank rows
        if (!on) setRecording(false)
    }

    private var recordState by mutableStateOf(prefs.record)

    /** 采集: whether the chart keeps the readings it sees. */
    val recording: Boolean
        get() = recordState

    fun setRecording(on: Boolean) {
        recordState = on
        prefs.record = on
        // the sampler lives in the process, not in the UI: the switch has to
        // reach it rather than being read from the page
        Monitor.recording = on
        // off is off: the curve goes with the switch, so the page has nothing
        // to draw until it is on again
        if (!on) history.clear()
    }

    private var sampleState by mutableStateOf(prefs.sampleMs)

    /** How often the chart stores a sample -- the monitor's own clock, and the
     *  one value that reaches past Prefs into the reader. */
    val sampleMs: Int
        get() = sampleState

    fun setSampleMs(ms: Int) {
        sampleState = ms
        prefs.sampleMs = ms
        Monitor.intervalMs = ms.toLong()
    }

    // ---- the live sample, as the monitor publishes it -----------------------

    /**
     * What the panel shows and the chart draws: the same flow for both, sampled
     * once in the process -- so a page that is not on screen costs nothing, and
     * two pages never disagree about what the battery is doing.
     */
    val samples: StateFlow<Snapshot>
        get() = Monitor.state

    /** The chart's history, filled by the monitor whichever page is showing. */
    val history: SampleBuffer
        get() = Monitor.buffer
}
