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
    "限制充电" to "Limit charging",
    "达上限停止充电，降到下限恢复充电，区间滞回" to "Upper stops, lower resumes, holds between",
    "上限" to "Upper limit",
    "下限" to "Lower limit",
    "禁止休眠" to "Inhibit sleep",
    "系统不休眠，保持网络在线" to "No sleep, the network stays up",
    "实时采集" to "Live data",
    "图形化" to "Chart",
    "图形化已关闭" to "The chart is off",
    "实时采集已关闭" to "Live data is off",
    "窗口" to "Window",
    "采样间隔" to "Interval",
    // status table
    "电源" to "Power",
    "USB类型" to "USB",
    "电压(V)" to "Voltage",
    "功率(W)" to "Power",
    "电流" to "Current",
    "温度(°C)" to "Temp",
    // ... and the bare names, the 通知 page's group headings
    "电压" to "Voltage",
    "功率" to "Power",
    "温度" to "Temperature",
    // Android publishes the gauge's own counter, never charge_full: the row
    // says what the two numbers really are, and the ⓘ next to them says what
    // the first one is not
    "统计/设计容量(mAh)" to "Stats / design (mAh)",
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
    // the header switches: background, then language
    "背景" to "Background",
    "语言" to "Language",
    "暗色" to "Dark",
    "亮色" to "Light",
    "跟随系统" to "Follow system",
    // root-only controls (the GTK app talks to a root daemon; Android has no
    // way to write the charger's sysfs without one)
    "未 root" to "no root",
    "仅提供状态" to "status only",

    "健康度" to "Health",
    "健康度说明" to "About health",
    "健康度是系统上报的电池状态，不是磨损百分比：\n" to
        "The battery state the system reports, not a wear percentage:\n",
    "磨损要算 充满容量/设计容量，而 Android 不发布 充满容量" to
        "wear is charge_full over charge_full_design, and Android publishes" +
        " no charge_full",
    "良好" to "Good",
    "过热" to "Overheat",
    "损坏" to "Dead",
    "过压" to "Over voltage",
    "故障" to "Failure",
    "过冷" to "Cold",
    // the app's two pages, side by side in the header, and 设置 at the far
    // right of it.  通知 is the page the app opens on, which the GTK app has no
    // counterpart for yet: its own master switch, one switch per notification,
    // the number each fires at, and how each one arrives.  高级 is the panel the
    // GTK app draws.
    "通知" to "Notifications",
    "高级" to "Advanced",
    "基础功能" to "Base",
    "设置" to "Settings",
    "返回" to "Back",
    "通知开关" to "Notifications",
    "通知方式" to "Notify by",
    "横幅" to "Banner",
    "语音" to "Voice",
    "充电完成" to "Charging complete",
    "电量过低" to "Battery low",
    "电源连接" to "Power connected",
    "电源断开" to "Power disconnected",
    // ... and the short words the rows wear under their group's heading
    "连接" to "Connected",
    "断开" to "Disconnected",
    "过高" to "High",
    "过低" to "Low",
    "充电过高" to "Charge high",
    "放电过高" to "Discharge high",
    "充电" to "Charging",
    "温度过高" to "Too hot",
    "温度过低" to "Too cold",
    "电压过高" to "Voltage high",
    "电压过低" to "Voltage low",
    "充电电流过高" to "High charge current",
    "放电电流过高" to "High discharge current",
    "功率过高" to "High power",
    // the four numbers the notifications fire at, each its own
    "达" to "at",
    "低于" to "below",
    "高于" to "above",
    // how often a voice says it, and the one that never stops on its own
    "次数" to "Times",
    "间隔" to "Interval",
    "直到电源断开" to "until power off",
    "1次" to "1×",
    "2次" to "2×",
    "3次" to "3×",
    "5次" to "5×",
    "10次" to "10×",
    "直到开始充电" to "until charging",
    // ... and the two screens a notification needs the system for: the
    // channel's banner and sound, and the vendor's autostart list
    "各厂商的设置位置不一样，下面的按钮带你去找" to "Every vendor files these in a different place; the buttons below take you there",
    "自启动" to "Autostart",
    "电池优化" to "Battery optimization",
    "精确闹钟" to "Exact alarms",
    "允许 chargecap 在后台继续运行" to "Let chargecap keep running in the background",
    "已允许后台运行" to "Background running allowed",
    "允许系统闹钟拉起监控" to "Let the system alarm restart the monitor",
    "已允许" to "Allowed",
    "最近任务里锁定 chargecap；并在手机管家的应用启动管理中打开自启动、关联启动和后台活动" to
        "Lock chargecap in the recent tasks, and enable autostart, associated start and background activity in the vendor's app launch settings",
    "让 chargecap 开机后自己起来" to "Let chargecap start itself after a reboot",
    // 设置's 关于: four lines, and a copy of them
    "关于" to "About",
    "版本" to "Version",
    "作者" to "Author",
    "更新" to "Updates",
    "隐私" to "Privacy",
    "不联网、不收集任何数据" to "No network, no data collected",
    // the ongoing notification of the background monitor
    "由于通知需要，后台运行中" to
        "Running in the background so notifications can arrive",
    "后台运行" to "Background running",
    "通知开关打开时保持后台运行" to
        "Keeps running in the background while notifications are on",
    "没有打开的通知项" to "No notifications are switched on",
    "通知横幅与声音" to "Banners and sound",
    "在通知设置里放开横幅和声音" to "Turn the banner and the sound on in the notification settings",
    "打开" to "Open",
    // the dialog 通知开关 opens with when the system would swallow the reminder
    "提醒可能收不到" to "The reminder may not arrive",
    "系统通知没有打开，横幅和声音都不会出现" to "System notifications are off, so there is no banner and no sound",
    "系统可能在后台关掉它：自启动与省电白名单" to "The system may stop it in the background: autostart and the battery exemption",
    "去设置" to "Go to settings",
    "知道了" to "Got it",
    // the sleep record under 禁止休眠: a number the app keeps, not a reminder
    "次" to "×",
    "自 %s 起" to "since %s",
    "还没有休眠" to "no sleep yet",
    "最近 %s，%s" to "latest %s, %s",
    "睡了 %d 分钟" to "slept %d min",
    "睡了 %d 小时 %d 分钟" to "slept %d h %d min",
    "休眠记录" to "Sleep log",
    "还没开启禁止休眠" to "sleep has never been inhibited",
    // the notification channel's own name and description, the two lines the
    // system's 通知 page shows above 横幅 / 声音
    "充电提醒" to "Charging alerts",
    "电量、温度、电压、电流或功率越过你设的线时提醒" to "When the charge, the temperature, the voltage, the current or the power crosses the line you set",
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
    /** 限制充电 / 禁止休眠 and the 电源 row's own values: a size up. */
    val big: Float,
    /**
     * The two switch titles.  A step above `big` in English, where the 电源 row
     * has no room for it (five things on one phone-screen-wide row) but the
     * switch rows have plenty.
     */
    val heading: Float,
)

