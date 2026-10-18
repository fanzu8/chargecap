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

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import java.util.Locale

// The strings, the metric table and the type scale, kept in step with the GTK
// app by hand: Chinese is the source language and every user-visible string
// goes through tr(), so the two UIs say the same thing in the same words.

enum class Lang(val tag: String) {
    AUTO("auto"), ZH("zh"), EN("en");

    companion object {
        fun of(tag: String?): Lang = entries.firstOrNull { it.tag == tag } ?: AUTO
    }
}

// ---- language ---------------------------------------------------------------
// Only Chinese and English are shipped.  The GTK app translates from the same
// table; the extra keys at the bottom are the ones Android needs instead of
// sysfs (charger types, root-only controls, battery health states).
private val EN = mapOf(
    // window / groups
    "充电限制" to "Charge limit",
    "启动" to "Enable",
    "开启后：达到上限停止充电，降到下限恢复" to
        "Stops at the upper limit, resumes at the lower",
    "上限" to "Upper limit",
    "下限" to "Lower limit",
    "禁止休眠" to "Inhibit sleep",
    "系统可能挂起，开启可保持网络在线" to
        "The system may suspend; on keeps the network up",
    "指标" to "Metrics",
    "窗口" to "Window",
    // status table
    "电源" to "Power",
    "USB类型" to "USB",
    "电压(V)" to "Voltage",
    "功率(W)" to "Power",
    "电流" to "Current",
    "温度(°C)" to "Temp",
    // Android publishes the gauge's own counter, never charge_full: the row
    // says what the two numbers really are, and the ⓘ next to them says what
    // the first one is not
    "电量计/设计容量(mAh)" to "Gauge / design (mAh)",
    "电量计说明" to "About the gauge",
    "电量计累计流过的电荷，不是剩余电量：\n" to
        "Charge that has flowed through the gauge, not what is left:\n",
    "· 与上面的电量百分比无关\n" to
        "· it has nothing to do with the percentage above\n",
    "· 部分机型（本机就是）满电时会复位\n" to
        "· on some phones (this one) it resets when the battery is full\n",
    "· 方向与量纲都可能不准；可靠的是它的变化速度，也就是电流" to
        "· its sign and scale are not to be trusted; its rate is" +
        " (that is the current)",
    "极值" to "range",
    "最大" to "max",
    "限制" to "limit",
    "已连接" to "Plugged",
    "未连接" to "Unplugged",
    "充电中" to "Charging",
    "未充电" to "Idle",
    "未知" to "Unknown",
    "无线" to "Wireless",
    // chart
    "现在" to "now",
    "选择上方指标以显示曲线" to "Select a metric above to plot",
    // USB type help: Android reports the port it is plugged into, not the
    // SDP / DCP / CDP handshake the Linux charger driver does
    "USB 类型说明" to "About USB types",
    "AC：充电头\n" to "AC: mains charger\n",
    "USB：电脑或充电宝的 USB 口\n" to "USB: port on a computer or a power bank\n",
    "无线：无线充电板\n" to "Wireless: charging pad\n",
    "未知：未识别，通常是没插线" to "Unknown: nothing recognised, usually unplugged",
    // the app's own name: the Chinese name is 电电, the project name is chargecap
    "电电" to "chargecap",
    "跟随系统" to "Follow system",
    // root-only controls (the GTK app talks to a root daemon; Android has no
    // way to write the charger's sysfs without one)
    "本机没有 root：只能监控，充电限制不可用" to
        "No root on this device: monitoring only, charging cannot be limited",
    "需要 root" to "needs root",
    "健康度" to "Health",
    "良好" to "Good",
    "过热" to "Overheat",
    "损坏" to "Dead",
    "过压" to "Over voltage",
    "故障" to "Failure",
    "过冷" to "Cold",
)

object Strings {
    /**
     * The language chosen in the header; AUTO follows the system.
     *
     * It is Compose state, not a plain field: the strings are translated while
     * the UI is being built, and some of them live in their own composition
     * scopes (the ⓘ popovers), which would otherwise keep the language they
     * were first composed in.
     */
    var lang: Lang by mutableStateOf(Lang.AUTO)

    fun system(): Lang =
        if (Locale.getDefault().language == "zh") Lang.ZH else Lang.EN

    val effective: Lang
        get() = if (lang == Lang.AUTO) system() else lang

    fun tr(text: String): String =
        if (effective == Lang.ZH) text else EN[text] ?: text
}

/** The string in the user's language (Chinese is the source language). */
fun tr(text: String): String = Strings.tr(text)

