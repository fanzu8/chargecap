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
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.withLink
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// The three screens, and nothing but the screens: each one takes the state,
// reads what it shows off it, writes back through its setters, and hands the
// values to the rows in Panel.kt (the vocabulary both pages draw with).  The
// reading of the battery, and the remembering of anything, happen elsewhere --
// see the layers at the top of AppState.kt.

/**
 * 通知: the page the app opens on.
 *
 * 通知开关 alone, because it is the page's one gate, and then the
 * notifications in two groups: the two about the battery itself, which a fresh
 * install has on, and the rest -- its temperature, its current -- which are
 * asked for rather than assumed.  Every row is the notification's own: its
 * switch, its number and its way of arriving.
 */
@Composable
fun NotifyPage(state: AppState, inset: PaddingValues) {
    val context = LocalContext.current

    // what the system has switched off, read the moment the master goes on:
    // empty means there is nothing to say
    var missing by remember { mutableStateOf(emptyList<Limit>()) }

    // 通知横幅 is a runtime permission from Android 13; below that the
    // manifest's is granted at install time.  Either way the answer comes back
    // here and only then is the rest of the system asked -- a permission dialog
    // still open would otherwise read as "notifications off"
    val askBanner = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()) { missing = limits(context) }

    PageColumn(inset) {
        // the gate on its own: a row that is a page-wide answer, not one
        // notification's
        Section {
            SwitchRow(tr("通知开关"), checked = state.notify, enabled = true,
                      master = true) { on ->
                state.setNotify(on)
                when {
                    // off is quiet, and a reminder from a switch that is off is
                    // the last thing the page should say
                    !on -> missing = emptyList()
                    Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU ->
                        askBanner.launch(Manifest.permission.POST_NOTIFICATIONS)
                    else -> missing = limits(context)
                }
            }
        }
        // the groups, in the order the page reads: the charge itself, the plug
        // and the charging state, then one group per kind of reading -- a
        // temperature and a voltage are not the same subject
        for (group in GROUPS) NotifyGroup(state, group.title(), group.keys)
    }

    // the switch is on but the system would swallow what it produces: the two
    // rows in 设置 are where that is fixed
    if (missing.isNotEmpty()) {
        val s = scale()
        AlertDialog(
            onDismissRequest = { missing = emptyList() },
            title = {
                Text(
                    tr("提醒可能收不到"),
                    fontSize = s.heading.sp,
                    fontWeight = FontWeight.Bold,
                )
            },
            text = {
                Column {
                    for (limit in missing) {
                        Text(
                            limit.line(),
                            fontSize = s.small.sp,
                            modifier = Modifier.padding(bottom = 4.dp),
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    missing = emptyList()
                    state.show(Page.SETTINGS)
                }) { Text(tr("去设置")) }
            },
            dismissButton = {
                TextButton(onClick = { missing = emptyList() }) {
                    Text(tr("知道了"))
                }
            },
        )
    }
}

/** What a missing limit reads as in the dialog. */
private fun Limit.line(): String = when (this) {
    Limit.NOTIFICATIONS -> tr("系统通知没有打开，横幅和声音都不会出现")
    Limit.BACKGROUND -> tr("系统可能在后台关掉它：自启动与省电白名单")
}

/**
 * The groups the page is read in: 充电完成 and 电量过低 are what the battery
 * itself says; then the plug and the charging state; then one group per kind of
 * reading.  The keys are the table's, so a group never reorders it -- one loop
 * over NOTIFICATIONS, filtered, rather than a second list to keep in step.
 */
@Composable
private fun NotifyGroup(state: AppState, title: String, keys: Set<String>) {
    val rows = NOTIFICATIONS.filter { it.key in keys }
    Section(title) {
        rows.forEachIndexed { index, n ->
            if (index > 0) RowDivider()
            NotifyRow(state, n)
        }
    }
}

/**
 * One heading and the notifications under it.  The title is a lambda for the
 * same reason a notification's is: the word is translated while the page is
 * being built, not once at class load.
 */
private data class Group(val title: () -> String, val keys: Set<String>)

/**
 * The groups, in the order the page shows them.  A temperature, a voltage, a
 * current and a power are four different readings, so each gets its own group
 * rather than one pile called 其他; the state four sit between the battery's own
 * charge and the readings, which is where a plug is noticed from.
 */
