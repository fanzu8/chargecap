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
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.SystemClock
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

// The Android side of the GTK app's sysfs reads.  Everything the panel and the
// chart show comes from the two *public* Android sources: BatteryManager's
// properties and the sticky ACTION_BATTERY_CHANGED broadcast.  They are the
// closest thing Android has to a fuel gauge, and unlike /sys/class/power_supply
// (SELinux: denied to apps) they need no privileges.
//
// The one thing Android does not expose is the design capacity, which the GTK
// app reads straight from the gauge.  PowerProfile reports it and is only
// reachable through reflection, so it is attempted once and the health
// percentage simply stays "—" when that fails.

/** One pass of the battery read, as the panel shows it. */
data class Snapshot(
    /** bumped every pass, so identical readings still redraw the chart */
    val seq: Long = 0,
    val capacity: Int? = null,          // %
    val voltageV: Double? = null,       // V
    val currentA: Double? = null,       // A (signed: + charging)
    val tempC: Double? = null,          // °C
    val charging: Boolean = false,
    val plugged: Boolean = false,
    val plugType: Int = 0,              // BatteryManager.BATTERY_PLUGGED_*
    val chargeCounterUAh: Int? = null,  // the charge it holds now
    val designUAh: Int? = null,         // the design capacity, if known
    val health: Int = BatteryManager.BATTERY_HEALTH_UNKNOWN,
    val currentMinMA: Double? = null,   // this session's extremes
    val currentMaxMA: Double? = null,
) {
    val powerW: Double? get() =
        if (voltageV != null && currentA != null) voltageV * currentA else null
}

/** The samples the chart draws, kept in memory only. */
class SampleBuffer(val capacity: Int) {
    private val time = LongArray(capacity)
    private val data: Map<String, FloatArray> =
        METRIC_KEYS.associateWith { FloatArray(capacity) }
    private var next = 0        // where the next sample goes
    var size = 0                // how many are held (grows to `capacity`)
        private set

    /** 采集 off: the curve goes with it -- a frozen picture is still a record
     *  nobody asked to keep. */
    fun clear() {
        next = 0
        size = 0
    }

    fun add(t: Long, values: Map<String, Double?>) {
        time[next] = t
        for ((key, array) in data) {
            val v = values[key]
            array[next] = if (v == null) Float.NaN else v.toFloat()
        }
        next = (next + 1) % capacity
        if (size < capacity) size++
    }

    // logical index: 0 is the oldest sample held
    private fun physical(i: Int) = (next - size + i + capacity) % capacity

    fun timeAt(i: Int): Long = time[physical(i)]

    fun valueAt(key: String, i: Int): Float = data.getValue(key)[physical(i)]

    /** First logical index whose timestamp is at or after `cutoff`. */
    fun firstVisibleFrom(cutoff: Long): Int {
        var lo = 0
        var hi = size
        while (lo < hi) {
            val mid = (lo + hi) / 2
            if (timeAt(mid) < cutoff) lo = mid + 1 else hi = mid
        }
        return lo
    }
}

/** Reads one snapshot from BatteryManager / the sticky battery broadcast. */
class BatteryReader(context: Context) {
    private val ctx = context.applicationContext
    private val manager =
        ctx.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
    private val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
    private val designUAh: Int? = designCapacityUAh(ctx)

    // The current comes from BATTERY_PROPERTY_CURRENT_NOW -- which is the only
    // reading that carries the current's sign -- with its unit decided by the
    // charge counter.  Android promises µA, but a vendor's health HAL may
    // answer in mA (this Huawei does: a 1.6 A charge reads as 1600, and 0.3 A
    // of discharge as -297), and nothing in the reading itself says which.  The
    // counter's *magnitude* does: its deltas are µAh on every device, and its
    // own sign is not to be trusted at all (this phone's counter only ever
    // counts up, whether the battery is charging or discharging).  So the slope
    // decides the scale, the HAL reading is what is shown, and the decision is
    // remembered -- the counter stops moving when the battery is full, but the
    // unit a phone answers in does not change.
    private class CounterSample(val at: Long, val uah: Int)

