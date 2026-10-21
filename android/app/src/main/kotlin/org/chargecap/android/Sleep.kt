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

import android.os.SystemClock
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// The record of the system's own sleeps.
//
// It is deliberately not a notification and cannot be one: a sleeping system
// delivers nothing, and the moment it can deliver is the moment it woke.  What
// it can answer is the question 高级's 禁止休眠 promises with its switch -- did
// the system sleep or did it not -- and so the record lives one row under that
// switch, read off the clocks rather than off anything the system would tell.
//
// The layer cake is the one at the top of AppState.kt: Prefs remembers, the
// sampler's pass calls [Sleeps.tick] with its two clocks, and the page reads
// the states here as it reads any other.

/** One sleep: when it ended, and how long it lasted. */
data class Nap(val at: Long, val secs: Int)

object Sleeps {
    /** a stretch shorter than this is a blink, not a sleep */
    const val MIN_SECS = 60

    /** awake time shorter than this belongs to the stretch it interrupted, so
     *  a night of doze punctuated by alarm wakeups is one sleep, not a hundred */
    const val MERGE_SECS = 120

    /** the sleeps a tap on the row can still list */
    const val KEPT = 10

    /** 禁止休眠's last turn-on, the moment the count starts from; 0 is never */
    var anchor by mutableStateOf(0L)
        private set

    var count by mutableStateOf(0)
        private set

    /** the last [KEPT] sleeps, newest first */
    var naps by mutableStateOf(emptyList<Nap>())
        private set

    private lateinit var store: Prefs

    private var lastWall = 0L
    private var lastUptime = 0L
    private var stretchStart = 0L    // wall clock of the stretch's first sample
    private var stretchLast = 0L     // ... and of its last sleeping one
    private var stretchMs = 0L
    private var lastPersist = 0L

    /**
     * Loaded once, with the process: the record survives a kill but not a
     * boot, and a boot is the one way to tell -- elapsedRealtime runs from
     * the boot, so a smaller one than the record's own is a reboot, and a
     * reboot clears the count.
     */
    fun start(prefs: Prefs) {
        store = prefs
        anchor = store.sleepAnchor
        count = store.sleepCount
        naps = store.sleepNaps.split(";").filter { it.isNotEmpty() }.map { part ->
            val (at, secs) = part.split(":").map { it.toLong() }
            Nap(at, secs.toInt())
        }
        if (SystemClock.elapsedRealtime() < store.sleepElapsed) {
            count = 0
            naps = emptyList()
            persist()
        }
    }

    /**
     * One sample's clocks: the wall clock, and uptimeMillis -- the one that
     * stands still while the CPU is suspended.  Its shortage against the wall
     * clock is how long the system slept inside this one interval, however
     * fast or slow the sampler was running.
     */
    fun tick(wall: Long, uptime: Long) = synchronized(this) {
        if (lastWall != 0L) {
            val slept = wall - lastWall - (uptime - lastUptime)
            if (slept > 0) {
                // a stretch begins with the sample before the first sleeping
                // one: that is when the system was last seen awake
                if (stretchStart == 0L) stretchStart = lastWall
                stretchMs += slept
                stretchLast = wall
            } else if (stretchStart != 0L && wall - stretchLast > MERGE_SECS * 1000) {
                close()
            }
        }
        lastWall = wall
        lastUptime = uptime
        // the clocks are cheap, the write is not: every ten seconds is often
        // enough for a record whose smallest event is a minute long
        if (wall - lastPersist > 10_000) {
            lastPersist = wall
            persist()
        }
    }

    /**
     * 禁止休眠 is on: the record starts over from this moment, because the
     * count is the last turn-on's, not the phone's lifetime.  It has nothing to
     * do with the notifications: what it answers is whether the switch that
     * promised no sleep held.
     */
    fun restart() = synchronized(this) {
        anchor = System.currentTimeMillis()
        count = 0
        naps = emptyList()
        stretchStart = 0
        stretchLast = 0
        stretchMs = 0
        persist()
    }

    /** The stretch is over: long enough counts, short enough never happened. */
    private fun close() {
        if (anchor != 0L && stretchMs >= MIN_SECS * 1000) {
            count += 1
            naps = (listOf(Nap(stretchLast, (stretchMs / 1000).toInt())) + naps).take(KEPT)
            persist()
        }
        stretchStart = 0
        stretchLast = 0
        stretchMs = 0
    }

    private fun persist() {
        if (!::store.isInitialized) return
        store.sleepAnchor = anchor
        store.sleepCount = count
        store.sleepNaps = naps.joinToString(";") { "${it.at}:${it.secs}" }
        store.sleepElapsed = SystemClock.elapsedRealtime()
    }

    /** The row's second line: the anchor, and the last sleep, or why there is
     *  none.  Never turned on has no anchor and so nothing to count. */
    fun line(): String {
        if (anchor == 0L) return tr("还没开启禁止休眠")
        val since = tr("自 %s 起").format(clock(anchor))
        val last = naps.firstOrNull()
            ?: return "$since · " + tr("还没有休眠")
        return "$since · " + tr("最近 %s，%s").format(clock(last.at), lasted(last.secs))
    }
}

/** How long a sleep lasted, in words. */
private fun lasted(secs: Int): String =
    if (secs < 3600) tr("睡了 %d 分钟").format(secs / 60)
    else tr("睡了 %d 小时 %d 分钟").format(secs / 3600, secs % 3600 / 60)

/** A nap's line in the history card. */
internal fun Nap.line(): String = clock(at) + " · " + lasted(secs)

/** Today's sleep says the time of day; an older one carries the date. */
private fun clock(ms: Long): String {
    val day = SimpleDateFormat("yyyyMMdd", Locale.getDefault())
    val sameDay = day.format(Date(ms)) == day.format(Date())
    return SimpleDateFormat(
        if (sameDay) "HH:mm" else "MM-dd HH:mm", Locale.getDefault(),
    ).format(Date(ms))
}
