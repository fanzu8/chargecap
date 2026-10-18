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

    var inhibitSleep: Boolean
        get() = store.getBoolean("inhibit_sleep", false)
        set(value) = store.edit().putBoolean("inhibit_sleep", value).apply()
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