private val GROUPS = listOf(
    Group({ tr("基础功能") }, setOf("done", "low")),
    Group({ tr("电源") }, setOf("plugged", "unplugged")),
    Group({ tr("充电") }, setOf("charging", "idle")),
    Group({ tr("温度") }, setOf("hot", "cold")),
    Group({ tr("电压") }, setOf("vhigh", "vlow")),
    Group({ tr("电流") }, setOf("iin", "drain")),
    Group({ tr("功率") }, setOf("power")),
)

/**
 * 高级: the panel the GTK app draws.
 *
 * The only page with something live on it, and even here nothing is collected:
 * the monitor publishes, the chart fills whether or not anybody is looking, and
 * this reads what is already there.
 */
@Composable
fun PanelPage(state: AppState, inset: PaddingValues) {
    // keep the State itself: the chart reads it inside its draw scope, so a
    // new reading invalidates the canvas at 500 ms even when no stored sample
    // has arrived yet
    val snapshotState = state.samples.collectAsState()
    val snapshot = snapshotState.value

    PageColumn(inset) {
        LimitsSection()

        SleepSection(state.inhibit, state::setInhibit)

        // the table and the chart are one card, under one 实时采集 switch
        LiveSection(state, snapshot, snapshotState)
    }
}

/**
 * 设置: the two rows that leave the app, because the screens they open belong
 * to the system rather than to either page.
 */
@Composable
fun SettingsPage(inset: PaddingValues) {
    val context = LocalContext.current

    PageColumn(inset) {
        Section {
            Text(
                tr("各厂商的设置位置不一样，下面的按钮带你去找"),
                fontSize = scale().small.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                modifier = Modifier.padding(vertical = 6.dp),
            )
            RowDivider()
            LinkRow(tr("自启动"), tr("让 chargecap 开机后自己起来")) {
                openAutostartSettings(context)
            }
            RowDivider()
            LinkRow(tr("通知横幅与声音"), tr("在通知设置里放开横幅和声音")) {
                openNotificationSettings(context)
            }
            RowDivider()
            val battery = if (batteryExempt(context)) tr("已允许后台运行")
                          else tr("允许 chargecap 在后台继续运行")
            LinkRow(tr("电池优化"), battery) { openBatteryOptimization(context) }
            RowDivider()
            val exact = if (exactAlarms(context)) tr("已允许")
                        else tr("允许系统闹钟拉起监控")
            LinkRow(tr("精确闹钟"), exact) { openExactAlarm(context) }
            RowDivider()
            Text(
                tr("最近任务里锁定 chargecap；并在手机管家的应用启动管理中打开自启动、关联启动和后台活动"),
                fontSize = scale().small.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                modifier = Modifier.padding(vertical = 8.dp),
            )
        }

        // 关于: plain text, no card and no copy button.  It is a block of
        // selectable text like any other on the phone -- long-press and copy
        // what is wanted, the whole block included.
        Column(Modifier.padding(start = 4.dp, end = 4.dp, top = 22.dp)) {
            Text(
                tr("关于"),
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 6.dp),
            )
            SelectionContainer {
                Text(
                    aboutText(),
                    fontSize = scale().heading.sp,
                    color = MaterialTheme.colorScheme.onSurface,
                    lineHeight = (scale().heading * 1.6).sp,
                )
            }
        }
    }
}

/** 0.0.1 (a1b2c3d4-20261021): the version, its commit, and the day it was built. */
internal val buildLabel: String
    get() = "${BuildConfig.VERSION_NAME} (${BuildConfig.GIT_COMMIT}-${BuildConfig.BUILD_DATE})"

/**
 * A key and its colon: 版本： in Chinese, Version: in English.
 *
 * The colon follows the language rather than the label, because it belongs to
 * the sentence and not to the key: a full-width one in English reads as a
 * stray box, a narrow one in Chinese leaves the value hanging.
 */
private fun aboutKey(label: String): String =
    label + if (Strings.effective == Lang.ZH) "：" else ":"