val SCALE = mapOf(
    "zh" to Scale(title = 11f, key = 11f, small = 11f, value = 11f,
                  sub = 11f, spin = 11f, btn = 28f, big = 13f, heading = 13f),
    "en" to Scale(title = 10f, key = 10f, small = 10f, value = 10f,
                  sub = 10f, spin = 10f, btn = 26f, big = 11f, heading = 13f),
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
    "15s" to 15, "30s" to 30, "1min" to 60, "2min" to 120, "5min" to 300,
    "10min" to 600, "30min" to 1800, "1h" to 3600,
    "2h" to 7200, "4h" to 14400, "8h" to 28800,
    "12h" to 43200, "18h" to 64800, "24h" to 86400,
    "36h" to 129600, "48h" to 172800,
)

val WINDOW_SECS: Set<Int> = WINDOWS.map { it.second }.toSet()

// ---- the chart's recording interval -----------------------------------------
// How often a sample is stored, independent of the panel's own 500 ms readout:
// the panel is a live number, this is the resolution of the history behind the
// curve.  The buffer holds a fixed number of samples, so a faster interval buys
// detail and spends reach -- 0.01 s keeps about an hour, 20 s keeps weeks.
val SAMPLES = listOf(
    "0.01s" to 10, "0.03s" to 30, "0.05s" to 50, "0.1s" to 100,
    "0.3s" to 300, "0.5s" to 500, "1s" to 1000, "2s" to 2000,
    "3s" to 3000, "5s" to 5000, "10s" to 10000, "15s" to 15000,
    "20s" to 20000,
)

val SAMPLE_MS: Set<Int> = SAMPLES.map { it.second }.toSet()

/** What a fresh install records at: the same rate the panel reads at. */
const val DEFAULT_SAMPLE_MS = 500

/** The interval a stored millisecond value stands for, or the default. */
fun sampleMs(stored: Int): Int = if (stored in SAMPLE_MS) stored else DEFAULT_SAMPLE_MS

fun sampleLabel(ms: Int): String =
    SAMPLES.firstOrNull { it.second == ms }?.first ?: "0.5s"

/** Formatting for the whole UI: the axis ticks are always ASCII dotted. */
fun fmt(pattern: String, value: Double): String =
    String.format(Locale.US, pattern, value)
