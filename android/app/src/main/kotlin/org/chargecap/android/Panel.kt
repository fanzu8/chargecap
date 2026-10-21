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

import android.os.BatteryManager
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.input.TextFieldLineLimits
import androidx.compose.foundation.text.input.setTextAndPlaceCursorAtEnd
import androidx.compose.foundation.text.input.rememberTextFieldState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay

// The panel: the status table, the limits and the chart controls, laid out like
// the GTK app's PreferencesPage -- the same rows, the same inline key chips,
// the same per-metric colours.  The one thing Android cannot do without root
// is the charging control itself, so those rows are shown greyed out with the
// reason next to them.

private val TITLE_W = 68.dp          // the title gutter of the status table
// A row's cells are laid out in shared columns (the GTK app's COL_FRACS), so a
// key in the second cell starts at the same x in every row -- the alignment the
// GTK panel has and this one lost when its rows each picked their own weights.
private const val COL_FIRST = 0.312f
private const val COL_REST = 1f - COL_FIRST
internal val DISABLED = 0.38f         // Material's disabled alpha
private const val HINT_MS = 2000L    // how long a ⓘ hint stays up
private val AMBER = Color(0xFFE5A50A)    // the GTK app's "off" colour
private val GREEN = Color(0xFF2EC27E)    // ... and its "on" colour

/** The plot's height, the GTK app's 139px ("+15px, as asked") in dp. */
val CHART_HEIGHT: Dp = 139.dp

/**
 * One group of rows, boxed like the GTK app's Adw.PreferencesGroup.
 *
 * The GTK app's page is a stack of boxes: a title, then a card holding the
 * rows with a hairline between them.  Without the boxes the whole panel reads
 * as one block and nothing says where a section starts -- which is exactly how
 * this looked before, so the boxes are the point.
 */
@Composable
internal fun Section(
    title: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(top = 6.dp),
    ) {
        if (title != null) {
            Text(
                title,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp),
            )
        }
        Surface(
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surfaceContainerHigh,
            border = BorderStroke(1.dp,
                                  MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f)),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(
                Modifier.padding(horizontal = 12.dp, vertical = 2.dp),
                content = content,
            )
        }
    }
}

/** The hairline Adw draws between the rows of a group. */
@Composable
internal fun RowDivider() {
    HorizontalDivider(
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f),
        thickness = 1.dp,
    )
}

/** An inline key: bold, dimmer than its value, with a flat chip behind it. */
@Composable
private fun KeyChip(
    text: String,
    color: Color? = null,
    size: Float = scale().key,
    raised: Boolean = false,
) {
    Text(
        text,
        color = color ?: MaterialTheme.colorScheme.onSurface,
        fontSize = size.sp,
        fontWeight = FontWeight.Bold,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = Modifier
            .shadow(if (raised) 2.dp else 0.dp, RoundedCornerShape(8.dp))
            .background(
                MaterialTheme.colorScheme.onSurface.copy(
                    alpha = if (raised) 0.16f else 0.10f),
                RoundedCornerShape(8.dp),
            )
            .padding(horizontal = 6.dp, vertical = 1.dp),
    )
}

@Composable
private fun ValueText(
    text: String,
    color: Color? = null,
    modifier: Modifier = Modifier,
    size: Float = scale().value,
) {
    Text(
        text,
        color = color ?: MaterialTheme.colorScheme.onSurface,
        fontSize = size.sp,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = modifier,
    )
}

/**
 * One status row: a title in the left gutter, then the row's cells.
 *
 * The cells take proportional widths, so the values of a column start at the
 * same place down the panel; the long title at the bottom sizes to its own
 * content instead and is laid out above its values.
 */