/** 关于 as one block: four plain lines, the releases page a real link. */
@Composable
private fun aboutText() = buildAnnotatedString {
    append(aboutKey(tr("版本")) + "  " + buildLabel + "\n")
    append(aboutKey(tr("作者")) + "  fanzu8\n")
    append(aboutKey(tr("更新")) + "  ")
    withLink(LinkAnnotation.Url(RELEASES_URL)) {
        withStyle(SpanStyle(color = MaterialTheme.colorScheme.primary)) {
            append(RELEASES_URL)
        }
    }
    append("\n")
    append(aboutKey(tr("隐私")) + "  " + tr("不联网、不收集任何数据"))
}

/** The scrolling column every page sits in, with the insets the Scaffold gave. */
@Composable
private fun PageColumn(
    inset: PaddingValues,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        Modifier
            .padding(inset)
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 12.dp),
        content = content,
    )
}

/**
 * One notification: whether it fires, at what number, and how it arrives.
 *
 * The switch and the number share a row -- the title, the line in the middle,
 * the switch at the end -- because they answer the same question about the same
 * notification, and the 达 / 低于 / 高于 that used to sit beside the number only
 * said what the notification's name already says.
 */
@Composable
private fun NotifyRow(state: AppState, n: Notification) {
    // every row stays live, master switch or not: what is switched on, where its
    // line is and how it arrives are settings you can make beforehand, and the
    // switch at the top of the page is what decides whether any of them fires
    // 通知开关 is the page's gate: with it off every row under it dims and
    // stops taking input, and not one answer is changed -- switching it back on
    // finds the page exactly as it was left
    val live = state.notify
    if (n.numbered) {
        SwitchStepperRow(
            title = n.short(),
            checked = state.itemOn(n),
            value = state.at(n),
            unit = n.unit,
            step = n.step,
            enabled = live,
            onCheck = { state.setItem(n, it) },
            onChange = { state.setAt(n, it) },
        )
    } else {
        // a state has no line to draw, so it has no number to draw either:
        // the row is the name and the switch, and the answers stay under it
        SwitchRow(
            title = n.short(),
            checked = state.itemOn(n),
            enabled = live,
            onChange = { state.setItem(n, it) },
        )
    }
    // the row's three answers are one value: the chip hands the whole answer
    // back, changed in the one field it owns
    NotifyKindRow(
        n = n,
        answer = state.answerOf(n),
        enabled = live,
        onAnswer = { picked ->
            val was = state.answerOf(n)
            state.setAnswer(n, picked)
            // a voice chosen is a voice heard: picking one is its own 试听 --
            // but only where the kind itself moved (a count or a gap is not a
            // new way of arriving), and only with 通知开关 on.  Switched off the
            // page is silent, and setting something up is not a notification
            if (state.notify && picked.kind == NotifyKind.VOICE &&
                was.kind != picked.kind
            ) {
                Voice.say(n.says(state.at(n)))
            }
        },
    )
}

/**
 * 通知方式, 次数 and 间隔 on one row: the way it arrives, how many times it
 * does, and how long it waits between those times.
 *
 * All three are the whole notification's answers -- a banner repeats and a
 * voice repeats -- and the count's last chip is the notification's own: 电量过低
 * until the plug goes in, 充电完成 until the power goes off, so 温度过高 and
 * 温度过低 stop at 10次.
 *
 * 间隔 sits at the far end of the row, so it keeps its place on every
 * notification whatever width the count beside it happens to be.  It is always
 * drawn: at 1次 it reads 0, the gap of a single notification, and nothing can
 * change that -- a number with nothing between is still an answer.
 */
