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
import android.speech.tts.TextToSpeech
import java.util.Locale

/**
 * The voice half of a notification: what 语音 says out loud.
 *
 * One engine for the process, started with the app and shut down with it, so a
 * notification that arrives while the screen is off still has a voice.  The
 * engine's language follows the app's rather than the system's: the words are
 * the app's own (translated by [tr]), and a Chinese sentence read by an English
 * voice is not an improvement.  A phone with no engine for that language says
 * nothing at all, which is the honest answer.
 *
 * When it says a thing, and how often, is the reminder's business
 * (Notifications.kt): this is one sentence at a time, taking over from whatever
 * was still being said -- or queueing behind it, for the echo of the same one.
 */
object Voice {
    private var engine: TextToSpeech? = null
    private var ready = false

    /** A sentence asked for before the engine was up -- the first 试听. */
    private var waiting: String? = null

    /** Start the engine; safe to call again. */
    fun start(context: Context) {
        if (engine != null) return
        val app = context.applicationContext
        engine = TextToSpeech(app) { status ->
            ready = status == TextToSpeech.SUCCESS
            if (ready) waiting?.let { say(it) }
            waiting = null
        }
    }

    /** Stop whatever is still being said: 通知开关 went off, or the app is
     *  going away.  Nothing is left running. */
    fun stop() {
        // a sentence already handed over plays to its end unless it is told to
        // stop, and one waiting for the engine to come up would arrive after the
        // switch is off -- so both are dropped here
        engine?.stop()
        waiting = null
    }

    /**
     * Say one sentence, in the app's language.  [queue] asks the engine to
     * finish what it is already saying first -- a repeat of the same sentence
     * wants that; anything new, a 试听 or the next reminder, takes over.
     */
    fun say(text: String, queue: Boolean = false) {
        val engine = engine
        if (engine == null || !ready) {
            // asked for before the engine was up: say it once it is
            waiting = text
            return
        }
        engine.language = if (Strings.effective == Lang.ZH) {
            Locale.SIMPLIFIED_CHINESE
        } else {
            Locale.ENGLISH
        }
        engine.speak(
            text,
            if (queue) TextToSpeech.QUEUE_ADD else TextToSpeech.QUEUE_FLUSH,
            null,
            "chargecap",
        )
    }

    /** Let the engine go: the activity is going away, and so is the voice. */
    fun shutdown() {
        stop()
        engine?.shutdown()
        engine = null
        ready = false
        waiting = null
    }
}