// ---- the status table's type scale ------------------------------------------
// Chinese says the same thing in fewer pixels than English does, so each
// language declares its own scale instead of the columns being retuned per
// language: wide languages step down a point.  (Same numbers as the GTK app's
// SCALE table, now in sp / dp.)
data class Scale(
    val title: Float, val key: Float, val small: Float, val value: Float,
    val sub: Float, val spin: Float, val btn: Float,
)

val SCALE = mapOf(
    "zh" to Scale(title = 11f, key = 11f, small = 11f, value = 11f,
                  sub = 11f, spin = 11f, btn = 28f),
    "en" to Scale(title = 10f, key = 10f, small = 10f, value = 10f,
                  sub = 10f, spin = 10f, btn = 26f),
)

fun scale(): Scale = SCALE[Strings.effective.tag] ?: SCALE.getValue("en")

// ---- chart: the selectable metrics ------------------------------------------
// Each one has its own colour (the same colour is reused by the matching item
// in the status panel and by its toggle button) and a fixed Y axis side, so
// selecting/unselecting never makes an axis jump to the other edge.
//     key,        名称,  单位,  颜色,      刻度格式,   Y 轴,   固定量程
data class Metric(
    val key: String, val name: String, val unit: String, val color: Color,
    val format: String, val side: String, val fixed: Pair<Float, Float>? = null,
)

val METRICS = listOf(
    Metric("voltage_v", "电压", "V", Color(0xFF3584E4), "%.3f", "left"),
    Metric("current_mA", "电流", "mA", Color(0xFFE01B24), "%+.0f", "left"),
    Metric("power_w", "功率", "W", Color(0xFF9141AC), "%.2f", "left"),
    Metric("temp_c", "温度", "°C", Color(0xFFE5A50A), "%.1f", "right"),
    // 电量 is a percentage, so 0-100 is a better axis than an auto-zoomed one
    Metric("capacity", "电量", "%", Color(0xFF2EC27E), "%.0f", "right",
           fixed = 0f to 100f),
)

val METRIC_KEYS: List<String> = METRICS.map { it.key }
val METRIC_INFO: Map<String, Metric> = METRICS.associateBy { it.key }

// A selected metric is written in its own colour, a little brighter than the
// curve, so it stays readable on the tinted background.
private val METRIC_BRIGHT = mapOf(
    "voltage_v" to Color(0xFF62A0EA),
    "current_mA" to Color(0xFFF66151),
    "power_w" to Color(0xFFC061CB),
    "temp_c" to Color(0xFFF5C211),
    "capacity" to Color(0xFF57E389),
)

fun metricBright(key: String): Color =
    METRIC_BRIGHT[key] ?: METRIC_INFO.getValue(key).color

// metrics selected the first time the app runs (no saved preferences yet)
val DEFAULT_METRICS = listOf("voltage_v", "current_mA")

// 指标 buttons and the curves' Y axes: the full English names are wide enough
// to eat into the plot, so both use a short form -- the button takes the unit,
// the axis takes the standard quantity symbol (IEC for the electrical ones),
// with the unit written under it as before.
private val METRIC_BTN_EN = mapOf(
    "voltage_v" to "V", "current_mA" to "mA", "power_w" to "W",
    "temp_c" to "°C", "capacity" to "%",
)
private val METRIC_AXIS_EN = mapOf(
    "voltage_v" to "U", "current_mA" to "I", "power_w" to "P",
    "temp_c" to "T", "capacity" to "SOC",
)

fun metricButtonLabel(m: Metric): String =
    if (Strings.effective == Lang.EN) METRIC_BTN_EN[m.key] ?: m.name else m.name

/** The tag drawn next to a curve's Y axis. */
fun metricAxisLabel(m: Metric): String =
    if (Strings.effective == Lang.EN) METRIC_AXIS_EN[m.key] ?: m.name else m.name

// ---- chart windows and the sampling rate ------------------------------------
val WINDOWS = listOf(
    "30s" to 30, "1min" to 60, "2min" to 120, "5min" to 300,
    "10min" to 600, "30min" to 1800, "1h" to 3600,
    "2h" to 7200, "4h" to 14400, "8h" to 28800,
    "12h" to 43200, "18h" to 64800, "24h" to 86400,
    "36h" to 129600, "48h" to 172800,
)

val WINDOW_SECS: Set<Int> = WINDOWS.map { it.second }.toSet()

/** Formatting for the whole UI: the axis ticks are always ASCII dotted. */
fun fmt(pattern: String, value: Double): String =
    String.format(Locale.US, pattern, value)