    private val history = ArrayDeque<CounterSample>()
    private var estimateA: Double? = null
    private var perMilli: Boolean? = null

    private companion object {
        const val SPAN_MS = 10000L    // how far back the slope reaches
        const val MIN_SPAN_MS = 3000L // ... and the least it will settle for
        const val KEEP_MS = 20000L    // samples older than this are dropped
        const val MIN_SLOPE_A = 0.03  // below this the slope decides nothing
        const val MAX_SLOPE_A = 20.0  // above this it is a gauge reset, not a current
    }

    private fun prop(id: Int): Int? =
        manager.getIntProperty(id).takeIf { it != Int.MIN_VALUE }

    /** The current in amperes, from the charge counter's slope. */
    private fun counterCurrent(counter: Int?, nowMs: Long): Double? {
        if (counter == null) return null
        history.addLast(CounterSample(nowMs, counter))
        while (history.size > 2 && nowMs - history.first().at > KEEP_MS) {
            history.removeFirst()
        }
        val newest = history.last()
        // the sample closest to SPAN_MS back, so the window stays roughly fixed
        var reference: CounterSample? = null
        for (sample in history) {
            if (newest.at - sample.at >= SPAN_MS) reference = sample else break
        }
        if (reference == null && newest.at - history.first().at >= MIN_SPAN_MS) {
            reference = history.first()
        }
        if (reference == null) return estimateA
        val dt = (newest.at - reference.at) / 1000.0
        if (dt <= 0.0) return estimateA
        val ah = (newest.uah - reference.uah) / 1_000_000.0
        val amps = ah / (dt / 3600.0)
        if (abs(amps) > MAX_SLOPE_A) {
            // the counter was reset (a full charge does it): the jump is not a
            // current, so start the window again rather than believe it
            history.clear()
            history.addLast(newest)
            return null
        }
        estimateA = amps
        return estimateA
    }

    /**
     * The current in amperes: the HAL's own reading -- which carries the sign
     * -- in the unit the counter says it is in, with the counter's own slope as
     * the fallback when there is no reading at all.
     */
    private fun currentA(reported: Int?, slope: Double?): Double? {
        if (reported == null) return slope
        // A full, idle phone often answers CURRENT_NOW with exactly 0 while the
        // coulomb counter is still falling.  Zero is a real reading for a phone
        // that is doing nothing, but not when the counter shows a drain: use
        // the counter's slope instead of printing 0 and freezing the chart.
        if (reported == 0 && slope != null && abs(slope) > MIN_SLOPE_A) return slope
        val magnitude = slope?.let { abs(it) } ?: 0.0
        if (magnitude > MIN_SLOPE_A) {
            val micro = abs(reported) / 1_000_000.0
            val milli = abs(reported) / 1_000.0
            perMilli = abs(milli - magnitude) <= abs(micro - magnitude)
        }
        return reported / if (perMilli == true) 1_000.0 else 1_000_000.0
    }

    fun read(): Snapshot {
        val nowMs = SystemClock.elapsedRealtime()
        // the sticky intent is the same data the system UI shows
        val intent = try {
            ctx.registerReceiver(null, filter)
        } catch (t: Throwable) {
            null
        }
        fun extra(key: String, fallback: Int) =
            intent?.getIntExtra(key, fallback) ?: fallback

        val level = extra(BatteryManager.EXTRA_LEVEL, -1)
        val levelScale = extra(BatteryManager.EXTRA_SCALE, 100)
        val capacity = if (level >= 0 && levelScale > 0)
            level * 100 / levelScale
        else prop(BatteryManager.BATTERY_PROPERTY_CAPACITY)

        val mv = extra(BatteryManager.EXTRA_VOLTAGE, -1)
        val deciC = extra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE)
        val status = extra(BatteryManager.EXTRA_STATUS, -1)
        val plugged = extra(BatteryManager.EXTRA_PLUGGED, 0)
        // the HAL's own current: the one reading that carries its sign.  Some
        // machines only answer with the averaged value, a few answer with
        // neither, and the unit is whatever the vendor chose (see currentA)
        val reported = prop(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW)
            ?: prop(BatteryManager.BATTERY_PROPERTY_CURRENT_AVERAGE)
        val counter = prop(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER)
        val slope = counterCurrent(counter, nowMs)