@Composable
private fun StatusRow(
    title: String,
    titleColor: Color? = null,
    unit: String? = null,
    unitColor: Color? = null,
    fitTitle: Boolean = false,
    titleSize: Float? = null,
    content: @Composable RowScope.() -> Unit,
) {
    val s = scale()
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(if (fitTitle) Modifier else Modifier.width(TITLE_W)) {
            KeyChip(title, titleColor, titleSize ?: s.title)
            if (unit != null) {
                Spacer(Modifier.height(1.dp))
                KeyChip(unit, unitColor ?: titleColor, s.sub)
            }
        }
        Spacer(Modifier.width(6.dp))
        Row(
            Modifier.weight(1f),
            verticalAlignment = Alignment.CenterVertically,
            content = content,
        )
    }
}

/** The second cell of a row: a key, then its value, in the shared column. */
@Composable
private fun RowScope.KeyedCell(
    label: String,
    color: Color? = null,
    value: String,
) {
    Row(
        Modifier.weight(COL_REST),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        KeyChip(label, color, scale().key)
        Spacer(Modifier.width(6.dp))
        ValueText(value, color)
    }
}

/** 已连接 / 充电中 take the GTK app's green, 未连接 / 未充电 its amber. */
@Composable
private fun ChargedValue(
    text: String,
    on: Boolean,
    modifier: Modifier = Modifier,
    bold: Boolean = false,
    big: Boolean = false,
) {
    val s = scale()
    Text(
        text,
        color = if (on) GREEN else AMBER,
        fontSize = (if (big) s.big else s.title).sp,
        fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = modifier,
    )
}

@Composable
private fun InfoButton(title: String, body: String) {
    var open by remember { mutableStateOf(false) }
    // a hint, not a menu: it goes away on its own, so a tapped ⓘ never sits
    // there covering the row it explains
    LaunchedEffect(open) {
        if (open) {
            delay(HINT_MS)
            open = false
        }
    }
    Box {
        TextButton(
            onClick = { open = true },
            contentPadding = PaddingValues(0.dp),
            modifier = Modifier.size(18.dp),
        ) {
            Text("ⓘ", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f))
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            Column(Modifier.padding(horizontal = 12.dp, vertical = 8.dp).width(240.dp)) {
                Text(title, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                Text(
                    body,
                    fontSize = 10.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
                )
            }
        }
    }
}

@Composable
private fun UsbHelp() {
    InfoButton(
        tr("USB 类型说明"),
        tr("AC：充电头\n") + tr("USB：电脑或充电宝的 USB 口\n") +
            tr("无线：无线充电板\n") + tr("未知：未识别，通常是没插线"),
    )
}

@Composable
private fun GaugeHelp() {
    InfoButton(
        tr("电量计说明"),
        tr("电量计累计流过的电荷，不是剩余电量：\n") +
            tr("· 与上面的电量百分比无关\n") +
            tr("· 部分机型（本机就是）满电时会复位\n") +
            tr("· 方向与量纲都可能不准；可靠的是它的变化速度，也就是电流"),
    )
}

@Composable
private fun HealthHelp() {
    InfoButton(
        tr("健康度说明"),
        tr("健康度是系统上报的电池状态，不是磨损百分比：\n") +
            tr("磨损要算 充满容量/设计容量，而 Android 不发布 充满容量"),
    )
}

/** BatteryManager's health states, which the GTK app computes from capacities. */
private fun healthLabel(health: Int): String? = when (health) {
    BatteryManager.BATTERY_HEALTH_GOOD -> tr("良好")
    BatteryManager.BATTERY_HEALTH_OVERHEAT -> tr("过热")
    BatteryManager.BATTERY_HEALTH_DEAD -> tr("损坏")
    BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE -> tr("过压")
    BatteryManager.BATTERY_HEALTH_UNSPECIFIED_FAILURE -> tr("故障")
    BatteryManager.BATTERY_HEALTH_COLD -> tr("过冷")
    else -> null
}

// ---- the status table -------------------------------------------------------