@Composable
private fun NotifyKindRow(
    n: Notification,
    /** the three answers as one value: the kind, the count and the gap */
    answer: Answer,
    /** 通知开关 off: drawn, dimmed, and opening nothing */
    enabled: Boolean,
    /** a chip picked one of them; the whole answer comes back, one field moved */
    onAnswer: (Answer) -> Unit,
) {
    val s = scale()
    // named here because they are read again and again below; the answer
    // itself stays one value, so a pick can never change two of them at once
    val kind = answer.kind
    val count = answer.times
    val gap = answer.gap
    // 通知方式's column is as wide as the widest chip it can draw, so 次数
    // starts at the same x on every row -- right after the chip, rather than
    // pushing it to the right edge or leaving a gap the width of the row
    val measurer = rememberTextMeasurer()
    val widestKind = remember(s, Strings.effective) {
        NotifyKind.entries.maxOf { k ->
            measurer.measure(
                notifyKindLabel(k) + " \u25be",
                TextStyle(fontSize = s.value.sp),
            ).size.width
        }
    }
    // one character of the row's own words, in the row's own language: the
    // spacing is nudged by characters -- one to the right before 次数, three to
    // the left after 间隔 -- and a Chinese glyph is wider than a Latin one
    val charStep = with(LocalDensity.current) {
        val word = tr("次数")
        (measurer.measure(word, TextStyle(fontSize = s.title.sp)).size.width.toFloat() /
            word.length).toDp()
    }
    val kindColumn = with(LocalDensity.current) {
        // the chip's own 5 dp each side, and a little slack so the label and its
        // arrow never have to wrap onto a second line
        (widestKind + 16.dp.toPx()).toDp()
    }
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 1.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // the same three lines, three times, each one chip: the whole of what
        // an answer is, in one place per answer
        AnswerTitle(tr("通知方式"), enabled)
        Spacer(Modifier.width(10.dp))
        Box(Modifier.widthIn(min = kindColumn)) {
            AnswerChip(
                title = tr("通知方式"),
                label = notifyKindLabel(kind),
                items = NotifyKind.entries.map { notifyKindLabel(it) to it },
                current = kind,
                // two short words would otherwise open a chip-sized menu; 140
                // dp still fits the title and both choices without spanning
                // most of the screen
                width = 140.dp,
                enabled = enabled,
            ) { onAnswer(answer.copy(kind = it)) }
        }
        // 次数 one character further right, so the three answers read as three
        // columns rather than one run of chips
        Spacer(Modifier.width(10.dp + charStep))
        AnswerTitle(tr("次数"), enabled)
        Spacer(Modifier.width(6.dp))
        AnswerChip(
            title = tr("次数"),
            label = n.timesLabel(count),
            items = n.times().map { it.second() to it.first },
            current = count,
            enabled = enabled,
        ) { onAnswer(answer.copy(times = it)) }
        // the rest of the row is 间隔's: at the far end it keeps its place on
        // every notification, whatever width the count beside it happens to be
        Spacer(Modifier.weight(1f))
        AnswerTitle(tr("间隔"), enabled)
        Spacer(Modifier.width(6.dp))
        // at 1次 there is nothing between: the answer is 0, and it is shown
        // rather than the column going away
        AnswerChip(
            title = tr("间隔"),
            label = if (count == 1) "0" else gapLabel(gap),
            items = if (count == 1) null else GAPS,
            current = gap,
            enabled = enabled,
        ) { onAnswer(answer.copy(gap = it)) }
        // three characters back from the edge: the last chip keeps the card's
        // margin instead of sitting against it
        Spacer(Modifier.width(charStep * 3f))
    }
}

/** The word in front of an answer's chip: the row's own size and weight. */
@Composable
private fun AnswerTitle(text: String, enabled: Boolean) {
    Text(
        text,
        fontSize = scale().title.sp,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.onSurface
            .copy(alpha = if (enabled) 1f else DISABLED),
    )
}

/**
 * One answer's chip, and the only way the row draws one.
 *
 * [items] and [current] are null for an answer nobody can change -- 间隔 at
 * 1次 -- which is drawn as the fixed chip instead; both take the same slot and
 * the same padding, so the row's three columns stay put whatever each holds.
 * The width is 通知方式's own: two short words would otherwise open a menu the
 * size of a tooltip (see ChipPicker).
 */
@Composable
private fun <T> AnswerChip(
    title: String,
    label: String,
    items: List<Pair<String, T>>?,
    current: T?,
    width: Dp? = null,
    enabled: Boolean = true,
    onPick: (T) -> Unit,
) {
    if (items == null || current == null) {
        FixedChip(label)
    } else {
        ChipPicker(
            label = label,
            title = title,
            items = items,
            current = current,
            onPick = onPick,
            width = width,
            enabled = enabled,
        )
    }
}

/** How a notification's way of arriving reads on its chip. */
fun notifyKindLabel(kind: NotifyKind): String = when (kind) {
    NotifyKind.BANNER -> tr("横幅")
    NotifyKind.VOICE -> tr("语音")
}