        return Snapshot(
            capacity = capacity,
            voltageV = if (mv > 0) mv / 1000.0 else null,
            currentA = currentA(reported, slope),
            tempC = if (deciC != Int.MIN_VALUE) deciC / 10.0 else null,
            charging = status == BatteryManager.BATTERY_STATUS_CHARGING,
            plugged = plugged != 0,
            plugType = plugged,
            chargeCounterUAh = counter,
            designUAh = designUAh,
            health = extra(BatteryManager.EXTRA_HEALTH,
                           BatteryManager.BATTERY_HEALTH_UNKNOWN),
        )
    }
}

/**
 * The design capacity the gauge knows and Android does not publish.
 *
 * PowerProfile.getAveragePower("battery.capacity") is a hidden API: reflection
 * is the only way in, and whether the platform allows it depends on the
 * version and on what the app targets.  It is tried once, and "not available"
 * is a perfectly fine answer.
 */
private fun designCapacityUAh(context: Context): Int? = try {
    val cls = Class.forName("com.android.internal.os.PowerProfile")
    val profile = cls.getConstructor(Context::class.java).newInstance(context)
    val mah = cls.getMethod("getAveragePower", String::class.java)
        .invoke(profile, "battery.capacity") as Double
    if (mah > 0) (mah * 1000).toInt() else null
} catch (t: Throwable) {
    null
}

/** The charger type, as Android reports it (the Linux app reads SDP/DCP/CDP). */
fun plugTypeLabel(type: Int): String? = when (type) {
    BatteryManager.BATTERY_PLUGGED_AC -> "AC"
    BatteryManager.BATTERY_PLUGGED_USB -> "USB"
    BatteryManager.BATTERY_PLUGGED_WIRELESS -> tr("无线")
    BatteryManager.BATTERY_PLUGGED_DOCK -> "Dock"
    else -> null
}

/**
 * Samples the battery twice a second and keeps the last 48 hours.
 *
 * The loop lives in the process rather than in the UI, so the chart keeps
 * filling while the screen is off (until Android reclaims the process) -- an
 * always-plugged-in phone is watched for hours at a time, which is exactly
 * when nobody is looking at the screen.
 */
object Monitor {
    /** how often the panel reads, whatever the chart is set to */
    const val SAMPLE_MS = 500L

    /** how often the rules alone read: the daemon's 3 s on postmarketOS */
    const val RULES_MS = 3000L

    /** samples kept for the longest window (48 h at 2 Hz), plus a little slack */
    val MAX_SAMPLES = (48 * 3600 * 1000L / SAMPLE_MS + 16).toInt()

    /**
     * How often a sample is stored for the chart, in milliseconds.
     *
     * Two clocks, on purpose: the panel keeps its 500 ms readout (it is a live
     * number), while the history is written at this interval.  A slower
     * interval therefore costs the curve its detail and buys the buffer reach.
     */
    @Volatile
    var intervalMs: Long = SAMPLE_MS

    /**
     * 采集: the chart records only while this is true.
     *
     * Only the chart: the same pass still publishes the snapshot the status
     * table and the rules read, so turning 采集 off pauses the curve and
     * nothing else.  [storedAt] is not advanced while it is off, so the first
     * sample after switching on is due at once.
     */
    @Volatile
    var recording: Boolean = false

    val buffer = SampleBuffer(MAX_SAMPLES)

    private val _state = MutableStateFlow(Snapshot())
    val state: StateFlow<Snapshot> = _state

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var job: Job? = null

    /** How often the reader wakes: 500 ms for a page, 3 s for the rules. */
    @Volatile
    private var readMs: Long = SAMPLE_MS

    /**
     * The next read stores a chart sample even if [intervalMs] has not elapsed
     * since the last one.  Set when the interval or the switch moves, so a new
     * setting shows a point at once instead of looking frozen for up to the
     * old (or the new) interval.
     */
    @Volatile
    private var storeDue = true