@Composable
fun StatusRows(s: Snapshot, blank: Boolean, sampleMs: Int, onSample: (Int) -> Unit) {
    val sc = scale()
    val red = METRIC_INFO.getValue("current_mA").color

    Column {
        // 电源: three bare values, no keys.  They hug the left instead of
        // spreading out -- the gaps were doing nothing, and the room they free
        // is where the chart's recording interval goes.
        StatusRow(tr("电源"), fitTitle = true, titleSize = sc.big) {
            ChargedValue(if (blank) "—" else if (s.plugged) tr("已连接") else tr("未连接"),
                         !blank && s.plugged, big = true, bold = true)
            Spacer(Modifier.width(8.dp))
            ChargedValue(if (blank) "—" else if (s.charging) tr("充电中") else tr("未充电"),
                         !blank && s.charging, big = true, bold = true)
            Spacer(Modifier.width(8.dp))
            ValueText(if (blank) "—" else s.capacity?.let { "$it%" } ?: "—", size = sc.big)
            Spacer(Modifier.weight(1f))
            // the same inline key as 温度(°C) or 极值: bold, on its own chip,
            // at full strength -- a bare dim label read as grey next to them
            KeyChip(tr("采样间隔"), null, sc.value, raised = true)
            Spacer(Modifier.width(4.dp))
            ChipPicker(
                label = sampleLabel(sampleMs),
                title = tr("采样间隔"),
                items = SAMPLES,
                current = sampleMs,
                onPick = onSample,
                raised = true,
            )
        }
        RowDivider()

        // second row: two mAh numbers and the battery's health.  The first one is the
        // gauge's own coulomb counter -- all Android publishes, since there is no
        // charge_full to make a wear percentage out of -- so it carries a ⓘ: on its
        // own, "54/4000" invites exactly the wrong reading (see the help text).
        StatusRow(tr("统计/设计容量(mAh)"), fitTitle = true) {
            val counter = if (blank) null else s.chargeCounterUAh?.let { it / 1000 }
            val design = if (blank) null else s.designUAh?.let { it / 1000 }
            ValueText(
                when {
                    counter != null && design != null -> "$counter/$design"
                    counter != null -> "$counter/—"
                    design != null -> "—/$design"
                    else -> "—"
                },
            )
            Spacer(Modifier.width(4.dp))
            GaugeHelp()
            Spacer(Modifier.width(10.dp))
            KeyChip(tr("健康度"), null, scale().small)
            Spacer(Modifier.width(4.dp))
            ValueText(if (blank) "—" else healthLabel(s.health) ?: "—")
            Spacer(Modifier.width(4.dp))
            HealthHelp()
        }
        RowDivider()

        // USB 类型 with a help button, then 温度 on the same row
        StatusRow(tr("USB类型")) {
            val type = plugTypeLabel(s.plugType)
            Row(Modifier.weight(COL_FIRST), verticalAlignment = Alignment.CenterVertically) {
                ValueText(
                    when {
                        blank || !s.plugged -> "—"
                        type == null -> tr("未知")
                        else -> type
                    },
                )
                Spacer(Modifier.width(4.dp))
                UsbHelp()
            }
            KeyedCell(
                tr("温度(°C)"), METRIC_INFO.getValue("temp_c").color,
                if (blank) "—" else s.tempC?.let { fmt("%.1f", it) } ?: "—",
            )
        }
        RowDivider()

        StatusRow(tr("电压(V)"), titleColor = METRIC_INFO.getValue("voltage_v").color) {
            ValueText(
                if (blank) "—" else s.voltageV?.let { fmt("%.3f", it) } ?: "—",
                METRIC_INFO.getValue("voltage_v").color,
                Modifier.weight(COL_FIRST),
            )
            KeyedCell(
                tr("功率(W)"), METRIC_INFO.getValue("power_w").color,
                if (blank) "—" else s.powerW?.let { fmt("%+.2f", it) } ?: "—",
            )
        }
        RowDivider()

        // 电流: the reading and its extremes on the left, the rated maximum and the
        // writable limit on the right, so the two halves read as one block.
        StatusRow(tr("电流"), titleColor = red, unit = "(mA)", unitColor = red) {
            Column(Modifier.weight(1f)) {
                ValueText(if (blank) "—" else s.currentA?.let { fmt("%+.0f", it * 1000) } ?: "—", red)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    KeyChip(tr("极值"), red, sc.small)
                    Spacer(Modifier.width(4.dp))
                    ValueText(
                        if (blank) "—"
                        else if (s.currentMinMA != null && s.currentMaxMA != null)
                            fmt("%.0f", s.currentMinMA) + " | " + fmt("%.0f", s.currentMaxMA)
                        else "—",
                        red,
                        size = sc.small,
                    )
                }
            }
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    KeyChip(tr("限制"), red, sc.small)
                    Spacer(Modifier.width(4.dp))
                    // the GTK app's spin button; without root there is nothing to
                    // write it to, so it stays empty and inert
                    Box(
                        Modifier
                            .width(38.dp)
                            .border(1.dp, MaterialTheme.colorScheme.onSurface.copy(alpha = 0.20f),
                                    RoundedCornerShape(6.dp))
                            .padding(horizontal = 6.dp, vertical = 1.dp),
                    ) {
                        Text("—", color = red.copy(alpha = 0.5f), fontSize = sc.spin.sp)
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    KeyChip(tr("最大"), red, sc.small)
                    Spacer(Modifier.width(4.dp))
                    ValueText("—", red, size = sc.small)
                }
            }
        }
        RowDivider()
    }
}

