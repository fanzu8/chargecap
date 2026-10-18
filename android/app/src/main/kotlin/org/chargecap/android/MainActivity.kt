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

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// The app: the GTK app's single panel, on Android.
//
// What carried over: the whole status table, the live chart with its metric
// toggles and windows, the language switch, 禁止休眠 (now a wake lock) and the
// in-memory sample history.
// What could not: the charging control itself -- it needs root to write the
// charger's sysfs, which the GTK app gets from its daemon (see android/README.md).

class MainActivity : ComponentActivity() {
    private lateinit var prefs: Prefs
    private lateinit var inhibitor: SleepInhibitor

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        Strings.lang = prefs.lang
        inhibitor = SleepInhibitor(this)
        if (prefs.inhibitSleep) inhibitor.acquire()

        // Sampling lives in the process rather than in the UI, so the chart
        // keeps filling while the screen is off.
        Monitor.start(applicationContext)

        setContent { ChargecapApp(prefs, inhibitor) }
    }

    override fun onDestroy() {
        // the wake lock dies with the process anyway; releasing it here keeps
        // the switch from outliving the app that owns it
        if (isFinishing) inhibitor.release()
        super.onDestroy()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChargecapApp(prefs: Prefs, inhibitor: SleepInhibitor) {
    var lang by remember { mutableStateOf(prefs.lang) }
    var selected by remember {
        mutableStateOf(prefs.metrics.ifEmpty { DEFAULT_METRICS })
    }
    var windowSecs by remember { mutableStateOf(prefs.windowSecs) }
    var inhibit by remember { mutableStateOf(prefs.inhibitSleep) }
    val snapshot by Monitor.state.collectAsState()

    AppTheme(darkTheme = isSystemInDarkTheme()) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text(tr("电电")) },
                    actions = {
                        LanguageButton(lang) { picked ->
                            lang = picked
                            Strings.lang = picked
                            prefs.lang = picked
                        }
                    },
                )
            },
        ) { inset ->
            Column(
                Modifier
                    .padding(inset)
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 12.dp),
            ) {
                LimitsSection()

                SleepSection(inhibit) { on ->
                    inhibit = on
                    prefs.inhibitSleep = on
                    if (on) inhibitor.acquire() else inhibitor.release()
                }
                Spacer(Modifier.height(10.dp))

                StatusSection(snapshot)

                ChartSection(
                    buffer = Monitor.buffer,
                    selected = selected,
                    onToggle = { key ->
                        // keep METRICS order so the Y axes never jump around
                        selected = if (key in selected) selected - key
                        else METRIC_KEYS.filter { it in selected || it == key }
                        prefs.metrics = selected
                    },
                    windowSecs = windowSecs,
                    onWindow = { secs ->
                        windowSecs = secs
                        prefs.windowSecs = secs
                    },
                    seq = snapshot.seq,
                )
            }
        }
    }
}

/**
 * The language switch: a couple of characters, in the header bar.
 *
 * It picks between following the system and a language pushed by hand, exactly
 * like the GTK app -- except that here the whole UI simply recomposes instead
 * of being restarted.
 */
@Composable
private fun LanguageButton(current: Lang, onPick: (Lang) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        TextButton(onClick = { open = true }) {
            Text(
                if (Strings.effective == Lang.ZH) "中" else "EN",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            for ((value, label) in listOf(
                Lang.AUTO to tr("跟随系统"),
                Lang.ZH to "中文",
                Lang.EN to "English",
            )) {
                DropdownMenuItem(
                    text = {
                        Text(
                            (if (value == current) "✓ " else "   ") + label,
                            fontSize = 13.sp,
                        )
                    },
                    onClick = {
                        open = false
                        onPick(value)
                    },
                )
            }
        }
    }
}