    /**
     * One reader at the pace the caller needs.
     *
     * [intervalMs] is the chart's own clock and never changes how often the
     * battery is read: a 0.01 s setting cannot make a phone read 100 times a
     * second, and a 20 s setting must not freeze the live numbers.  When only
     * the notification service is looking, [RULES_MS] is the pace; when
     * nothing is looking, [stop] turns the reader off altogether.
     */
    fun start(context: Context, everyMs: Long = SAMPLE_MS) {
        val ms = everyMs.coerceAtLeast(10L)
        if (job?.isActive == true && readMs == ms) return
        job?.cancel()
        readMs = ms
        val reader = BatteryReader(context)
        job = scope.launch {
            // signed current extremes, reset every time the reader restarts
            var minMA: Double? = null
            var maxMA: Double? = null
            var seq = 0L
            var storedAt = 0L
            var publishedAt = 0L
            while (isActive) {
                val now = SystemClock.elapsedRealtime()
                // the sleep record rides on the same pass: the wall clock
                // against uptime, which stands still while the system dozes
                Sleeps.tick(System.currentTimeMillis(), SystemClock.uptimeMillis())
                val raw = reader.read()
                val ma = raw.currentA?.let { it * 1000.0 }
                if (ma != null) {
                    minMA = minMA?.let { min(it, ma) } ?: ma
                    maxMA = maxMA?.let { max(it, ma) } ?: ma
                }
                val snapshot = raw.copy(
                    seq = ++seq,
                    currentMinMA = minMA,
                    currentMaxMA = maxMA,
                )
                // the chart's clock: one stored sample per interval, whatever
                // the reader itself is doing (the chart may read faster).
                // storeDue forces one now when the interval or the switch moved
                val due = storeDue || now - storedAt >= intervalMs
                if (due && recording) {
                    storeDue = false
                    storedAt = now
                    buffer.add(
                        now,
                        mapOf(
                            "voltage_v" to snapshot.voltageV,
                            "current_mA" to ma,
                            // power is plotted as a magnitude: it tracks the
                            // current's shape almost exactly, so keeping its
                            // sign on top of the current's would just overlap
                            "power_w" to snapshot.powerW?.let { abs(it) },
                            "temp_c" to snapshot.tempC,
                            "capacity" to snapshot.capacity?.toDouble(),
                        ),
                    )
                }
                // the page's clock: 500 ms however fast the chart is sampling,
                // so the numbers (and the drawing) look steady
                if (now - publishedAt >= SAMPLE_MS) {
                    publishedAt = now
                    _state.value = snapshot
                }
                delay(readMs)
            }
        }
    }

    /** Nothing needs a reading: stop the reader rather than idle with it. */
    fun stop() {
        job?.cancel()
        job = null
    }

    /** The chart's setting moved: store the next sample at once. */
    fun resetStore() {
        storeDue = true
    }
}

/**
 * Which of the three readers is on.
 *
 * 实时采集 with the page in front: 500 ms, for the numbers and the chart.
 * The notification service alone: 3 s, for the rules.  Neither: nothing at
 * all -- no timer, no battery read, no wake-up.
 */
object Sampling {
    /** Whether a page is on screen; the activity sets it in onStart/onStop. */
    @Volatile
    var visible: Boolean = false

    fun apply(context: Context, prefs: Prefs) {
        val chartMs = prefs.sampleMs.toLong()
        if (Monitor.intervalMs != chartMs) {
            Monitor.intervalMs = chartMs
            Monitor.resetStore()
        }
        val live = prefs.live && visible
        val chart = live && prefs.record
        // the chart rides on the live reader; the 3 s reader has no page
        if (chart && !Monitor.recording) Monitor.resetStore()
        Monitor.recording = chart
        when {
            // the chart may want samples faster than the page's 500 ms; the
            // page itself still repaints at 500
            live -> Monitor.start(
                context,
                if (chart) minOf(Monitor.SAMPLE_MS, prefs.sampleMs.toLong())
                else Monitor.SAMPLE_MS,
            )
            prefs.notify -> Monitor.start(context, Monitor.RULES_MS)
            else -> Monitor.stop()
        }
    }
}