// ---- the controls -----------------------------------------------------------
// 充电限制 needs the root daemon the GTK app writes its request file to, and
// Android has no such thing without root: the rows are the GTK app's own, shown
// with the daemon's defaults and switched off.

@Composable
internal fun SwitchRow(
    title: String,
    checked: Boolean,
    enabled: Boolean,
    subtitle: String = "",
    /** the page's own switch: a size up from the rows under it */
    master: Boolean = false,
    onChange: (Boolean) -> Unit,
) {
    val s = scale()
    val alpha = if (enabled) 1f else DISABLED
    Row(
        Modifier
            .fillMaxWidth()
            // a row keeps its height whether it can be tapped or not, so a dead
            // row is not a smaller one; the master is taller than the rows under
            // it, which is the other half of how the two are told apart
            .heightIn(min = if (master) 56.dp else 48.dp)
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            // plain bold text: the chip that used to sit behind these two
            // titles read as a shadow around the words
            Text(
                title,
                fontSize = (if (master) s.heading + 4f else s.heading).sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface,
            )
            // a row without a note keeps its title and nothing else: the 通知
            // page's rows read for themselves
            if (subtitle.isNotEmpty()) {
                Text(
                    subtitle,
                    fontSize = s.small.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f * alpha),
                )
            }
        }
        Switch(
            checked = checked,
            onCheckedChange = onChange,
            enabled = enabled,
            // the master is the page's one switch, and the ones under it are a
            // size down, so the two are told apart at a glance
            modifier = Modifier.scale(if (master) 1f else 0.8f),
        )
    }
}

/**
 * A notification's three answers on one row: the title, the number it fires at
 * in the middle, and the switch at the end.
 *
 * The number sits between the two because that is where it is read -- "电量过低
 * 10%, on" -- and the 达 / 低于 / 高于 that used to stand beside it said nothing
 * the title had not already said.  The ± stay: a number is stepped far more
 * often than it is typed, and both go through the same check.
 */
@Composable
internal fun SwitchStepperRow(
    title: String,
    checked: Boolean,
    value: Int,
    unit: String,
    step: Int,
    /** 通知开关 off: the row dims and stops taking input, and keeps every
     *  answer it already holds */
    enabled: Boolean = true,
    onCheck: (Boolean) -> Unit,
    onChange: (Int) -> Int,
) {
    val s = scale()
    val alpha = if (enabled) 1f else DISABLED
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            title,
            fontSize = s.heading.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha),
            modifier = Modifier.weight(1f),
        )
        NumberField(value, unit, enabled = enabled, onCommit = onChange)
        Spacer(Modifier.width(2.dp))
        StepButton("−", enabled) { onChange(value - step) }
        StepButton("+", enabled) { onChange(value + step) }
        Spacer(Modifier.width(4.dp))
        Switch(
            checked = checked,
            onCheckedChange = onCheck,
            enabled = enabled,
            modifier = Modifier.scale(0.8f),
        )
    }
}

