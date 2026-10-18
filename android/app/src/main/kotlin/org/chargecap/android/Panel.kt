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
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// The panel: the status table, the limits and the chart controls, laid out like
// the GTK app's PreferencesPage -- the same rows, the same inline key chips,
// the same per-metric colours.  The one thing Android cannot do without root
// is the charging control itself, so those rows are shown greyed out with the
// reason next to them.

private val TITLE_W = 68.dp          // the title gutter of the status table
private val DISABLED = 0.38f         // Material's disabled alpha
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
private fun Section(
    title: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(top = 12.dp),
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
                Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                content = content,
            )
        }
    }
}

/** The hairline Adw draws between the rows of a group. */
@Composable
private fun RowDivider() {
    HorizontalDivider(
        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.08f),
        thickness = 1.dp,
    )
}

/** An inline key: bold, dimmer than its value, with a flat chip behind it. */
@Composable
private fun KeyChip(text: String, color: Color? = null, size: Float = scale().key) {
    Text(
        text,
        color = color ?: MaterialTheme.colorScheme.onSurface,
        fontSize = size.sp,
        fontWeight = FontWeight.Bold,
        maxLines = 1,
        overflow = TextOverflow.Ellipsis,
        modifier = Modifier
            .background(
                MaterialTheme.colorScheme.onSurface.copy(alpha = 0.10f),
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
    content: @Composable RowScope.() -> Unit,
) {
    val s = scale()
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(if (fitTitle) Modifier else Modifier.width(TITLE_W)) {
            KeyChip(title, titleColor, s.title)
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

/** 已连接 / 充电中 take the GTK app's green, 未连接 / 未充电 its amber. */
@Composable
private fun ChargedValue(text: String, on: Boolean, modifier: Modifier = Modifier) {
    ValueText(text, if (on) GREEN else AMBER, modifier)
}

@Composable
private fun InfoButton(title: String, body: String) {
    var open by remember { mutableStateOf(false) }
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
fun StatusSection(s: Snapshot) {
    val sc = scale()
    val red = METRIC_INFO.getValue("current_mA").color

    Section {
        // 电源: three bare values, no keys
        StatusRow(tr("电源")) {
            ChargedValue(if (s.plugged) tr("已连接") else tr("未连接"), s.plugged,
                         Modifier.weight(1f))
            ChargedValue(if (s.charging) tr("充电中") else tr("未充电"), s.charging,
                         Modifier.weight(1f))
            ValueText(s.capacity?.let { "$it%" } ?: "—", modifier = Modifier.weight(1f))
        }
        RowDivider()

        // USB 类型 with a help button, then 温度 on the same row
        StatusRow(tr("USB类型")) {
            val type = plugTypeLabel(s.plugType)
            Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
                ValueText(
                    when {
                        !s.plugged -> "—"
                        type == null -> tr("未知")
                        else -> type
                    },
                )
                Spacer(Modifier.width(4.dp))
                UsbHelp()
            }
            KeyChip(tr("温度(°C)"), METRIC_INFO.getValue("temp_c").color, sc.key)
            Spacer(Modifier.width(6.dp))
            ValueText(
                s.tempC?.let { fmt("%.1f", it) } ?: "—",
                METRIC_INFO.getValue("temp_c").color,
                Modifier.weight(1f),
            )
        }
        RowDivider()

        StatusRow(tr("电压(V)"), titleColor = METRIC_INFO.getValue("voltage_v").color) {
            ValueText(
                s.voltageV?.let { fmt("%.3f", it) } ?: "—",
                METRIC_INFO.getValue("voltage_v").color,
                Modifier.weight(1f),
            )
            KeyChip(tr("功率(W)"), METRIC_INFO.getValue("power_w").color, sc.key)
            Spacer(Modifier.width(6.dp))
            ValueText(
                s.powerW?.let { fmt("%+.2f", it) } ?: "—",
                METRIC_INFO.getValue("power_w").color,
                Modifier.weight(2f),
            )
        }
        RowDivider()

        // 电流: the reading and its extremes on the left, the rated maximum and the
        // writable limit on the right, so the two halves read as one block.
        StatusRow(tr("电流"), titleColor = red, unit = "(mA)", unitColor = red) {
            Column(Modifier.weight(1f)) {
                ValueText(s.currentA?.let { fmt("%+.0f", it * 1000) } ?: "—", red)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    KeyChip(tr("极值"), red, sc.small)
                    Spacer(Modifier.width(4.dp))
                    ValueText(
                        if (s.currentMinMA != null && s.currentMaxMA != null)
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

        // last row: two mAh numbers and the battery's health.  The first one is the
        // gauge's own coulomb counter -- all Android publishes, since there is no
        // charge_full to make a wear percentage out of -- so it carries a ⓘ: on its
        // own, "54/4000" invites exactly the wrong reading (see the help text).
        StatusRow(tr("电量计/设计容量(mAh)"), fitTitle = true) {
            val counter = s.chargeCounterUAh?.let { it / 1000 }
            val design = s.designUAh?.let { it / 1000 }
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
            ValueText(healthLabel(s.health) ?: "—")
            Spacer(Modifier.width(4.dp))
        HealthHelp()
    }
    }
}

// ---- the controls -----------------------------------------------------------
// 充电限制 needs the root daemon the GTK app writes its request file to, and
// Android has no such thing without root: the rows are the GTK app's own, shown
// with the daemon's defaults and switched off.

@Composable
private fun SwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    enabled: Boolean,
    onChange: (Boolean) -> Unit,
) {
    val s = scale()
    val alpha = if (enabled) 1f else DISABLED
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                title,
                fontSize = s.title.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha),
            )
            Text(
                subtitle,
                fontSize = s.small.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f * alpha),
            )
        }
        Switch(checked = checked, onCheckedChange = onChange, enabled = enabled)
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
private fun StepperRow(
    title: String,
    value: String,
    enabled: Boolean,
    onChange: (Int) -> Unit,
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
        Text(
            value,
            fontSize = s.spin.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = alpha),
        )
        Spacer(Modifier.width(6.dp))
        StepButton("−", enabled) { onChange(-1) }
        StepButton("+", enabled) { onChange(1) }
    }
}

@Composable
fun LimitsSection() {
    Section(tr("充电限制")) {
        Row(
            Modifier.padding(vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            KeyChip(tr("需要 root"), AMBER, scale().small)
            Spacer(Modifier.width(6.dp))
            Text(
                tr("本机没有 root：只能监控，充电限制不可用"),
                fontSize = scale().small.sp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            )
        }
        RowDivider()
        SwitchRow(tr("启动"), tr("开启后：达到上限停止充电，降到下限恢复"),
                  checked = false, enabled = false) {}
        RowDivider()
        StepperRow(tr("上限"), "70%", enabled = false) {}
        RowDivider()
        StepperRow(tr("下限"), "68%", enabled = false) {}
    }
}

/**
 * 禁止休眠: a partial wake lock, which Android does allow without root -- its
 * own box, untitled, like the GTK app's group with no title.
 */
@Composable
fun SleepSection(inhibit: Boolean, onChange: (Boolean) -> Unit) {
    Section {
        SwitchRow(tr("禁止休眠"), tr("持有唤醒锁：熄屏也不休眠，网络保持在线"),
                  checked = inhibit, enabled = true, onChange = onChange)
    }
}

// ---- the chart controls -----------------------------------------------------

@Composable
private fun MetricButton(metric: Metric, on: Boolean, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(10.dp),
        color = if (on) metric.color.copy(alpha = 0.30f) else Color.Transparent,
    ) {
        Text(
            metricButtonLabel(metric),
            fontSize = scale().value.sp,
            fontWeight = if (on) FontWeight.Bold else FontWeight.Normal,
            color = if (on) metricBright(metric.key)
            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.30f),
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}

@Composable
private fun WindowSelector(windowSecs: Int, onWindow: (Int) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val label = WINDOWS.firstOrNull { it.second == windowSecs }?.first ?: "1min"
    Box {
        TextButton(onClick = { open = true }) {
            ValueText("$label ▾")
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            for ((text, secs) in WINDOWS) {
                DropdownMenuItem(
                    text = { Text(text, fontSize = scale().value.sp) },
                    onClick = {
                        open = false
                        onWindow(secs)
                    },
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ChartSection(
    buffer: SampleBuffer,
    selected: List<String>,
    onToggle: (String) -> Unit,
    windowSecs: Int,
    onWindow: (Int) -> Unit,
    seq: Long,
) {
    Section(tr("指标")) {
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            for (metric in METRICS) {
                MetricButton(metric, metric.key in selected) { onToggle(metric.key) }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    tr("窗口"),
                    fontSize = scale().value.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f),
                )
                Spacer(Modifier.width(4.dp))
                WindowSelector(windowSecs, onWindow)
            }
        }
        Spacer(Modifier.height(4.dp))
        LiveChart(
            buffer = buffer,
            selected = selected,
            windowSecs = windowSecs,
            seq = seq,
            modifier = Modifier
                .fillMaxWidth()
                .height(CHART_HEIGHT),
        )
    Spacer(Modifier.height(6.dp))
    }
}
