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
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// The app: the app opens on 通知 (its own page, Android only for now), the
// panel the GTK app draws is the page beside it (高级), and the gear holds 设置
// -- the two screens that belong to the system rather than to either page.
//
// This file is the frame and nothing else: which page is showing, the header,
// and the two buttons in it that are not pages.  The pages themselves are in
// Pages.kt, what they read and write in AppState.kt, and the rows they draw
// with in Panel.kt.
//
// What carried over: the whole status table, the live chart with its metric
// toggles and windows, the language switch, 禁止休眠 (now a wake lock) and the
// in-memory sample history.
// What could not: the charging control itself -- it needs root to write the
// charger's sysfs, which the GTK app gets from its daemon (see android/README.md).
// What Android has first: 通知, the page of notifications and their thresholds.

class MainActivity : ComponentActivity() {
    private lateinit var prefs: Prefs
    private lateinit var inhibitor: SleepInhibitor

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)
        Strings.lang = prefs.lang
        inhibitor = SleepInhibitor(this)
        if (prefs.inhibitSleep) inhibitor.acquire()

        // 通知横幅与声音 hang off the channel, so it has to exist before the
        // system's 通知 page has anything to show (see Notifications.kt)
        createNotificationChannel(this)

        // the sleep record loads with the process, and a reboot clears it
        Sleeps.start(prefs)

        // Sampling lives in the process rather than in the UI, so the chart
        // keeps filling while the screen is off -- when 采集 is on: the switch
        // is read here, once, before the sampler starts.
        Monitor.recording = prefs.record
        Monitor.start(applicationContext, prefs.sampleMs.toLong())

        // ... and the rules ride on those same samples, with the process rather
        // than with a page, so a notification arrives with the screen off too
        Voice.start(this)
        startNotifier(this)

        setContent { ChargecapApp(prefs, inhibitor) }
    }

    override fun onDestroy() {
        // the wake lock dies with the process anyway; releasing it here keeps
        // the switch from outliving the app that owns it.  The voice engine is
        // left alone: the monitor service may still have a reminder to say.
        if (isFinishing) inhibitor.release()
        super.onDestroy()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChargecapApp(prefs: Prefs, inhibitor: SleepInhibitor) {
    // everything the pages read and write; built once, for the life of the UI
    val state = remember { AppState(prefs, inhibitor) }

    // 通知开关 on: keep the rules alive with the screen off.  A foreground
    // service is the only thing Android leaves running for that; the small
    // ongoing notification is its price, and vendor autostart alone does not
    // buy it.  Off stops the service and its notification too.
    val context = LocalContext.current
    LaunchedEffect(state.notify) {
        if (state.notify) MonitorService.start(context)
        else MonitorService.stop(context)
    }

    // the phone's own back: 设置 to the page that opened it, 高级 to 通知 --
    // and from 通知 it leaves the app, as it should
    BackHandler(enabled = state.page != Page.NOTIFY) { state.leave() }

    AppTheme(theme = state.theme) {
        when (state.page) {
            // 通知 and 高级 are the app's two functions, side by side in the
            // header; only what sits under it changes
            Page.NOTIFY, Page.OTHER -> Scaffold(
                topBar = { AppHeader(state) },
            ) { inset ->
                if (state.page == Page.NOTIFY) NotifyPage(state, inset)
                else PanelPage(state, inset)
            }

            // 设置: what is neither page's own, behind the gear at the far right
            Page.SETTINGS -> Scaffold(
                topBar = {
                    TopAppBar(
                        title = { Text(tr("设置")) },
                        navigationIcon = {
                            TextButton(onClick = { state.leave() }) {
                                Text(
                                    "‹ " + tr("返回"),
                                    fontSize = 12.sp,
                                    color = MaterialTheme.colorScheme.onSurface,
                                )
                            }
                        },
                    )
                },
            ) { inset -> SettingsPage(inset) }
        }
    }
}

/**
 * The header the two pages share: 通知 and 高级 in front -- they are what the
 * app is -- then the theme and the language as a pair, then 设置 alone on the
 * far right.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppHeader(state: AppState) {
    TopAppBar(
        title = { PageTabs(state) },
        actions = {
            BackgroundButton(state.theme, state::setTheme)
            LanguageButton(state.lang, state::setLang)
            SettingsButton { state.show(Page.SETTINGS) }
        },
    )
}

/**
 * 通知 and 高级, where a title would otherwise be: the page you are on is the
 * one written solid *and* sitting on its own background, so which of the two is
 * showing needs no reading -- the other is a door to it.
 */
@Composable
private fun PageTabs(state: AppState) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        for (target in listOf(Page.NOTIFY, Page.OTHER)) {
            val here = target == state.page
            Text(
                if (target == Page.NOTIFY) tr("通知") else tr("高级"),
                fontSize = 17.sp,
                fontWeight = if (here) FontWeight.Bold else FontWeight.Normal,
                color = if (here) MaterialTheme.colorScheme.onPrimaryContainer
                        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f),
                modifier = Modifier
                    .clip(RoundedCornerShape(10.dp))
                    .background(
                        if (here) MaterialTheme.colorScheme.primaryContainer
                        else Color.Transparent)
                    .clickable { state.show(target) }
                    .padding(horizontal = 10.dp, vertical = 6.dp),
            )
            Spacer(Modifier.width(4.dp))
        }
    }
}

/**
 * The gear, alone at the far right: 设置, one page in.
 *
 * A gear rather than a word because the two pages beside it are the words --
 * what is in here is not a page of the app, it is the way out to the system's.
 */
@Composable
private fun SettingsButton(onClick: () -> Unit) {
    HeaderButton("\u2699", fontSize = 22.sp, onClick = onClick)
}

/**
 * A header button: a couple of characters, or the gear, sized to what is in it.
 *
 * Not a TextButton, whose minimum width is what held the theme and the language
 * apart -- they are meant to read as one pair.
 */
@Composable
private fun HeaderButton(
    label: String,
    fontSize: TextUnit = 15.sp,
    onClick: () -> Unit,
) {
    Text(
        label,
        fontSize = fontSize,
        color = MaterialTheme.colorScheme.onSurface,
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 10.dp),
    )
}

/**
 * The background switch: the scheme in a couple of characters, in the header
 * bar, left of the language one.
 *
 * Dark is the default (the GTK app's too), so a fresh install opens dark and
 * the button is there to go lighter, or to follow the system.
 */
@Composable
private fun BackgroundButton(current: Theme, onPick: (Theme) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val zh = Strings.effective == Lang.ZH
    Box {
        HeaderButton(
            when (current) {
                Theme.DARK -> if (zh) "暗" else "Dark"
                Theme.LIGHT -> if (zh) "亮" else "Light"
                Theme.AUTO -> if (zh) "随" else "Auto"
            },
        ) { open = true }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            MenuTitle(tr("背景"))
            for ((value, label) in listOf(
                Theme.DARK to tr("暗色"),
                Theme.LIGHT to tr("亮色"),
                Theme.AUTO to tr("跟随系统"),
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

/**
 * The language switch: a couple of characters, in the header bar, right of the
 * background one.
 *
 * It picks between following the system and a language pushed by hand, exactly
 * like the GTK app -- except that here the whole UI simply recomposes instead
 * of being restarted.
 */
@Composable
private fun LanguageButton(current: Lang, onPick: (Lang) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        // the button says what you would get, not what you have: a Chinese
        // page offers "EN", an English one 中
        HeaderButton(if (Strings.effective == Lang.ZH) "EN" else "中") { open = true }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            MenuTitle(tr("语言"))
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