@Composable
private fun StepButton(label: String, enabled: Boolean, onClick: () -> Unit) {
    TextButton(
        onClick = onClick,
        enabled = enabled,
        contentPadding = PaddingValues(0.dp),
        modifier = Modifier.size(30.dp, 26.dp),
    ) {
        Text(label, fontSize = 14.sp)
    }
}

@Composable
internal fun StepperRow(
    title: String,
    value: Int,
    unit: String,
    step: Int,
    enabled: Boolean,
    /** where the number landed: the row shows what was kept, not what was typed */
    onChange: (Int) -> Int,
) {
    val s = scale()
    val alpha = if (enabled) 1f else DISABLED
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 1.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            title,
            fontSize = s.title.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha),
            modifier = Modifier.weight(1f),
        )
        NumberField(value, unit, enabled, onChange)
        Spacer(Modifier.width(6.dp))
        StepButton("−", enabled) { onChange(value - step) }
        StepButton("+", enabled) { onChange(value + step) }
    }
}

/**
 * The number itself: typed, not only stepped.
 *
 * A field the width of its digits with its unit beside it, the keyboard's done
 * -- or simply looking away -- as the moment it is read.  What comes out goes
 * through the same check as a stepped number (AppState.kt keeps the ranges and
 * the two lines that may not cross), and the row then shows what was kept, so a
 * number out of range is answered rather than stored.
 */
@Composable
private fun NumberField(
    value: Int,
    unit: String,
    enabled: Boolean,
    onCommit: (Int) -> Int,
) {
    val s = scale()
    val alpha = if (enabled) 1f else DISABLED
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    val line = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.18f)
    val field = rememberTextFieldState(value.toString())

    // a step, or a number the check moved, is the app's and the text follows it;
    // typing only moves the text, and the number moves when the field is read
    LaunchedEffect(value) {
        val shown = value.toString()
        if (field.text.toString() != shown) field.setTextAndPlaceCursorAtEnd(shown)
    }

    fun commit() {
        val typed = field.text.toString().trim().toIntOrNull()
        val kept = if (typed == null) value else onCommit(typed)
        if (field.text.toString() != kept.toString()) {
            field.setTextAndPlaceCursorAtEnd(kept.toString())
        }
    }

    // the hairline runs under the number and its unit, and says the number can
    // be typed in; a row that cannot be edited has none
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = if (enabled) Modifier.drawBehind {
            drawLine(
                line,
                Offset(0f, size.height),
                Offset(size.width, size.height),
                1.dp.toPx(),
            )
        } else Modifier,
    ) {
        BasicTextField(
            state = field,
            enabled = enabled,
            textStyle = LocalTextStyle.current.copy(
                fontSize = s.spin.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha),
                textAlign = TextAlign.End,
            ),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Number,
                imeAction = ImeAction.Done,
            ),
            // the keyboard's done reads it; so does looking away
            onKeyboardAction = {
                commit()
                focus.clearFocus()
                keyboard?.hide()
            },
            lineLimits = TextFieldLineLimits.SingleLine,
            cursorBrush = SolidColor(MaterialTheme.colorScheme.primary),
            modifier = Modifier
                .width(44.dp)
                .onFocusChanged { if (!it.isFocused) commit() },
        )
        Text(
            unit,
            fontSize = s.spin.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha),
        )
    }
}

