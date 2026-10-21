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

// The rules: what the app does with the readings rather than draws.
//
// Kept off the pages on purpose -- this runs whether or not anybody is looking
// at a screen -- and free of Android on purpose too: a rule is a comparison, and
// Notifications.kt is what turns the answer into a banner and a voice.  The
// layer cake is the one at the top of AppState.kt; this is the top of it, next
// to Prefs, Monitor and AppState.

/**
 * One notification as it is set right now: what it watches, where its line is,
 * and how it arrives.
 *
 * A [Notification] is the definition everybody shares; a Rule is that definition
 * with this app's answers, handed over by AppState whenever a switch moves.
 */
data class Rule(
    val n: Notification,
    val at: Int,
    /**
     * The three answers as they stood when the rules were armed -- kind,
     * count and gap in one value.  The reminder re-reads them from the live
     * rules at every repeat, so a chip moved mid-count takes effect there.
     */
    val answer: Answer,
) {
    val kind: NotifyKind get() = answer.kind
    /** how many times it repeats, 0 for the endless one where there is one */
    val times: Int get() = answer.times
    /** how long it waits between those repeats, in seconds */
    val gapSecs: Int get() = answer.gap
    /** How far past its line a sample is -- negative means it has not reached
     *  it.  The reading stays in the notification's own unit. */
    fun past(s: Snapshot): Float = n.distance(s, at)

    /** Past the line: the one moment that is worth saying. */
    fun crossed(s: Snapshot): Boolean = past(s) >= 0f

    /** Back by this notification's own step: far enough that the next crossing
     *  is news again, and a value sitting on the line is not. */
    fun clear(s: Snapshot): Boolean = past(s) <= -n.step

    /** What it says, in one sentence, to the banner and to the voice alike. */
    fun says(): String = n.says(at)
}

/**
 * The rules as they stand, and which of them have already spoken.
 *
 * One sample in, a decision out: a rule fires when its line is crossed and is
 * quiet until the reading comes back clear, so a battery sitting on 45.0 °C says
 * its piece once rather than twice a second.
 *
 * [arm] is written by AppState -- the only thing that knows what is switched on
 * -- and read once per sample here.  A new set of rules starts by looking at
 * where the readings are, not by saying so: turning a switch on, or opening the
 * app under one that was already on, is not a crossing.
 */
object NotifyRules {
    @Volatile
    private var current: List<Rule> = emptyList()

    /** The rules as armed; the pages do not read this, the notifier does. */
    val rules: List<Rule>
        get() = current

    private val spoken = mutableSetOf<String>()

    /**
     * The next sample only learns: a set of rules that has just been handed
     * over takes what is already past a line as read.  Turning 通知开关 (or one
     * notification) on is not itself news, so the first sample after arming
     * writes down what is true now and says nothing; only a crossing after
     * that fires.  The same holds when the app opens under a switch that was
     * already on.
     */
    private var seeding = true

    /**
     * Hand over what is set now, as a new set of rules: a switch has moved, so
     * the memory of who has spoken goes with it, and the next sample is the
     * one that learns -- silently -- where the readings already are.
     */
    fun arm(now: List<Rule>) = synchronized(this) {
        spoken.clear()
        seeding = true
        current = now
    }

    /**
     * The same rules at new numbers: a stepper moved a line, rather than
     * changing which lines are watched.  What has been said stays said -- eight
     * steps of a threshold must not be eight banners.
     */
    fun retune(now: List<Rule>) = synchronized(this) {
        current = now
    }

    /** One sample: call [fire] for each rule that has just crossed its line. */
    fun sample(s: Snapshot, fire: (Rule) -> Unit) {
        val fired = synchronized(this) {
            val out = mutableListOf<Rule>()
            if (seeding) {
                // the first look after a switch moved: whatever is already
                // past its line is taken as said, and this pass says nothing
                seeding = false
                for (rule in rules) {
                    if (rule.crossed(s)) spoken.add(rule.n.key)
                }
                return@synchronized out
            }
            for (rule in rules) {
                when {
                    rule.crossed(s) && spoken.add(rule.n.key) -> out.add(rule)
                    !rule.crossed(s) && rule.clear(s) -> spoken.remove(rule.n.key)
                }
            }
            out
        }
        // speaking and posting are slow, and the lock is not theirs to hold
        fired.forEach(fire)
    }
}