@Composable
fun LimitsSection() {
    // no section title: the switch below says what the box is for
    Section {
        Row(
            Modifier.padding(vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            KeyChip(tr("未 root"), AMBER, scale().small)
            Spacer(Modifier.width(6.dp))
            Text(
                tr("仅提供状态"),
                fontSize = scale().small.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            )
        }
        RowDivider()
        SwitchRow(tr("限制充电"), subtitle = tr("达上限停止充电，降到下限恢复充电，区间滞回"),
                  checked = false, enabled = false, onChange = {})
        RowDivider()
        StepperRow(tr("上限"), 50, "%", 5, enabled = false) { it }
        RowDivider()
        StepperRow(tr("下限"), 45, "%", 5, enabled = false) { it }
    }
}

/**
 * 禁止休眠: a partial wake lock, which Android does allow without root -- its
 * own box, untitled, like the GTK app's group with no title.
 */
@Composable
fun SleepSection(inhibit: Boolean, onChange: (Boolean) -> Unit) {
    Section {
        SwitchRow(tr("禁止休眠"), subtitle = tr("系统不休眠，保持网络在线"),
                  checked = inhibit, enabled = true, onChange = onChange)
        RowDivider()
        SleepRow()
    }
}

/**
 * 休眠记录: the record under the switch that promises it will not happen.
 *
 * Read-only on purpose -- a sleeping system delivers nothing, so this is not
 * a notification and has no 通知方式, no 次数 and no 间隔.  It has nothing to do
 * with 通知开关 either: the count is the last 禁止休眠 turn-on's, because the
 * question it answers is whether that switch held.  A tap opens the history
 * the record kept.
 */
@Composable
private fun SleepRow() {
    val s = scale()
    var open by remember { mutableStateOf(false) }
    // one line, not two: the name, the record's own words, the count.  Two
    // lines made this row a size taller than 禁止休眠 above it, and the two
    // rows are read as a pair -- the promise and whether it held
    Row(
        Modifier
            .fillMaxWidth()
            .clickable { open = true }
            .heightIn(min = 48.dp)
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            tr("休眠记录"),
            fontSize = s.heading.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(
            Sleeps.line(),
            fontSize = s.small.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 8.dp),
        )
        Text(
            "${Sleeps.count}" + tr("次"),
            fontSize = s.heading.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
    if (open) {
        AlertDialog(
            onDismissRequest = { open = false },
            title = {
                Text(
                    tr("休眠记录"),
                    fontSize = s.heading.sp,
                    fontWeight = FontWeight.Bold,
                )
            },
            text = {
                Column {
                    if (Sleeps.naps.isEmpty()) {
                        Text(
                            tr("还没有休眠"),
                            fontSize = s.small.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                        )
                    } else {
                        for (nap in Sleeps.naps) {
                            Text(
                                nap.line(),
                                fontSize = s.small.sp,
                                color = MaterialTheme.colorScheme.onSurface,
                                modifier = Modifier.padding(bottom = 4.dp),
                            )
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { open = false }) { Text(tr("知道了")) }
            },
        )
    }
}

// ---- the chart controls -----------------------------------------------------

@Composable
private fun ChipButton(
    onClick: () -> Unit,
    color: Color,
    shape: Shape = RoundedCornerShape(10.dp),
    shadow: Dp = 0.dp,
    content: @Composable () -> Unit,
) {
    Box(
        Modifier
            // on a dark panel a black shadow is invisible, so a raised chip also
            // takes a shade lighter background
            .shadow(shadow, shape)
            .clip(shape)
            .background(color)
            .clickable(onClick = onClick)
            .padding(horizontal = 5.dp, vertical = 3.dp),
    ) {
        content()
    }
}

@Composable
private fun MetricButton(metric: Metric, on: Boolean, onClick: () -> Unit) {
    ChipButton(
        onClick = onClick,
        color = if (on) metric.color.copy(alpha = 0.30f)
        else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.06f),
    ) {
        Text(
            metricButtonLabel(metric),
            fontSize = scale().value.sp,
            fontWeight = if (on) FontWeight.Bold else FontWeight.Normal,
            color = if (on) metricBright(metric.key)
            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.30f),
        )
    }
}

/**
 * The title of a menu, so a popover says what it is choosing between.
 */
@Composable
internal fun MenuTitle(text: String) {
    Text(
        text,
        fontSize = 11.sp,
        fontWeight = FontWeight.Normal,
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
        modifier = Modifier.padding(start = 12.dp, top = 8.dp, bottom = 2.dp),
    )
}

/**
 * One candidate in a menu: a line of plain text, the chosen one ticked.
 *
 * It was Material's own DropdownMenuItem, which reserves 48dp for every row:
 * thirteen candidates came to most of a phone screen, with the text alone in
 * the middle of each.  This row is text and nothing else -- 24dp, which leaves
 * the 12dp of air above and below the words that was asked for.
 */
@Composable
private fun MenuRow(text: String, selected: Boolean, onClick: () -> Unit) {
    Text(
        text,
        fontSize = scale().value.sp,
        fontWeight = FontWeight.Normal,
        color = MaterialTheme.colorScheme.onSurface.copy(
            alpha = if (selected) 1f else 0.85f),
        maxLines = 1,
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .heightIn(min = 24.dp)
            .padding(horizontal = 12.dp),
    )
}

/**
 * A chip that shows the value it holds and opens a list to change it.
 *
 * Content sized on purpose: a TextButton's minimum width and padding pushed the
 * metric row onto a second line once already.
 */
@Composable
internal fun <T> ChipPicker(
    label: String,
    title: String,
    items: List<Pair<String, T>>,
    current: T,
    onPick: (T) -> Unit,
    raised: Boolean = false,
    /** a menu wider than its contents asks for: the 通知方式 list is two short
     *  words, and a chip-sized menu reads as a tooltip rather than a list */
    width: Dp? = null,
    /** 通知开关 off: the chip is drawn, dimmed, and opens nothing */
    enabled: Boolean = true,
) {
    var open by remember { mutableStateOf(false) }
    Box(Modifier.alpha(if (enabled) 1f else DISABLED)) {
        ChipButton(
            onClick = { if (enabled) open = true },
            shape = RoundedCornerShape(8.dp),
            color = MaterialTheme.colorScheme.onSurface.copy(
                alpha = if (raised) 0.16f else 0.10f),
            shadow = if (raised) 2.dp else 0.dp,
        ) {
            Text(
                "$label \u25be",
                fontSize = scale().value.sp,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
        DropdownMenu(
            expanded = open,
            onDismissRequest = { open = false },
            modifier = if (width != null) Modifier.width(width) else Modifier,
        ) {
            MenuTitle(title)
            for ((itemLabel, value) in items) {
                MenuRow(
                    text = (if (value == current) "\u2713 " else "   ") + itemLabel,
                    selected = value == current,
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
 * A chip that names a value nothing can change -- 间隔 at 1次, where the gap is
 * 0.  It is drawn like the pickers beside it, a shade dimmer, and it does not
 * open anything.
 */
@Composable
internal fun FixedChip(label: String) {
    Box(
        Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.onSurface.copy(alpha = 0.06f))
            .padding(horizontal = 5.dp, vertical = 3.dp),
    ) {
        Text(
            label,
            fontSize = scale().value.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = DISABLED),
        )
    }
}

@Composable
fun ChartRows(
    buffer: SampleBuffer,
    selected: List<String>,
    onToggle: (String) -> Unit,
    windowSecs: Int,
    onWindow: (Int) -> Unit,
    seq: Long,
    /** 实时采集: off means there is nothing to chart */
    live: Boolean,
    /** 图形化: whether the sampler keeps what it reads */
    recording: Boolean,
) {
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            for (metric in METRICS) {
                if (metric != METRICS.first()) Spacer(Modifier.width(4.dp))
                MetricButton(metric, metric.key in selected) { onToggle(metric.key) }
            }
            // the slack goes between the two, exactly as the GTK app's spacer
            // does, so the whole row stays one line wide
            // the slack goes between the two, exactly as the GTK app's spacer
            // does, so the whole row stays one line wide
            Spacer(Modifier.weight(1f))
            Text(
                tr("窗口"),
                fontSize = scale().value.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
            )
            Spacer(Modifier.width(4.dp))
            ChipPicker(
                label = WINDOWS.firstOrNull { it.second == windowSecs }?.first ?: "1min",
                title = tr("窗口"),
                items = WINDOWS,
                current = windowSecs,
                onPick = onWindow,
            )
        }
        Spacer(Modifier.height(3.dp))
        if (live && recording) {
            LiveChart(
                buffer = buffer,
                selected = selected,
                windowSecs = windowSecs,
                seq = seq,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(CHART_HEIGHT),
            )
        } else {
            // 采集 off: no canvas at all, so nothing is laid out, drawn or
            // repainted -- the box only keeps the height, so the page does
            // not jump when the switch comes back
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(CHART_HEIGHT),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    if (live) tr("图形化已关闭") else tr("实时采集已关闭"),
                    fontSize = scale().small.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
                )
            }
        }
    Spacer(Modifier.height(4.dp))
    }
}

/**
 * 高级's live card: 实时采集 at the top, the readings under it, the chart at
 * the bottom -- one card, because they are one thing.
 *
 * 实时采集 is the master: off stops the reads (the rows blank rather than
 * freezing a number that is no longer true) and puts 图形化 out of reach, which
 * goes off with it.  On Android the process-wide sampler keeps running for the
 * notification rules -- this gates the page, not the monitor.
 */
@Composable
fun LiveSection(state: AppState, snapshot: Snapshot) {
    Section {
        // the card's two gates, one at each end
        LiveSwitchesRow(
            live = state.live,
            recording = state.recording,
            onLive = state::setLive,
            onRecord = state::setRecording,
        )
        RowDivider()
        StatusRows(
            s = snapshot,
            blank = !state.live,
            sampleMs = state.sampleMs,
            onSample = state::setSampleMs,
        )
        RowDivider()
        ChartRows(
            buffer = state.history,
            selected = state.metrics,
            onToggle = state::toggleMetric,
            windowSecs = state.windowSecs,
            onWindow = state::setWindow,
            seq = if (state.live) snapshot.seq else 0L,
            live = state.live,
            recording = state.recording,
        )
    }
}

/**
 * 实时采集 and 图形化 on one line, at the card's two ends: the table's gate
 * and the chart's, a pair of switches of the same kind.
 *
 * 图形化 is only reachable while 实时采集 reads the phone -- a chart of nothing
 * is not a setting.  The switch lays itself out at 32 dp however it is scaled,
 * so the row boxes it at 24; the row itself is 36 dp, a little taller than the
 * value rows, because two switches on one line need the room.
 */
@Composable
private fun LiveSwitchesRow(
    live: Boolean,
    recording: Boolean,
    onLive: (Boolean) -> Unit,
    onRecord: (Boolean) -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 36.dp)
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        LiveSwitch(tr("实时采集"), live, enabled = true, onChange = onLive)
        Spacer(Modifier.weight(1f))
        LiveSwitch(tr("图形化"), recording, enabled = live, onChange = onRecord)
    }
}

@Composable
private fun RowScope.LiveSwitch(
    title: String,
    checked: Boolean,
    enabled: Boolean,
    onChange: (Boolean) -> Unit,
) {
    val s = scale()
    Text(
        title,
        fontSize = s.heading.sp,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.onSurface
            .copy(alpha = if (enabled) 1f else DISABLED),
    )
    Spacer(Modifier.width(6.dp))
    Box(
        Modifier.height(24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Switch(
            checked = checked,
            onCheckedChange = onChange,
            enabled = enabled,
            modifier = Modifier.scale(0.8f),
        )
    }
}

/** 打开: a row that leaves the app for a screen only the system owns. */
@Composable
internal fun LinkRow(title: String, subtitle: String, onClick: () -> Unit) {
    val s = scale()
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                title,
                fontSize = s.heading.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                subtitle,
                fontSize = s.small.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            )
        }
        ChipButton(
            onClick = onClick,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.10f),
        ) {
            Text(
                tr("打开") + " \u203a",
                fontSize = s.value.sp,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
    }
}
