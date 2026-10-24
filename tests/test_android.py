# ---------------------------------------------------------------------------
# chargecap - keep an always-plugged-in phone inside a charge window
#
# Licence: General Pleasure League (GPL) 1.0
#          https://github.com/fanzu8/General-Pleasure-League
#
#          You are the general of your own life, the master of your own fate:
#          no restrictions, no compulsions - use it, change it, share it, and
#          let pleasure be your primary guide.  Just be happy.
# ---------------------------------------------------------------------------

"""Static checks on the Android port.

The Android app is Kotlin, so it cannot be run here any more than the GTK app
can; these tests read its sources instead and hold it to the desktop app -- the
same metrics, the same windows, the same numbers, the same words -- plus the
few places where Android genuinely cannot follow (the charging control needs
root, and there is no charge_full).
"""
import ast
import os
import re
import unittest

from tests.helpers import ROOT, gui_constant, gui_tree

ANDROID = os.path.join(ROOT, "android")
MAIN = os.path.join(ANDROID, "app", "src", "main")
KOTLIN = os.path.join(MAIN, "kotlin", "org", "chargecap", "android")

SOURCES = ("Strings.kt", "Battery.kt", "Chart.kt", "AppState.kt", "Rules.kt",
           "Pages.kt", "Panel.kt", "MainActivity.kt", "Notifications.kt",
           "MonitorService.kt", "BootReceiver.kt", "Watchdog.kt",
           "RestartReceiver.kt", "PowerReceiver.kt", "Prefs.kt", "Sleep.kt",
           "SystemSettings.kt", "Theme.kt", "Voice.kt")

# the strings the Android UI needs and the GTK app has no counterpart for:
# Android reports the port it is plugged into (AC / USB / wireless / dock)
# rather than the Linux charger's SDP / DCP / CDP handshake, it publishes the
# battery's health instead of charge_full, and the controls that need root say
# so.
ANDROID_ONLY = {
    # the gauge's counter, and the two ⓘ that explain what the rows hold
    "统计/设计容量(mAh)",
    "电量计说明",
    "电量计累计流过的电荷，不是剩余电量：\n",
    "· 与上面的电量百分比无关\n",
    "· 部分机型（本机就是）满电时会复位\n",
    "· 方向与量纲都可能不准；可靠的是它的变化速度，也就是电流",
    "健康度说明",
    "健康度是系统上报的电池状态，不是磨损百分比：\n",
    "磨损要算 充满容量/设计容量，而 Android 不发布 充满容量",
    # Android reports the port it is plugged into, not SDP / DCP / CDP
    "无线",
    "AC：充电头\n",
    "USB：电脑或充电宝的 USB 口\n",
    "无线：无线充电板\n",
    # the controls need root, and the health comes as a state, not a percentage
    "未 root",
    "仅提供状态",
    "良好",
    "过热",
    "损坏",
    "过压",
    "故障",
    "过冷",
    # the dialog 通知开关 opens with when the system would swallow the reminder
    "提醒可能收不到",
    "系统通知没有打开，横幅和声音都不会出现",
    "系统可能在后台关掉它：自启动与省电白名单",
    "去设置",
    # 设置, the two switches only the system owns, each a row out of the app
    "返回",
    # ... and the screens only the system owns: the channel's banner and sound,
    # and the vendor's autostart list, which the app cannot switch itself
    "各厂商的设置位置不一样，下面的按钮带你去找",
    "通知横幅与声音",
    "在通知设置里放开横幅和声音",
    "自启动",
    "让 chargecap 开机后自己起来",
    "电池优化",
    "允许 chargecap 在后台继续运行",
    "已允许后台运行",
    "SCHEDULE_EXACT_ALARM 权限",
    "允许系统定时唤醒 chargecap",
    "已允许",
    "最近任务里锁定 chargecap；并在手机管家的应用启动管理中打开自启动、关联启动和后台活动",
    "打开",
    # the background pace the notification page promises
    "后台每 30 秒检查一次；需要连续判断请到高级打开禁止休眠",
    # the notification channel: the row the system's 通知 page hinges on
    "充电提醒",
    "电量、温度、电压、电流或功率越过你设的线时提醒",
    # the ongoing notification of the foreground monitor
    "由于通知需要，后台运行中", "后台运行",
    "通知开关打开时保持后台运行", "没有打开的通知项",
}

# the shared vocabulary: rename a label on one side and the other has to
# follow, so both panels keep reading the same way
SHARED = (
    # 通知: both apps carry the same notifications, the same words and the
    # same two ways of arriving, so the vocabulary is shared now
    "通知", "高级", "通知开关", "通知方式", "次数", "间隔",
    "横幅", "语音",
    "充电完成", "电量过低", "温度过高", "温度过低", "放电电流过高",
    "电源连接", "电源断开", "电压过高", "电压过低", "充电电流过高",
    "功率过高",
    "连接", "断开", "过高", "过低", "充电过高", "放电过高",
    # the groups the page reads in: the charge, the plug and the charging
    # state, then one per kind of reading
    "基础功能", "电源", "充电", "温度", "电压", "电流", "功率",
    "达", "低于", "高于",
    "1次", "2次", "3次", "5次", "10次",
    "直到开始充电", "直到电源断开",
    # 关于: the same four lines on both sides, and a copy of them
    "设置", "关于", "版本", "作者", "更新", "隐私",
    "不联网、不收集任何数据",
    # the sleep record under 禁止休眠: a number the app keeps, not a reminder
    "次", "休眠记录", "还没开启禁止休眠",
    "自 %s 起", "还没有休眠", "最近 %s，%s",
    "睡了 %d 分钟", "睡了 %d 小时 %d 分钟",
    "知道了",
    "限制充电", "达上限停止充电，降到下限恢复充电，区间滞回", "上限", "下限",
    "禁止休眠", "系统不休眠，保持网络在线", "窗口", "实时采集", "图形化",
    "图形化已关闭", "实时采集已关闭",
    "背景", "语言", "暗色", "亮色", "跟随系统", "采样间隔", "健康度",
    "电源", "USB类型", "电压(V)", "功率(W)", "电流", "温度(°C)",
    "极值", "最大", "限制", "已连接", "未连接", "充电中", "未充电", "未知",
    "现在", "选择上方指标以显示曲线", "USB 类型说明",
    "未知：未识别，通常是没插线", "跟随系统",
)

# the GTK app writes its tick formats as Python format specs; Kotlin has only
# printf's, so the two are compared through this translation
FORMATS = {"{:.3f}": "%.3f", "{:+.0f}": "%+.0f", "{:.2f}": "%.2f",
           "{:.1f}": "%.1f", "{:.0f}": "%.0f"}


def read(path, *parts):
    with open(os.path.join(path, *parts)) as f:
        return f.read()


def kotlin(name):
    return read(KOTLIN, name)


def all_kotlin():
    return "\n".join(kotlin(name) for name in SOURCES)


def code_only(src):
    """The source with its comments taken out (a comment may name anything)."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(re.sub(r"//.*$", "", line) for line in src.split("\n"))


def unescape(text):
    """A Kotlin (or Python) string literal as its value."""
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1),
                                                                m.group(1)),
                  text)


def en_table():
    """The EN map of Strings.kt, as {source: translation}."""
    body = re.search(r"private val EN = mapOf\((.*?)\n\)", kotlin("Strings.kt"),
                     re.S).group(1)
    return {unescape(src): unescape(dst) for src, dst in re.findall(
        r'"((?:[^"\\]|\\.)*)"\s+to\s+"((?:[^"\\]|\\.)*)"', body)}


def asked_strings():
    """Every string the Kotlin UI translates with tr()."""
    used = set()
    for name in SOURCES:
        for text in re.findall(r'tr\("((?:[^"\\]|\\.)*)"\)', kotlin(name)):
            used.add(unescape(text))
    return used


def metric_table():
    """METRICS from Strings.kt, as dicts (the Kotlin Metric dataclass)."""
    block = re.search(r"val METRICS = listOf\((.*?)\n\)", kotlin("Strings.kt"),
                      re.S).group(1)
    out = []
    for m in re.finditer(
            r'Metric\("(\w+)", "([^"]+)", "([^"]+)", Color\(0x([0-9A-Fa-f]{8})\),'
            r' "([^"]*)", "(\w+)"(?:,\s*fixed = ([\d.]+)f to ([\d.]+)f)?\)',
            block):
        key, name, unit, colour, fmt, side, lo, hi = m.groups()
        out.append({
            "key": key, "name": name, "unit": unit,
            "colour": "#" + colour[2:].lower(), "format": fmt, "side": side,
            "fixed": (float(lo), float(hi)) if lo else None,
        })
    return out


def kotlin_constant(name):
    """A val/const declared in one of the Kotlin sources."""
    for source in SOURCES:
        m = re.search(
            r"(?:const )?(?:val|var) %s(?:\s*:\s*[\w<>?.]+)?\s*=\s*([\d.]+)"
            % name, kotlin(source))
        if m:
            return float(m.group(1))
    raise AssertionError(f"{name} is not declared in any of {SOURCES}")


def gui_class_constant(name):
    """A constant that lives inside a GTK class body (LiveChart.TICKS, say)."""
    for node in ast.walk(gui_tree()):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not assigned anywhere in the GUI")


class SourceTest(unittest.TestCase):
    """A small helper, so a failure names the missing fragment instead of
    printing the whole file."""

    def assertHas(self, src, fragment, where=""):
        self.assertTrue(fragment in src,
                        f"{where or 'source'}: {fragment!r} not found")

    def assertLacks(self, src, fragment, where=""):
        self.assertFalse(fragment in src,
                         f"{where or 'source'}: {fragment!r} is there")


class StringsTest(SourceTest):
    def setUp(self):
        self.en = en_table()

    def test_every_string_the_ui_asks_for_has_an_english_entry(self):
        missing = sorted(s for s in asked_strings() if s not in self.en)
        self.assertEqual(missing, [], f"untranslated: {missing}")

    def test_no_stale_entries(self):
        """An entry nobody asks for is dead weight (or a renamed string)."""
        used = asked_strings()
        unused = sorted(k for k in self.en if k not in used)
        self.assertEqual(unused, [], f"unused entries: {unused}")

    def test_shared_strings_match_the_gtk_app(self):
        """The two UIs say the same thing in the same words: every string both
        apps show has the same English translation on both sides."""
        gtk = gui_constant("EN")
        for key in SHARED:
            with self.subTest(key):
                self.assertIn(key, gtk, f"the GTK app lost {key}")
                self.assertIn(key, self.en, f"the Android app lost {key}")
                self.assertEqual(self.en[key], gtk[key])

    def test_only_the_documented_android_extras_are_added(self):
        """The strings Android needs and the GTK app does not are a short,
        deliberate list -- an accidental extra one is a typo somewhere."""
        gtk = gui_constant("EN")
        extra = {k for k in self.en if k not in gtk}
        self.assertEqual(sorted(extra), sorted(ANDROID_ONLY))

    def test_the_ui_follows_the_system_unless_overridden(self):
        """Three choices, like the GTK app: auto / Chinese / English."""
        src = kotlin("Strings.kt")
        self.assertHas(src, "Locale.getDefault().language")
        for tag in ("auto", "zh", "en"):
            self.assertHas(src, f'"{tag}"')
        self.assertHas(src, "if (lang == Lang.AUTO) system() else lang")

    def test_the_type_scale_is_the_gtk_apps(self):
        """English is the wider language, so its table is set a point smaller
        (the same SCALE numbers the GTK app uses, now in sp)."""
        scale = gui_constant("SCALE")
        src = kotlin("Strings.kt")
        for key in ("title", "key", "small", "value", "sub", "spin", "big",
                    "heading"):
            for lang in ("zh", "en"):
                with self.subTest(lang=lang, key=key):
                    self.assertHas(src, f"{key} = {scale[lang][key]:g}f")
        # ... which is the whole point of the scale
        self.assertLess(scale["en"]["value"], scale["zh"]["value"])


class MetricTest(SourceTest):
    def setUp(self):
        self.gtk = gui_constant("METRICS")
        self.android = metric_table()

    def test_metrics_match_the_gtk_app(self):
        """Key, name, unit, colour, tick format, axis side and the fixed range
        are the GTK app's, one for one: the two charts draw the same picture."""
        self.assertEqual(len(self.android), len(self.gtk),
                         [m["key"] for m in self.android])
        for mine, theirs in zip(self.android, self.gtk):
            key, name, unit, colour, fmt, side, fixed = theirs
            with self.subTest(metric=key):
                self.assertEqual(mine["key"], key)
                self.assertEqual(mine["name"], name)
                self.assertEqual(mine["unit"], unit)
                self.assertEqual(mine["colour"], colour.lower())
                self.assertEqual(mine["format"], FORMATS[fmt])
                self.assertEqual(mine["side"], side)
                self.assertEqual(mine["fixed"], fixed)

    def test_button_and_axis_abbreviations_match_the_gtk_app(self):
        src = kotlin("Strings.kt")
        for table in ("METRIC_BTN_EN", "METRIC_AXIS_EN", "METRIC_BRIGHT"):
            for key, text in gui_constant(table).items():
                with self.subTest(table=table, key=key):
                    self.assertHas(src, f'"{key}" to ')

    def test_the_english_abbreviations_are_the_gtk_apps(self):
        """Short on purpose: the button takes the unit, the axis the quantity
        symbol, because the full names eat into the plot."""
        src = kotlin("Strings.kt")
        for key, text in gui_constant("METRIC_BTN_EN").items():
            self.assertHas(src, f'"{key}" to "{text}"')
        for key, text in gui_constant("METRIC_AXIS_EN").items():
            self.assertHas(src, f'"{key}" to "{text}"')

    def test_the_default_selection_is_the_gtk_apps(self):
        self.assertEqual(tuple(gui_constant("DEFAULT_METRICS")),
                         ("voltage_v", "current_mA"))
        self.assertHas(kotlin("Strings.kt"),
                       'listOf("voltage_v", "current_mA")')


class ChartTest(SourceTest):
    def test_windows_match_the_gtk_app(self):
        block = re.search(r"val WINDOWS = listOf\((.*?)\n\)",
                          kotlin("Strings.kt"), re.S).group(1)
        mine = [(label, int(secs)) for label, secs in re.findall(
            r'"([^"]+)" to (\d+)', block)]
        self.assertEqual(mine, [tuple(w) for w in gui_constant("WINDOWS")])

    def test_the_recording_intervals_match_the_gtk_app(self):
        """Both front ends offer the same intervals for the chart's history, and
        the default is the rate the panel itself reads at."""
        def table(src, start, stop):
            """The (label, milliseconds) pairs of a front end's own table."""
            block = src[src.index(start):].split(stop)[0]
            # Kotlin writes "0.01s" to 10, Python ("0.01s", 10)
            pairs = re.findall(r'"(\d+(?:\.\d+)?)s"(?: to |, )(\d+)', block)
            return [(label + "s", int(ms)) for label, ms in pairs]

        android = table(kotlin("Strings.kt"), "val SAMPLES = listOf", "\n)")
        gtk = table(read(ROOT, "chargecap"), "SAMPLES = (", "\n\n")
        self.assertEqual(android, gtk, "the two interval tables differ")
        self.assertEqual(android[0], ("0.01s", 10))
        self.assertEqual(android[-1], ("20s", 20000))
        self.assertEqual(len(android), 13)
        self.assertIn(("0.5s", 500), android)
        # a fresh install records at the panel's own rate, in both apps
        self.assertIn("const val DEFAULT_SAMPLE_MS = 500", kotlin("Strings.kt"))
        self.assertIn("SAMPLE_MS = 500", read(ROOT, "chargecap"))
        self.assertIn('store.getInt("sample_ms", DEFAULT_SAMPLE_MS)',
                      kotlin("Prefs.kt"))
        self.assertIn('.get("sample_ms")', read(ROOT, "chargecap"))

    def test_the_two_front_ends_lay_their_cells_out_alike(self):
        """A row's key-value cell starts at the same x in every row, which is
        what the GTK app's COL_FRACS buys it -- and what the Android panel lost
        when each row picked its own weights (温度 and 功率 did not line up)."""
        panel = kotlin("Panel.kt")
        self.assertHas(panel, "private const val COL_FIRST = 0.312f")
        self.assertHas(panel, "private fun RowScope.KeyedCell(")
        self.assertEqual(panel.count("weight(COL_FIRST)"), 2,
                         "the USB row and the voltage row share the first column")
        self.assertEqual(panel.count("KeyedCell("), 3, "two uses and the definition")
        self.assertEqual(gui_constant("COL_FRACS")[0], 0.312)

    def test_the_recording_interval_sits_on_the_power_row(self):
        """电源's three values hug the left (the gaps between them were doing
        nothing) and the interval takes the room they free -- the chart row is
        left with 窗口, as it was."""
        panel = kotlin("Panel.kt")
        status = re.search(r"fun StatusRows\(.*?\n    }\n}", panel, re.S).group(0)
        self.assertHas(status, 'tr("采样间隔")', "电源 row")
        self.assertHas(status, "ChipPicker(", "电源 row")
        self.assertHas(status, "Spacer(Modifier.weight(1f))", "电源 row")
        # the three values are packed, not spread over equal weights
        self.assertLacks(status, "Modifier.weight(1f))\n            ChargedValue")
        chart = re.search(r"fun ChartRows\(.*?\n    }\n}", panel, re.S).group(0)
        self.assertHas(chart, 'tr("窗口")', "chart row")
        self.assertLacks(chart, "SAMPLES", "the interval left the chart row")

    def test_the_power_row_hugs_its_title_and_is_bold(self):
        """电源's values start right after the title (no 68dp gutter) and the
        two states carry the title's own weight."""
        panel = kotlin("Panel.kt")
        self.assertHas(panel, 'StatusRow(tr("电源"), fitTitle = true, titleSize = sc.big)')
        status = re.search(r"fun StatusRows\(.*?\n    }\n}", panel, re.S).group(0)
        self.assertEqual(status.count("bold = true"), 2, "plugged and charging")
        self.assertHas(panel, "fontWeight = if (bold) FontWeight.Bold")
        gtk = read(ROOT, "chargecap")
        # the two switch titles are plain bold text: no chip behind them, so
        # the only rule left naming them is the size and weight one
        self.assertHas(gtk, '"row.switch-row.compact-status label.title"')
        self.assertEqual(gtk.count("row.switch-row.compact-status label.title"), 1)
        self.assertHas(gtk, "label.sample-value { font-weight: 400; }")
        self.assertHas(gtk, "def _capacity_row(self):")
        self.assertHas(gtk, 'box.append(key_label(_("健康度")))')
        self.assertHas(gtk, 'self.f["charge_full"] = full')
        self.assertHas(gtk, 'val.add_css_class("bold-label")')

        self.assertHas(gtk, ".bold-label { font-weight: 700; }")

    def test_the_interval_chip_is_raised_and_its_caption_bold(self):
        """The recording interval reads as a control: a bold caption and a chip
        with a shadow -- and a shade lighter, because a black shadow is
        invisible on a dark panel."""
        panel = kotlin("Panel.kt")
        self.assertHas(panel, 'KeyChip(tr("采样间隔"), null, sc.value, raised = true)')
        self.assertHas(panel, "raised = true,")
        self.assertHas(panel, "shadow: Dp = 0.dp,")
        self.assertHas(panel, "raised: Boolean = false,")
        # a candidate row is one line of plain text 24dp tall: Material's own
        # item reserves 48dp, which thirteen candidates turned into most of a
        # phone screen, and a one-line row with no room at all read as too tight
        self.assertLacks(panel, "DropdownMenuItem(")
        self.assertHas(
            panel,
            "private fun MenuRow(text: String, selected: Boolean, onClick: () -> Unit) {")
        self.assertHas(panel, "heightIn(min = 24.dp)")
        # the text in a menu carries no weight of its own, title included
        self.assertHas(panel, "text,\n        fontSize = 11.sp,\n        fontWeight = FontWeight.Normal,")
        self.assertHas(panel, "fontWeight = FontWeight.Normal,\n        color = MaterialTheme.colorScheme.onSurface.copy(\n            alpha = if (selected) 1f else 0.85f),")
        # both lists in the GTK app are the same popover of ticked choices, and
        # both go in a scroller: without one the window's sixteen rows never
        # appeared at all
        gtk = read(ROOT, "chargecap")
        self.assertHas(gtk, "def choice_popover(items, current, on_pick, max_height=420):")
        self.assertHas(gtk, "pop = choice_popover(SAMPLES, SAMPLE_MS_CHOICE, self._on_sample,")
        self.assertHas(gtk, "[(label, secs) for label, secs in WINDOWS],")
        self.assertHas(gtk, "self.chart.window_secs, self._on_window_picked, max_height=420)")
        # the chip sits at the foot of the panel, so its list opens upwards
        self.assertHas(gtk, "btn.set_direction(Gtk.ArrowType.UP)")
        # no radio circles left, and no stock dropdown either
        self.assertLacks(gtk, "Gtk.CheckButton(label=label)")
        self.assertLacks(gtk, "Gtk.DropDown.new_from_strings(")
        # a choice is one line in a row the height of the checkbutton it replaced
        self.assertHas(gtk, "popover button.choice {")
        self.assertHas(gtk, "min-height: 28px; min-width: 0px; padding: 0px 6px; margin: 0px;")
        self.assertHas(gtk, "min-height: 0px; padding: 0px; font-weight: 400;")
        # the tick is moved when a row is picked, not baked in at build time:
        # the list is reopened after every choice, so the old tick went stale
        self.assertHas(gtk, '("\\u2713 " if value == chosen else "   ") + text')
        self.assertHas(gtk, "tick(value)")
        # 限制充电 / 禁止休眠 are plain bold text: the chip behind them, which
        # read as a shadow around the words, is gone.  电源 keeps its own
        self.assertLacks(panel, "KeyChip(title, null, s.heading)")
        self.assertEqual(gtk.count("row.switch-row.compact-status label.title"), 1)
        self.assertHas(panel, "alpha = if (raised) 0.16f else 0.10f")
        self.assertHas(panel, ".shadow(shadow, shape)")
        # the GTK app's interval is a compact chip carrying the same chevron
        gtk = read(ROOT, "chargecap")
        self.assertHas(gtk, "def _sample_button(self):")
        self.assertHas(gtk, 'self._sample_label = Gtk.Label(label=sample_label() + "  \\u25be")')
        self.assertHas(gtk, 'caption.add_css_class("sample-caption")')
        self.assertHas(gtk, "label.sample-caption { font-weight: 700;")

    def test_the_window_list_starts_at_fifteen_seconds(self):
        self.assertIn('"15s" to 15, "30s" to 30', kotlin("Strings.kt"))
        self.assertIn('("15s", 15), ("30s", 30),', read(ROOT, "chargecap"))

    def test_the_panel_and_the_chart_run_on_two_clocks(self):
        """The panel publishes at 500 ms and the rules judge at 3 s; the chart,
        while it records, may read faster at its own interval.  With the chart
        off, a 0.01 s setting must not turn the phone into a 100 Hz reader, and
        a 20 s one must not freeze the numbers."""
        battery = kotlin("Battery.kt")
        self.assertHas(battery, "var intervalMs: Long = SAMPLE_MS")
        self.assertHas(battery, "val due = storeDue || now - storedAt >= intervalMs")
        self.assertHas(battery, "fun resetStore() {")
        self.assertHas(battery, "if (now - publishedAt >= SAMPLE_MS)")
        self.assertHas(battery, "delay(readMs)")
        self.assertHas(battery, "const val RULES_MS = 3000L")
        # the chart's clock is set from the state; the reader follows it only
        # while the chart records
        self.assertHas(battery, "Monitor.intervalMs = chartMs")
        self.assertHas(battery,
                       "if (chart) minOf(Monitor.SAMPLE_MS, prefs.sampleMs.toLong())")
        self.assertHas(kotlin("Prefs.kt"), 'store.getInt("sample_ms", DEFAULT_SAMPLE_MS)')

    def test_the_curve_has_a_live_head(self):
        """The stored samples may be 20 s apart; the curve still has to move at
        the page's 500 ms, so the live reading is drawn as its head."""
        chart = kotlin("Chart.kt")
        self.assertHas(chart, "tipState: State<Snapshot>,")
        # the head is part of the range, not clamped into a stale one: after
        # an interval change the old range pinned it until the next sample
        self.assertHas(chart, "val liveValue = snapshotValue(tip, m.key)")
        self.assertHas(chart, "if (liveValue < lo) lo = liveValue")
        self.assertHas(chart, "if (liveValue > hi) hi = liveValue")
        self.assertHas(chart, "val head = snapshotValue(tip, m.key)?.takeIf { !it.isNaN() }")
        self.assertLacks(chart, "coerceIn(lo, hi)")
        # a dot at the right edge, not the path's last point: joining it drew
        # one straight line across the whole interval
        self.assertLacks(chart, "xs[count] = pw")
        self.assertHas(chart, "if (count == 0 && head == null) continue")
        self.assertHas(chart, "if (count > 0) {")
        self.assertHas(chart, "drawCircle(m.color")
        # the State is read inside the draw scope, so the 500 ms publisher --
        # not the next stored sample -- invalidates the canvas
        self.assertHas(chart, "val tip = tipState.value")
        panel = kotlin("Panel.kt")
        self.assertHas(panel, "tipState: State<Snapshot>,")
        self.assertHas(panel, "tipState = tipState,")
        self.assertHas(kotlin("Pages.kt"),
                       "LiveSection(state, snapshot, snapshotState)")
        self.assertHas(kotlin("Pages.kt"),
                       "val snapshotState = state.samples.collectAsState()")

    def test_sample_rate_and_history_match_the_gtk_app(self):
        """Half a second per sample and a 48 hour history: the Android ring
        buffer holds the same span as the GTK app's arrays."""
        self.assertEqual(kotlin_constant("SAMPLE_MS"), 500.0)
        self.assertEqual(gui_constant("SAMPLE_MS"), 500)
        self.assertHas(all_kotlin(), "48 * 3600 * 1000L / SAMPLE_MS + 16")
        # the GTK app computes the same number, from the same two constants
        self.assertHas(read(ROOT, "chargecap"),
                       "MAX_SAMPLES = 48 * 3600 * 1000 // SAMPLE_MS + 16")

    def test_chart_height_is_the_gtk_apps(self):
        self.assertEqual(kotlin_constant("CHART_HEIGHT"), 139.0)
        m = re.search(r"self\.set_size_request\(-1, (\d+)\)",
                      read(ROOT, "chargecap"))
        self.assertEqual(int(m.group(1)), 139)

    def test_grid_and_axis_geometry_match_the_gtk_app(self):
        src = kotlin("Chart.kt")
        self.assertHas(src, "PTS_PER_PX = 2")
        self.assertHas(src, "GRID_DIVS = 5")
        self.assertHas(src, "floatArrayOf(0f, 0.25f, 0.5f, 0.75f, 1f)")
        # the axis columns are measured from what they draw, not fixed
        self.assertHas(src, "fun columnWidth(m: Metric): Float")
        self.assertHas(src, "val widths = sel.associate { it.key to columnWidth(it) }")
        self.assertLacks(src, "colW")
        self.assertHas(src, "0.6.dp")           # curve thickness
        self.assertHas(src, "0.5.dp")           # grid, thinner than the curve
        self.assertEqual(gui_class_constant("TICKS"),
                         (0.0, 0.25, 0.5, 0.75, 1.0))
        self.assertEqual(gui_class_constant("GRID_DIVS"), 5)
        self.assertEqual(gui_class_constant("PTS_PER_PX"), 2)
        # ... and the GTK chart does the same, with no fixed column
        gtk = read(ROOT, "chargecap")
        self.assertIn("def _column_width(self, cr, key, rng):", gtk)
        self.assertNotIn("COL_W", gtk)
        self.assertLess(gui_class_constant("GRID_W"),
                        gui_class_constant("LINE_W"))

    def test_a_flat_curve_gets_the_same_fallback_range(self):
        """Both charts open a flat signal out to +-0.5, so it is not a hairline
        on an invisible axis."""
        src = kotlin("Chart.kt")
        self.assertHas(src, "if (b - a < 1e-9f) {")
        self.assertHas(src, "a -= 0.5f")
        self.assertHas(src, "b += 0.5f")

    def test_time_labels_use_the_gtk_apps_format(self):
        src = kotlin("Chart.kt")
        self.assertHas(src, 'tr("现在")')
        self.assertHas(src, '"-%d:%02d".format(total / 60, total % 60)')
        self.assertHas(src, '"-%d:%02d".format(total / 3600, total % 3600 / 60)')

    def test_unselected_metric_buttons_are_deliberately_faint(self):
        src = kotlin("Panel.kt")
        self.assertHas(src, "onSurface.copy(alpha = 0.30f)")
        self.assertHas(src, "metric.color.copy(alpha = 0.30f)")


class CapabilityTest(SourceTest):
    """What Android can and cannot do, pinned so the app stays honest about it:
    the GTK app's control half needs a root daemon and sysfs writes."""

    def test_the_root_only_controls_are_shown_but_disabled(self):
        panel = kotlin("Panel.kt")
        limits = re.search(r"fun LimitsSection\(\) \{(.*?)\n\}",
                           panel, re.S).group(1)
        # no section title: the switch below says what the box is for
        self.assertHas(limits, "Section {", "LimitsSection")
        self.assertLacks(limits, 'tr("充电限制")', "LimitsSection")
        self.assertHas(limits, 'tr("限制充电")', "LimitsSection")
        # the switch and both steppers are inert, not merely unlabelled
        self.assertGreaterEqual(limits.count("enabled = false"), 3)
        self.assertHas(limits, 'KeyChip(tr("未 root"), AMBER', "LimitsSection")
        self.assertHas(limits, 'tr("仅提供状态")', "LimitsSection")

    def test_the_hints_close_themselves(self):
        """A ⓘ covers the row it explains, so it goes away on its own instead
        of waiting to be dismissed (the GTK app's ⓘ does the same)."""
        panel = kotlin("Panel.kt")
        self.assertHas(panel, "private const val HINT_MS = 2000L")
        self.assertHas(panel, "LaunchedEffect(open)")
        self.assertHas(panel, "delay(HINT_MS)")
        gui = read(ROOT, "chargecap")
        self.assertHas(gui, "HINT_MS = 2000")
        self.assertHas(gui, 'pop.connect("map", lambda *_: GLib.timeout_add(HINT_MS, pop.popdown))')

    def test_the_input_current_limit_is_not_writable(self):
        """`限制` is drawn as an empty, inert box: without root there is no
        sysfs node to write a limit to."""
        panel = kotlin("Panel.kt")
        self.assertLacks(panel, "BATTERY_PROPERTY")
        self.assertHas(panel, "border(1.dp")

    def test_inhibit_sleep_is_a_wake_lock(self):
        """The GTK app holds a systemd-inhibit; Android's equivalent is a
        partial wake lock, and it needs the matching permission."""
        manifest = read(MAIN, "AndroidManifest.xml")
        self.assertHas(manifest, "android.permission.WAKE_LOCK", "manifest")
        self.assertHas(kotlin("Prefs.kt"), "PARTIAL_WAKE_LOCK")
        self.assertHas(kotlin("Prefs.kt"), '"chargecap:sleep"')
        # one inhibitor for the process: an Activity recreated for an unclaimed
        # configuration change must not leave a second wake lock held
        self.assertHas(kotlin("Prefs.kt"), "companion object")
        self.assertHas(kotlin("Prefs.kt"), "fun get(context: Context): SleepInhibitor")
        self.assertHas(kotlin("MainActivity.kt"), "SleepInhibitor.get(this)")
        self.assertLacks(kotlin("MainActivity.kt"), "SleepInhibitor(this)")
        # ... and it is released with the app, never left behind -- unless
        # 禁止休眠 is still on, when the service keeps the explicit lock
        self.assertHas(kotlin("MainActivity.kt"), "inhibitor.release()")
        self.assertHas(kotlin("MainActivity.kt"), "!prefs.inhibitSleep")

    def test_the_current_is_the_hal_reading_calibrated_by_the_counter(self):
        """CURRENT_NOW is the only reading that carries the current's sign, but
        its unit is only a promise (mA on this Huawei where the API says µA, so
        a 0.3 A discharge reads as -297).  The counter's *magnitude* decides the
        unit -- its own sign cannot be trusted: this phone's counter only ever
        counts up -- and the decision is remembered, because the counter stops
        moving once the battery is full."""
        battery = kotlin("Battery.kt")
        self.assertHas(battery, "BATTERY_PROPERTY_CURRENT_NOW")
        self.assertHas(battery, "BATTERY_PROPERTY_CHARGE_COUNTER")
        self.assertHas(battery, "currentA(reported, slope)")
        # a full idle phone reports CURRENT_NOW 0 while the counter falls
        self.assertHas(battery,
                       "if (reported == 0 && slope != null && abs(slope) > MIN_SLOPE_A) return slope")
        self.assertHas(battery, "abs(milli - magnitude) <= abs(micro - magnitude)")
        self.assertHas(battery, "private var perMilli: Boolean? = null")
        self.assertHas(battery, "perMilli == true")
        # the reader keeps its counter history across a read-rate change; a new
        # reader has no slope, so a full idle phone's current would read 0 for
        # the seconds until a new history exists
        self.assertHas(battery, "private var reader: BatteryReader? = null")
        self.assertHas(battery,
                       "val battery = reader ?: BatteryReader(context.applicationContext).also { reader = it }")
        self.assertLacks(battery, "val reader = BatteryReader(context)")
        # a counter reset is not a current
        self.assertHas(battery, "abs(amps) > MAX_SLOPE_A")
        self.assertHas(battery, "history.clear()")

    def test_the_battery_data_is_the_public_api(self):
        """No sysfs, and no hidden APIs beyond the one optional reflection for
        the design capacity -- which has to degrade to nothing."""
        battery = code_only(kotlin("Battery.kt"))
        self.assertLacks(battery, "/sys/class/power_supply")
        self.assertLacks(battery, "Runtime.exec")
        self.assertHas(battery, "BatteryManager")
        self.assertHas(battery, "getIntProperty")
        self.assertHas(battery, "PowerProfile")
        self.assertHas(battery, "catch (t: Throwable) {")

    def test_samples_are_kept_in_memory_only(self):
        """Like the GTK app: nothing is written to disk, so nothing has to be
        cleaned up but the wake lock."""
        for name in SOURCES:
            with self.subTest(name):
                self.assertLacks(code_only(kotlin(name)), "openFileOutput")

    def test_the_status_panel_says_what_android_does_not_publish(self):
        """charge_full does not exist here, so the row is named for what the
        platform really reports (the gauge's counter) and the health comes from
        the platform as a state, not as a percentage."""
        panel = kotlin("Panel.kt")
        self.assertHas(panel, 'tr("统计/设计容量(mAh)")')
        self.assertHas(panel, "BATTERY_HEALTH_GOOD -> tr(\"良好\")")
        self.assertHas(panel, "chargeCounterUAh")
        # the counter's number invites the wrong reading on its own, so the row
        # carries the explanation next to it
        self.assertHas(panel, "GaugeHelp()")
        self.assertHas(kotlin("Strings.kt"), "电量计累计流过的电荷，不是剩余电量：")


class PanelTest(SourceTest):
    """The panel's shape: boxed sections, a dark default, and hints that talk
    about this platform rather than about Linux."""

    def test_the_sections_are_boxed_like_the_gtk_apps_groups(self):
        panel = kotlin("Panel.kt")
        self.assertHas(panel, "fun Section(")
        self.assertHas(panel, "surfaceContainerHigh")
        self.assertHas(panel, "fun RowDivider()")
        self.assertHas(panel, "HorizontalDivider(")
        # every part of the panel is one of those boxes; the table and the
        # chart now share the one LiveSection card
        for section in ("LimitsSection", "SleepSection", "LiveSection"):
            body = re.search(r"fun %s\(.*?\n\}" % section, panel, re.S).group(0)
            with self.subTest(section=section):
                self.assertHas(body, "Section(", section)
        # ... and the status rows separate themselves the way Adw does
        status = re.search(r"fun StatusRows\(.*?\n    }\n}", panel, re.S).group(0)
        self.assertGreaterEqual(status.count("RowDivider()"), 4)

    def test_the_metric_row_and_the_window_picker_share_one_line(self):
        """The GTK app puts the metric buttons and the window picker on one row
        (buttons left, picker right, a spacer between) -- which is what lets the
        whole panel, chart included, fit a phone screen without scrolling."""
        chart = re.search(r"fun ChartRows\(.*?\n    }\n}", kotlin("Panel.kt"), re.S).group(0)
        body = chart[chart.index("Column {"):]
        self.assertHas(body, "Row(verticalAlignment = Alignment.CenterVertically)")
        self.assertHas(body, "Spacer(Modifier.weight(1f))")
        self.assertLess(body.index("MetricButton("), body.index("ChipPicker("))
        self.assertLess(body.index("ChipPicker("), body.index("LiveChart("))
        # one row, not a wrapping FlowRow, and one line per label
        self.assertLacks(body, "FlowRow")

    def test_the_chip_buttons_are_exactly_their_content(self):
        """Material's Surface(onClick) spends a 48dp minimum touch target on
        every button -- 37px of empty padding each, which pushed the metric row
        onto a second line on a 360dp screen."""
        panel = kotlin("Panel.kt")
        self.assertHas(panel, "private fun ChipButton(")
        self.assertHas(panel, ".clip(shape)")
        self.assertHas(panel, ".clickable(onClick = onClick)")
        for user in ("MetricButton",):
            body = re.search(r"private fun %s\(.*?\n\}" % user, panel, re.S).group(0)
            with self.subTest(user=user):
                self.assertHas(body, "ChipButton(", user)
                self.assertLacks(body, "Surface(", user)

    def test_the_background_is_dark_by_default(self):
        theme = kotlin("Theme.kt")
        self.assertHas(theme, "enum class Theme")
        self.assertHas(theme, "DARK(\"dark\"), LIGHT(\"light\"), AUTO(\"auto\")")
        self.assertHas(theme, "entries.firstOrNull { it.tag == tag } ?: DARK")
        self.assertHas(kotlin("Prefs.kt"), "Theme.of(store.getString(\"theme\", null))")
        # the scheme is applied by the theme, not by the system's
        self.assertHas(kotlin("MainActivity.kt"), "AppTheme(theme = state.theme)")

    def test_the_hints_describe_this_platform(self):
        """Where the two platforms differ the notes are the Android app's own:
        the GTK app reads SDP / DCP / CDP from its charger driver and computes a
        wear percentage from the gauge, and neither exists here.  What both can
        say the same way (the sleep note) is shared, not duplicated."""
        panel = kotlin("Panel.kt")
        self.assertHas(panel, 'tr("系统不休眠，保持网络在线")')
        self.assertHas(panel, "HealthHelp()")
        self.assertHas(panel, r'tr("健康度是系统上报的电池状态，不是磨损百分比：\n")')
        # the GTK app's Linux-only subjects stay out of the Android app's own
        # strings (a comment may name them; the UI may not)
        shown = "\n".join(code_only(kotlin(name)) for name in SOURCES)
        shown = "\n".join(line for line in shown.split("\n") if "tr(" in line)
        for gtk_only in ("systemd-inhibit", "SDP", "DCP", "CDP", "logind"):
            with self.subTest(gtk_only=gtk_only):
                self.assertLacks(shown, gtk_only)


class NotifyPageTest(SourceTest):
    """The 通知 page -- the screen the app opens on -- and 设置, the gear holding
    the two screens only the system owns.  Android has 通知 first (the GTK app has
    no counterpart yet, see TODO.md); the panel it does draw is the page beside
    it, 其他.

    The three screens are Pages.kt, what they read and write is AppState.kt (over
    Prefs.kt), and the live sample is Battery.kt's one monitor: these tests keep
    the layers where they are as much as they keep the wording."""

    def header(self):
        return re.search(r"private fun AppHeader\(.*?\n\}", kotlin("MainActivity.kt"),
                         re.S).group(0)

    def page(self):
        return re.search(r"fun NotifyPage\(.*?\n\}", kotlin("Pages.kt"),
                         re.S).group(0)

    def row(self):
        return re.search(r"private fun NotifyRow\(.*?\n\}", kotlin("Pages.kt"),
                         re.S).group(0)

    def panel(self):
        return re.search(r"fun PanelPage\(.*?\n\}", kotlin("Pages.kt"),
                         re.S).group(0)

    def settings(self):
        return re.search(r"fun SettingsPage\(.*?\n\}", kotlin("Pages.kt"),
                         re.S).group(0)

    def state(self):
        return kotlin("AppState.kt")

    def branches(self):
        """The when (page) branches, in the order they are drawn: the two pages
        under the shared header, then 设置."""
        app = kotlin("MainActivity.kt")
        two = app.index("Page.NOTIFY, Page.OTHER -> Scaffold(")
        settings = app.index("Page.SETTINGS -> Scaffold(")
        return app[two:settings], app[settings:]

    # ---- the frame: two pages in the header, and the gear ------------------

    def test_the_two_pages_sit_side_by_side_in_the_header(self):
        """通知, the page the app opens on, and 其他, the panel the GTK app
        draws -- where a title would otherwise be."""
        app = kotlin("MainActivity.kt")
        self.assertHas(self.state(), "enum class Page { NOTIFY, OTHER, SETTINGS }")
        self.assertHas(self.state(), "var page by mutableStateOf(Page.NOTIFY)")
        self.assertHas(self.header(), "PageTabs(state)")
        tabs = re.search(r"private fun PageTabs\(.*?\n\}", app, re.S).group(0)
        for label in ("通知", "高级"):
            with self.subTest(label=label):
                self.assertHas(tabs, f'"{label}"')
        # the page you are on is the one written solid, on its own background
        self.assertHas(tabs, "fontWeight = if (here) FontWeight.Bold")
        self.assertHas(tabs, ".background(")
        self.assertHas(tabs, "primaryContainer")

    def test_the_theme_and_the_language_are_a_pair_before_the_gear(self):
        """Left to right: the two pages, then the theme and the language, then
        设置 alone on the far right."""
        header = self.header()
        for first, second in (
            ("PageTabs(state)",
             "BackgroundButton(state.theme, state::setTheme)"),
            ("BackgroundButton(state.theme, state::setTheme)",
             "LanguageButton(state.lang, state::setLang)"),
            ("LanguageButton(state.lang, state::setLang)",
             "SettingsButton { state.show(Page.SETTINGS) }"),
        ):
            with self.subTest(first=first):
                self.assertLess(header.index(first), header.index(second))
        # a couple of characters each, in a box the size of what is in them: a
        # TextButton's minimum width is what held the pair apart
        app = kotlin("MainActivity.kt")
        self.assertHas(app, "private fun HeaderButton(")
        # the language button is a door, not a label: it names the other one
        self.assertHas(app, 'HeaderButton(if (Strings.effective == Lang.ZH) "EN" else "中")')
        self.assertLacks(header, "TextButton(")
        # ... and the gear is a gear, not another word
        gear = re.search(r"private fun SettingsButton\(.*?\n\}", app, re.S).group(0)
        self.assertHas(gear, "HeaderButton(" + chr(34) + chr(92) + "u2699")
        self.assertHas(gear, "22.sp")

    def test_the_notifications_are_the_default_page(self):
        """The app opens on 通知; 其他 is the panel the GTK app draws, and 设置
        is neither page's own."""
        two, rest = self.branches()
        self.assertHas(two,
                       "if (state.page == Page.NOTIFY) NotifyPage(state, inset)")
        self.assertHas(two, "else PanelPage(state, inset)")
        self.assertHas(rest, "SettingsPage(inset)")
        for section in ("LimitsSection()", "SleepSection(", "LiveSection("):
            with self.subTest(section=section):
                self.assertHas(self.panel(), section)
        self.assertLacks(two, "LimitsSection()")
        self.assertHas(kotlin("MainActivity.kt"), 'tr("设置")')

    def test_back_walks_back_the_way_it_came(self):
        """設置 remembers the page it was opened from; 其他 returns to 通知, and
        from 通知 the phone's own back leaves the app."""
        state = self.state()
        self.assertHas(state, "var back = Page.NOTIFY")
        self.assertHas(state, "if (target == Page.SETTINGS) back = page")
        self.assertHas(state,
                       "page = if (page == Page.SETTINGS) back else Page.NOTIFY")
        main = kotlin("MainActivity.kt")
        self.assertHas(main,
                       "BackHandler(enabled = state.page != Page.NOTIFY) { state.leave() }")
        self.assertHas(main, "TextButton(onClick = { state.leave() })")

    # ---- the framework: one state, one reader ------------------------------

    def test_every_screen_is_a_function_of_the_one_state(self):
        """A page takes AppState and nothing else: it reads what it shows and
        writes through the setters, so no screen re-plumbs anything."""
        pages = kotlin("Pages.kt")
        for page in ("NotifyPage", "PanelPage"):
            with self.subTest(page=page):
                self.assertHas(pages, f"fun {page}(state: AppState")
        self.assertHas(pages, "fun SettingsPage(inset: PaddingValues)")
        # the activity keeps no stored value of its own any more
        main = kotlin("MainActivity.kt")
        self.assertLacks(main, "mutableStateOf(prefs")
        self.assertHas(main, "val state = remember { AppState(prefs, inhibitor) }")

    def test_the_low_level_read_is_one_place(self):
        """The battery is sampled once, by the monitor, and the screens read it
        through the state: a page that collected its own would be a second
        reader and a second clock.  The process-level readers -- the rules'
        notifier, the voice's endless count and the foreground service's ongoing
        notification -- are not pages and do not sample either; they listen to
        the one flow."""
        self.assertHas(self.state(), "Monitor.state")
        self.assertHas(self.state(), "Monitor.buffer")
        self.assertHas(kotlin("Battery.kt"), "Monitor.intervalMs = chartMs")
        for name in SOURCES:
            if name in ("Battery.kt", "AppState.kt", "Notifications.kt",
                        "Voice.kt"):
                continue
            for reading in ("Monitor.state", "Monitor.buffer",
                            "Monitor.intervalMs"):
                with self.subTest(name=name, reading=reading):
                    self.assertLacks(code_only(kotlin(name)), reading, name)
        # the notifier's one read is its wire from the samples, inside the rules
        wire = re.search(r"fun startNotifier\(.*?\n\}",
                         kotlin("Notifications.kt"), re.S).group(0)
        self.assertHas(wire, "Monitor.state.collect")
        # the reader is started by the controller, when a page or the service
        # needs it -- never by a page on its own
        self.assertHas(kotlin("Battery.kt"), "object Sampling")
        self.assertHas(kotlin("MainActivity.kt"),
                       "Sampling.apply(applicationContext, prefs)")

    def test_a_new_notification_is_one_line_in_the_table(self):
        """NOTIFICATIONS says what a notification is -- key, words, unit, range
        -- and the page loops over it while Prefs keys off it, so the next one is
        one line and nothing else."""
        table = re.search(r"val NOTIFICATIONS = listOf\((.*?)\n\)",
                          self.state(), re.S).group(1)
        self.assertEqual(re.findall(r'Notification\(\s*"(\w+)"', table),
                         ["done", "low", "plugged", "unplugged", "charging",
                          "idle", "hot", "cold", "vhigh", "vlow", "iin",
                          "drain", "power"])
        for default in ("100", "10", "45", "-20", "4300", "3400", "3000",
                        "1000", "20"):
            with self.subTest(default=default):
                self.assertHas(table, default)
        # one loop over the table, filtered into the page's groups
        group = re.search(r"private fun NotifyGroup\(.*?\n\}", kotlin("Pages.kt"),
                          re.S).group(0)
        self.assertHas(group, "NOTIFICATIONS.filter { it.key in keys }")
        self.assertHas(group, "NotifyRow(state, n)")
        self.assertEqual(kotlin("Pages.kt").count("NotifyRow(state, n)"), 1)
        # one key per notification, and every part of it is stored under it
        prefs = kotlin("Prefs.kt")
        for stored in ('"notify_$key"', '"notify_${key}_at"',
                       '"notify_${n.key}_kind"', '"notify_${n.key}_times"',
                       '"notify_${n.key}_gap"'):
            with self.subTest(stored=stored):
                self.assertHas(prefs, stored)

    # ---- what the page says, and what it stores ---------------------------

    def test_every_switch_waits_to_be_asked(self):
        """A fresh install arms nothing: the master switch decides whether
        anything fires at all, and each notification is its owner's own choice,
        so turning the master on does not start a page of reminders.  The
        discharge one still reads the size of a discharge -- the reading is
        signed, so charging is not a drain."""
        table = re.search(r"val NOTIFICATIONS = listOf\((.*?)\n\)",
                          kotlin("AppState.kt"), re.S).group(1)
        self.assertLacks(table, "onByDefault")
        self.assertHas(table,
                       '"drain", { tr("放电电流过高") }, { tr("高于") }, " mA", 1000, 100, 0, 5000')
        self.assertHas(table, "s.currentA?.let { -(it * 1000.0).toFloat() - at } ?: -1000f")
        self.assertHas(kotlin("AppState.kt"), "prefs.notifyItem(it.key)")
        self.assertHas(kotlin("Prefs.kt"),
                       'fun notifyItem(key: String): Boolean = store.getBoolean("notify_$key", false)')
        self.assertHas(kotlin("Strings.kt"), '"放电电流过高" to "High discharge current"')

    def test_the_master_switch_is_off_until_it_is_turned_on(self):
        self.assertHas(kotlin("Prefs.kt"), 'store.getBoolean("notify", false)')
        self.assertHas(self.page(), 'SwitchRow(tr("通知开关")')

    def test_the_notification_page_carries_no_notes(self):
        """Four rows per notification as it is, and every one of them says what
        it is -- so nothing is written under them."""
        for part in (self.page(), self.row()):
            with self.subTest(part=part.split("(")[0]):
                self.assertLacks(part, "subtitle")
        # the two rows that leave the app keep theirs
        self.assertHas(self.settings(), "LinkRow(tr(")

    def test_a_notification_arrives_as_a_voice_unless_asked(self):
        prefs = kotlin("Prefs.kt")
        self.assertHas(prefs, 'BANNER("banner"), VOICE("voice")')
        self.assertHas(prefs, "entries.firstOrNull { it.tag == tag } ?: VOICE")
        self.assertHas(kotlin("AppState.kt"), "answers[n.key] ?: Answer.FRESH")
        self.assertHas(kotlin("Prefs.kt"), "val FRESH = Answer(NotifyKind.VOICE, 1, DEFAULT_GAP)")
        for label in ("横幅", "语音"):
            with self.subTest(label=label):
                self.assertHas(kotlin("Pages.kt"), f'tr("{label}")')
        # arriving twice over is gone: the page offers one or the other
        self.assertLacks(prefs, "BOTH")
        self.assertLacks(kotlin("Pages.kt"), "语音 + 横幅")

    def test_every_notification_has_a_switch_a_number_and_a_type(self):
        """All three are the notification's own -- nothing on this page is a
        page-wide setting, which is why they all go through the table."""
        row = self.row()
        for part in ("SwitchStepperRow(", "NotifyKindRow("):
            with self.subTest(part=part):
                self.assertHas(row, part)
        state = self.state()
        for member in ("fun itemOn(", "fun setItem(", "fun answerOf(",
                       "fun setAnswer(", "fun at(", "fun setAt(", "fun step("):
            with self.subTest(member=member):
                self.assertHas(state, member)
        # every row stays live: the master switch is the gate, and it is not a
        # row that dims the ones under it
        # the row wears the short word; the sentence it says keeps the name
        for line in ("title = n.short(),", "checked = state.itemOn(n),",
                     "value = state.at(n),", "enabled = live,",
                     "onCheck = { state.setItem(n, it) },",
                     "onChange = { state.setAt(n, it) },"):
            with self.subTest(line=line):
                self.assertHas(row, line)
        # the 达 / 低于 / 高于 words are gone: the title says which way it reads
        for word in ("n.label()", "达", "低于", "高于"):
            with self.subTest(word=word):
                self.assertLacks(row, word)
        self.assertHas(row, "NotifyKindRow(")
        # 通知方式 and 次数 share one row, and both are the whole
        # notification's: a banner repeats as well as a voice
        self.assertHas(row, "answer = state.answerOf(n),")
        self.assertHas(row, "onAnswer = { picked ->")
        self.assertLacks(row, "takeIf { state.kindOf(n)")
        self.assertLacks(kotlin("Pages.kt"), "NotifyTimesRow")
        # 通知开关 off dims every row under it and changes none of them
        self.assertHas(row, "val live = state.notify")

    def test_the_master_is_a_size_up_from_the_rows_under_it(self):
        """通知开关 is the page's one gate: a bigger word and a full-size switch,
        with the four it gates a step down -- so which switch is which needs no
        reading."""
        self.assertHas(self.page(), "master = true)")
        panel = kotlin("Panel.kt")
        self.assertHas(panel, "master: Boolean = false,")
        self.assertHas(panel, "(if (master) s.heading + 4f else s.heading).sp")
        self.assertHas(panel, ".heightIn(min = if (master) 56.dp else 48.dp)")
        self.assertHas(panel, "Modifier.scale(if (master) 1f else 0.8f)")
        # the switch is drawn smaller, its touch target is not
        self.assertHas(kotlin("Panel.kt"), "Switch(")

    def test_a_number_can_be_typed_as_well_as_stepped(self):
        """The value is a field you tap and type into, with the same − and +
        beside it: the keyboard's done -- or looking away -- is when it is
        read, and what the field then shows is what was kept."""
        panel = kotlin("Panel.kt")
        field = re.search(r"private fun NumberField\(.*?\n\}", panel, re.S).group(0)
        self.assertHas(field, "BasicTextField(")
        self.assertHas(field, "state = field,")
        self.assertHas(field, "KeyboardType.Number")
        self.assertHas(field, "ImeAction.Done")
        self.assertHas(field, "onFocusChanged { if (!it.isFocused) commit() }")
        # not a number puts the old one back; a number goes through the check
        self.assertHas(field, 'field.text.toString().trim().toIntOrNull()')
        self.assertHas(field, "val kept = if (typed == null) value else onCommit(typed)")
        row = re.search(r"internal fun StepperRow\(.*?\n\}", panel, re.S).group(0)
        self.assertHas(row, 'StepButton("−", enabled) { onChange(value - step) }')
        self.assertHas(row, 'StepButton("+", enabled) { onChange(value + step) }')
        # the check itself is one place, and a step takes the same road as a
        # typed number
        self.assertHas(self.state(),
                       "fun step(n: Notification, direction: Int) = setAt(n, at(n) + direction * n.step)")

    def test_a_number_lands_inside_its_own_range(self):
        """电量 is a percentage, a temperature is not, and neither is a
        voltage, a current or a power: each one carries its own range and its
        own step, so a press moves 5 % or 50 mV as the reading deserves."""
        table = re.search(r"val NOTIFICATIONS = listOf\((.*?)\n\)",
                          self.state(), re.S).group(1)
        for line in ('"%", 100, 1, 0, 100', '"%", 10, 1, 0, 100',
                     '" °C", 45, 1, -60, 100', '" °C", -20, 1, -60, 100',
                     # millivolts, milliamps and watts are not percentages
                     '" mV", 4300, 100, 3000, 5000', '" mV", 3400, 100, 2500, 4500',
                     '" mA", 3000, 100, 0, 10000',
                     '" mA", 1000, 100, 0, 5000', '" W", 20, 1, 0, 100'):
            with self.subTest(line=line):
                self.assertHas(table, line)
        state = self.state()
        self.assertHas(state, "fun inside(reading: Int): Int = reading.coerceIn(low, high)")
        self.assertHas(state, "fun setAt(n: Notification, reading: Int): Int {")
        self.assertHas(state, "val inside = keepApart(n, reading)")
        self.assertHas(state, "return inside")

    def test_the_two_charge_lines_never_cross(self):
        """充电完成 has to stay above 电量过低, so each one's range stops at the
        other: typed or stepped, full at 55% is never below empty at 55%."""
        state = self.state()
        self.assertHas(state, 'above = "low",')
        body = re.search(r"private fun keepApart\(.*?\n    \}", state, re.S).group(0)
        self.assertHas(body, "val floor = other?.let { at(it) + 1 }")
        self.assertHas(body,
                       "val ceiling = NOTIFICATIONS.firstOrNull { it.above == n.key }?.let { at(it) - 1 }")
        self.assertHas(body, "val lo = maxOf(n.low, floor ?: n.low)")
        self.assertHas(body, "val hi = minOf(n.high, ceiling ?: n.high)")
        self.assertHas(body, "reading.coerceIn(lo, hi)")

    def test_the_voice_count_is_the_voices_own(self):
        """通知次数 belongs to a voice: the counts 1次 to 10次 for all of them,
        and for the two with something to wait for their own endless chip -- 电量过低
        until the plug goes in, 充电完成 until the cable comes out.  A banner is
        one banner, so the row is not on the page unless there is a voice."""
        state = self.state()
        self.assertHas(state, "val TIMES: List<Pair<Int, () -> String>> = listOf(")
        for line in ('1 to { tr("1次") }', '2 to { tr("2次") }',
                     '3 to { tr("3次") }', '5 to { tr("5次") }',
                     '10 to { tr("10次") }'):
            with self.subTest(line=line):
                self.assertHas(state, line)
        self.assertHas(state, "val TIMES: List<Pair<Int, () -> String>> = listOf(")
        # ... and the endless one comes from the row that has something to wait
        self.assertHas(state, "TIMES + listOfNotNull(until?.let { 0 to it.label })")
        self.assertHas(state, "fun Notification.timesLabel(count: Int): String =")
        # the count is one field of the answer, and Prefs keeps it under the
        # same key the row always wrote
        self.assertHas(kotlin("Prefs.kt"),
                       'store.getInt("notify_${n.key}_times", 1)')
        # a count is not a line: moving it does not re-arm the rules
        body = re.search(r"fun setAnswer\(.*?\n    \}", state, re.S).group(0)
        self.assertHas(body, "arm(again = kindMoved)")

    def test_the_readings_are_grouped_by_kind(self):
        """温度, 电压, 电流 and 功率 are four different readings, so each is its
        own group rather than one pile called 其他; the plug and the charging
        state sit between the battery's own charge and them."""
        page = kotlin("Pages.kt")
        groups = re.search(r"private val GROUPS = listOf\((.*?)\n\)", page,
                           re.S).group(1)
        self.assertEqual(re.findall(r'Group\(\{ tr\("(\w+)"\) \}', groups),
                         ["基础功能", "电源", "充电", "温度", "电压", "电流", "功率"])
        # every notification is in exactly one group, in the table's order
        table = re.search(r"val NOTIFICATIONS = listOf\((.*?)\n\)",
                          self.state(), re.S).group(1)
        keys = re.findall(r'Notification\(\s*"(\w+)"', table)
        listed = re.findall(r'setOf\(([^)]*)\)', groups)
        seen = [k.strip().strip('"') for line in listed for k in line.split(",")]
        self.assertEqual(sorted(seen), sorted(keys))
        self.assertEqual(len(seen), len(set(seen)))
        # the page draws them in that order, and no group is left out
        self.assertHas(page, "for (group in GROUPS) NotifyGroup(state, group.title(), group.keys)")

    def test_a_state_row_has_no_number_to_step(self):
        """电源连接 and the other three states are on or off, not readings
        with a line: their row is the name, the switch, and the answers under
        it -- no field, no − and +."""
        table = re.search(r"val NOTIFICATIONS = listOf\((.*?)\n\)",
                          self.state(), re.S).group(1)
        self.assertEqual(table.count("numbered = false"), 4)
        self.assertHas(kotlin("AppState.kt"), "val numbered: Boolean = true,")
        row = self.row()
        self.assertHas(row, "if (n.numbered) {")
        self.assertHas(row, "SwitchStepperRow(")
        self.assertHas(row, "} else {")
        self.assertHas(row, "SwitchRow(")

    def test_turning_the_master_on_asks_what_the_system_allows(self):
        """通知开关 on is where a reminder can be lost before it is posted: the
        channel may be silenced and the system may stop the app, so both are
        read as soon as the switch is on -- after the permission answer, never
        while its dialog is still open -- and 设置 is one tap away."""
        page = self.page()
        self.assertHas(page, "var missing by remember { mutableStateOf(emptyList<Limit>()) }")
        self.assertHas(page, "RequestPermission()) { missing = limits(context) }")
        self.assertHas(page, "!on -> missing = emptyList()")
        self.assertHas(page, "else -> missing = limits(context)")
        self.assertHas(page, "state.show(Page.SETTINGS)")
        self.assertHas(kotlin("Pages.kt"), "private fun Limit.line(): String")
        system = kotlin("SystemSettings.kt")
        self.assertHas(system, "fun limits(context: Context): List<Limit>")
        self.assertHas(system, "notifications.areNotificationsEnabled()")
        self.assertHas(system, "IMPORTANCE_NONE")
        self.assertHas(system, "power?.isIgnoringBatteryOptimizations(context.packageName)")

    def test_a_row_wears_a_short_word_and_the_sentence_keeps_the_name(self):
        """电源连接 reads 连接 under the 电源 heading, 温度过高 reads 过高 -- but
        the banner and the voice still say the full sentence."""
        table = re.search(r"val NOTIFICATIONS = listOf\((.*?)\n\)",
                          self.state(), re.S).group(1)
        for short in ("连接", "断开", "过高", "过低", "充电过高", "放电过高"):
            with self.subTest(short=short):
                self.assertHas(table, f'short = {{ tr("{short}") }}')
        # ... and the sentence comes from the full title
        self.assertHas(self.state(),
                       'if (numbered) "${title()} ${value(reading)}" else title()')
        # the row asks for the short one
        self.assertHas(self.row(), "title = n.short(),")

    def test_the_master_switch_dims_the_rows_it_gates(self):
        """通知开关 off is a gate, not a reset: the rows dim and stop taking
        input, and keep every answer they hold."""
        row = self.row()
        self.assertHas(row, "val live = state.notify")
        self.assertHas(row, "enabled = live,")
        self.assertHas(kotlin("Panel.kt"), "enabled: Boolean = true,")
        # a chip too, and the answer labels beside it
        self.assertHas(kotlin("Panel.kt"), "if (enabled) open = true")
        self.assertHas(kotlin("Pages.kt"),
                       "private fun AnswerTitle(text: String, enabled: Boolean)")

    def test_the_three_answers_are_one_value(self):
        """通知方式, 次数 and 间隔 are one answer -- kind, count, gap -- so the
        page's chips and the reminder's loop read the same value and a pick
        can never leave one of the three stale.  The stored keys stay where
        they were, so an install that already has answers keeps them."""
        prefs = kotlin("Prefs.kt")
        self.assertHas(prefs, "data class Answer(val kind: NotifyKind, val times: Int, val gap: Int)")
        self.assertHas(prefs, "fun notifyAnswer(n: Notification): Answer = Answer.of(")
        self.assertHas(prefs, "fun setNotifyAnswer(n: Notification, answer: Answer) {")
        self.assertHas(prefs, "if (n.times().any { it.first == times }) times else FRESH.times")
        self.assertHas(prefs, "if (GAPS.any { it.second == gap }) gap else FRESH.gap")
        state = self.state()
        self.assertHas(state, "private val answers = mutableStateMapOf<String, Answer>()")
        self.assertHas(state, "fun answerOf(n: Notification): Answer = answers[n.key] ?: Answer.FRESH")
        self.assertHas(state, "fun setAnswer(n: Notification, answer: Answer) {")
        # the three old setters are gone: three memories could disagree
        for gone in ("fun kindOf(", "fun setKind(", "fun timesOf(", "fun setTimes(",
                     "fun gapOf(", "fun setGap("):
            with self.subTest(gone=gone):
                self.assertLacks(state, gone)
        # one chip-drawing path, and the fixed 0 is its own branch of it
        self.assertHas(kotlin("Pages.kt"), "private fun <T> AnswerChip(")
        self.assertHas(kotlin("Rules.kt"), "val answer: Answer,")

    def test_the_three_chips_sit_in_columns(self):
        """通知方式 starts at the same x on every row -- its column is as wide as
        the widest chip it can draw -- the count sits right after its label, and
        间隔 owns the far end of the row, so all three line up across
        notifications whatever width the values happen to be."""
        row = re.search(r"private fun NotifyKindRow\(.*?\n\}",
                        kotlin("Pages.kt"), re.S).group(0)
        self.assertHas(row, "val widestKind = remember(s, Strings.effective) {")
        self.assertHas(row, "NotifyKind.entries.maxOf { k ->")
        self.assertHas(row, "Box(Modifier.widthIn(min = kindColumn)) {")
        # two choices do not need a menu most of the screen wide
        self.assertHas(row, "width = 140.dp,")
        self.assertLacks(row, "width = 300.dp")
        # the rest of the row is 间隔's, so the count's width never moves it
        self.assertHas(row, "Spacer(Modifier.weight(1f))")
        after = row[row.index("Spacer(Modifier.weight(1f))"):]
        self.assertHas(after, 'tr("间隔")')
        # one notification has no gap, and the row still says so: 0, and a
        # chip that opens nothing
        self.assertHas(after, 'items = if (count == 1) null else GAPS,')
        self.assertHas(after, 'label = if (count == 1) "0" else gapLabel(gap),')
        # ... and the one helper that draws a chip with or without choices
        page = kotlin("Pages.kt")
        self.assertHas(page, "private fun <T> AnswerChip(")
        self.assertHas(page, "if (items == null || current == null) {")
        self.assertHas(page, "FixedChip(label)")
        self.assertIn("else GAPS,", after)
        self.assertHas(kotlin("Panel.kt"),
                       "internal fun FixedChip(label: String) {")

    def test_each_endless_count_waits_for_its_own_reading(self):
        """直到开始充电 is 电量过低's -- a low charge is fixed by plugging in --
        and 直到电源断开 is 充电完成's, since that is what a full battery is
        waiting for.  The two temperatures have neither: they stop at 10次."""
        table = re.search(r"val NOTIFICATIONS = listOf\((.*?)\n\)",
                          self.state(), re.S).group(1)
        self.assertEqual(table.count("until = Until("), 2)
        self.assertHas(table, 'until = Until({ tr("直到开始充电") }, { s -> s.charging })')
        self.assertHas(table, 'until = Until({ tr("直到电源断开") }, { s -> !s.plugged })')
        # an endless count stored where there is none to wait for reads as
        # once: the answer is clipped to the counts the notification offers
        self.assertHas(kotlin("Prefs.kt"),
                       "if (n.times().any { it.first == times }) times else FRESH.times")
        self.assertHas(self.state(), "answers[n.key] = answer.inside(n)")
        # ... and the reminder is told what stops it
        wire = re.search(r"private fun remind\(.*?\n\}",
                         kotlin("Notifications.kt"), re.S).group(0)
        self.assertHas(wire, "if (now.times == 0 && now.n.until?.done(Monitor.state.value) == true)")

    def test_switching_the_master_off_is_silent(self):
        """通知开关 off means nothing arrives -- the 试听 included, since setting
        something up is not a notification, and a reminder that is still being
        said does not get to finish its minute."""
        row = self.row()
        self.assertHas(row, "if (state.notify && picked.kind == NotifyKind.VOICE &&")
        body = re.search(r"fun setNotify\(.*?\n    \}", self.state(), re.S).group(0)
        self.assertHas(body, "stopReminders()")
        self.assertHas(body, "Voice.stop()")
        # and the banners already in the shade: off means nothing left behind
        self.assertHas(body, "cancelAll(prefs.context)")
        self.assertHas(body, "Watchdog.cancel(prefs.context)")
        notifier = kotlin("Notifications.kt")
        self.assertHas(notifier, "fun stopReminders() {")
        self.assertHas(notifier, "reminders.values.forEach { it.cancel() }")
        self.assertHas(notifier, "fun cancelAll(context: Context) {")
        voice = kotlin("Voice.kt")
        self.assertHas(voice, "fun stop() {")
        # ... and the engine's queue, which the coroutine does not own: a
        # sentence already handed over would otherwise play to its end
        self.assertHas(voice, "engine?.stop()")
        self.assertHas(voice, "waiting = null")

    def test_the_numbers_are_the_notifications_own(self):
        """The panel's 上限 / 下限 are the daemon's: reading them here would tie
        a notification to the charge window, which they must not be."""
        page = self.page()
        for borrowed in ("上限", "下限", "LimitsSection"):
            with self.subTest(borrowed=borrowed):
                self.assertLacks(page, borrowed)

    def test_the_switches_are_the_stored_ones(self):
        state = self.state()
        for written in ("prefs.notify = on", "prefs.setNotifyItem(n.key, on)",
                        "prefs.setNotifyAnswer(n, answers.getValue(n.key))",
                        "prefs.setNotifyAt(n.key, inside)"):
            with self.subTest(written=written):
                self.assertHas(state, written)
        # every stored part of a notification is read back through its key
        for read in ("prefs.notifyItem(it.key)",
                     "prefs.notifyAnswer(it)",
                     "prefs.notifyAt(it.key, it.default)"):
            with self.subTest(read=read):
                self.assertHas(state, read)

    def test_the_system_rows_lead_out_of_the_app(self):
        """The two switches a notification needs that are not the app's: the
        banner and its sound belong to the system's notification settings, and
        autostart to a vendor screen.  Both leave the app from 设置, and 自启动
        comes first -- it is the one no two phones file in the same place."""
        page = self.settings()
        self.assertHas(page, "LinkRow(")
        self.assertHas(page, 'LinkRow(tr("自启动")')
        self.assertHas(page, 'LinkRow(tr("通知横幅与声音")')
        self.assertLess(page.index('LinkRow(tr("自启动")'),
                        page.index('LinkRow(tr("通知横幅与声音")'))
        self.assertHas(page, "openAutostartSettings(context)")
        self.assertHas(page, "openNotificationSettings(context)")
        self.assertHas(page, 'LinkRow(tr("电池优化")')
        self.assertHas(page, 'LinkRow(tr("SCHEDULE_EXACT_ALARM 权限")')
        self.assertHas(page, "openBatteryOptimization(context)")
        self.assertHas(page, "openExactAlarm(context)")
        self.assertHas(page, "最近任务里锁定")
        system = kotlin("SystemSettings.kt")
        self.assertHas(system, "ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS")
        self.assertHas(system, "ACTION_REQUEST_SCHEDULE_EXACT_ALARM")
        self.assertHas(system, "canScheduleExactAlarms")
        # ... and the phone may keep them somewhere else entirely
        self.assertHas(page, 'tr("各厂商的设置位置不一样，下面的按钮带你去找")')

    def test_autostart_tries_the_vendors_then_the_apps_own_page(self):
        src = kotlin("SystemSettings.kt")
        # huawei first: this was written on one, and both of its screens answer
        self.assertHas(src,
                       '"com.huawei.systemmanager/'
                       '.startupmgr.ui.StartupNormalAppListActivity"')
        for vendor in ("com.miui.securitycenter", "com.coloros.safecenter",
                       "com.oppo.safe", "com.vivo.permissionmanager",
                       "com.samsung.android.lool", "com.meizu.safe"):
            with self.subTest(vendor=vendor):
                self.assertHas(src, vendor)
        # every phone has this one, so a vendor that moved the screen still
        # leaves the user somewhere useful
        self.assertHas(src, "Settings.ACTION_APPLICATION_DETAILS_SETTINGS")
        # and a screen that is not there is an answer, not a crash
        self.assertHas(src, "catch (t: Throwable)")

    def test_the_notification_row_opens_our_channels_own_page(self):
        """The channel's page is the one with 横幅 / 声音 / 震动 on it; the app's
        notification page and the app's own page are the doors after it."""
        src = kotlin("SystemSettings.kt")
        self.assertHas(src, "Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS")
        self.assertHas(src, "Settings.EXTRA_CHANNEL_ID")
        self.assertHas(src, "Settings.EXTRA_APP_PACKAGE")
        self.assertHas(src, "Settings.ACTION_APP_NOTIFICATION_SETTINGS")
        self.assertHas(src, "Settings.ACTION_APPLICATION_DETAILS_SETTINGS")
        # the channel page is Android 8; below it only the app's own page
        self.assertHas(src, "Build.VERSION_CODES.O) return openAppInfo(context)")

    def test_the_channel_exists_before_the_first_notification(self):
        """The system's 通知 page offers 横幅 / 声音 only once a channel exists,
        and 设置's row promises exactly those switches -- so the channel is made
        at launch, not with the first post."""
        channel = kotlin("Notifications.kt")
        self.assertHas(channel, 'const val NOTIFY_CHANNEL = "chargecap"')
        self.assertHas(channel, "NotificationManager.IMPORTANCE_HIGH")
        self.assertHas(channel, "createNotificationChannel(")
        self.assertHas(kotlin("MainActivity.kt"), "createNotificationChannel(this)")

    def test_the_banner_permission_is_asked_for_where_it_exists(self):
        """Android 13+ asks before an app may post banners; before that the
        manifest's permission is granted at install time."""
        self.assertHas(read(MAIN, "AndroidManifest.xml"),
                       "android.permission.POST_NOTIFICATIONS")
        pages = kotlin("Pages.kt")
        self.assertHas(pages, "ActivityResultContracts.RequestPermission()")
        self.assertHas(pages, "Build.VERSION_CODES.TIRAMISU")
        self.assertHas(pages, "askBanner.launch(")
        self.assertHas(pages, "Manifest.permission.POST_NOTIFICATIONS")


class SleepTest(SourceTest):
    """系统休眠: the record under 禁止休眠, read off the clocks."""

    def setUp(self):
        self.src = kotlin("Sleep.kt")

    def test_the_sleep_is_read_off_the_clocks(self):
        """uptimeMillis stands still while the CPU is suspended, so the wall
        clock's excess is the sleep inside one sample -- however fast or slow
        the sampler was running."""
        self.assertHas(kotlin("Battery.kt"),
                       "Sleeps.tick(System.currentTimeMillis(), SystemClock.uptimeMillis())")
        self.assertHas(self.src, "val slept = wall - lastWall - (uptime - lastUptime)")

    def test_one_sleep_is_a_merged_stretch(self):
        """A stretch of a minute or more is one 休眠, and awake time under two
        minutes belongs to the stretch it interrupted -- a night of doze
        punctuated by alarm wakeups is one event, not a hundred."""
        self.assertHas(self.src, "const val MIN_SECS = 60")
        self.assertHas(self.src, "const val MERGE_SECS = 120")
        self.assertHas(self.src, "stretchMs >= MIN_SECS * 1000")
        self.assertHas(self.src, "wall - stretchLast > MERGE_SECS * 1000")

    def test_the_count_starts_at_the_last_turn_on_and_dies_with_the_boot(self):
        """The count is the last 通知开关 turn-on's, not the phone's lifetime:
        turning it on starts the record over, and a reboot -- elapsedRealtime
        gone backwards -- clears it."""
        self.assertHas(kotlin("AppState.kt"), "if (on) Sleeps.restart()")
        # ... and that line is in 禁止休眠's setter, not the notifications'
        inhibit = re.search(r"fun setInhibit\(.*?\n    \}",
                            kotlin("AppState.kt"), re.S).group(0)
        self.assertHas(inhibit, "if (on) Sleeps.restart()")
        notify = re.search(r"fun setNotify\(.*?\n    \}",
                           kotlin("AppState.kt"), re.S).group(0)
        self.assertLacks(notify, "Sleeps.restart()")
        self.assertHas(self.src, "anchor = System.currentTimeMillis()")
        self.assertHas(self.src, "SystemClock.elapsedRealtime() < store.sleepElapsed")
        body = re.search(r"fun start\(prefs: Prefs\).*?\n    \}", self.src, re.S).group(0)
        self.assertHas(body, "count = 0")
        # the record is stored, so a kill is not enough to lose it
        for stored in ("sleep_anchor", "sleep_count", "sleep_naps", "sleep_elapsed"):
            with self.subTest(stored=stored):
                self.assertHas(kotlin("Prefs.kt"), f'"{stored}"')

    def test_the_row_sits_under_the_promise(self):
        """禁止休眠 promises the system will not sleep; the row under it is
        where that can be caught.  It is a record, not a notification: no
        switch, no 通知方式, no 次数, no 间隔 -- the count is the whole row, and
        a tap opens the history it kept."""
        panel = kotlin("Panel.kt")
        section = re.search(r"fun SleepSection\(.*?\n\}", panel, re.S).group(0)
        self.assertHas(section, 'SwitchRow(tr("禁止休眠")')
        self.assertHas(section, "RowDivider()")
        self.assertHas(section, "SleepRow()")
        row = re.search(r"private fun SleepRow\(.*?\n\}", panel, re.S).group(0)
        for absent in ("Switch(", "ChipPicker(", "通知方式", "次数", "间隔"):
            with self.subTest(absent=absent):
                self.assertLacks(row, absent)
        self.assertHas(row, "AlertDialog(")
        self.assertHas(row, 'tr("休眠记录")')
        self.assertHas(row, '"${Sleeps.count}" + tr("次")')
        self.assertHas(row, "Sleeps.line()")

    def test_the_words_are_the_records_own(self):
        for key in ("休眠记录", "还没开启禁止休眠", "还没有休眠",
                    "自 %s 起", "最近 %s，%s", "睡了 %d 分钟",
                    "睡了 %d 小时 %d 分钟", "次"):
            with self.subTest(key=key):
                self.assertHas(kotlin("Strings.kt"), f'"{key}"')


class RulesTest(SourceTest):
    """The rules: what the app does with the readings rather than draws.

    A notification fires on the way in and stays quiet until the reading comes
    back clear; it arrives as a banner, a voice or both; and all of it runs with
    the process rather than with a page, so these tests are about the one
    comparison, the one memory and the one wire from the monitor."""

    def rules(self):
        return kotlin("Rules.kt")

    def notifier(self):
        return kotlin("Notifications.kt")

    def test_a_rule_fires_once_and_rearms_on_the_way_back(self):
        src = self.rules()
        # one comparison per sample, in the notification's own unit
        self.assertHas(src, "fun past(s: Snapshot): Float = n.distance(s, at)")
        self.assertHas(src, "fun crossed(s: Snapshot): Boolean = past(s) >= 0f")
        # ... and back by its own step, so a value resting on the line says it
        # once rather than twice a second
        self.assertHas(src, "fun clear(s: Snapshot): Boolean = past(s) <= -n.step")
        # the set is the memory of who has spoken, and add() is the test
        self.assertHas(src,
                       "rule.crossed(s) && spoken.add(rule.n.key) -> out.add(rule)")
        self.assertHas(src,
                       "!rule.crossed(s) && rule.clear(s) -> spoken.remove(rule.n.key)")

    def test_a_new_line_starts_from_here(self):
        """Any switch moving re-arms: the memory starts over, and the first look
        after it learns where the readings are instead of saying so."""
        src = self.rules()
        self.assertHas(src, "private var current: List<Rule> = emptyList()")
        self.assertHas(src, "fun arm(now: List<Rule>) = synchronized(this) {")
        self.assertHas(src, "spoken.clear()")

    def test_turning_a_switch_on_says_nothing_at_once(self):
        """Arming is a look, not a word: 通知开关 (or one notification) turned
        on -- or the app opened under one already on -- takes whatever is
        already past its line as read, so only a crossing afterwards fires."""
        src = self.rules()
        self.assertHas(src, "private var seeding = true")
        self.assertHas(src, "seeding = true")
        self.assertHas(src, "if (seeding) {")
        self.assertHas(src, "seeding = false")
        self.assertHas(src, "if (rule.crossed(s)) spoken.add(rule.n.key)")
        # ... and the seeding pass ends without firing anything
        self.assertHas(src, "return@synchronized out")

    def test_the_master_switch_leaves_nothing_to_watch(self):
        state = kotlin("AppState.kt")
        self.assertHas(state, "if (!notify) emptyList()")
        self.assertHas(state,
                       ".map { Rule(it, at(it), answerOf(it)) }")
        # a switch re-arms; a stepper only moves where a line is
        for setter in ("setNotify", "setItem"):
            with self.subTest(setter=setter):
                body = re.search(rf"fun {setter}\(.*?\n    \}}", state, re.S).group(0)
                self.assertHas(body, "\n        arm()")
        stepper = re.search(r"fun setAt\(.*?\n    \}", state, re.S).group(0)
        self.assertHas(stepper, "arm(again = false)")
        # the answer's one setter is both: a kind re-arms, a count or a gap
        # only retunes
        answer = re.search(r"fun setAnswer\(.*?\n    \}", state, re.S).group(0)
        self.assertHas(answer, "val kindMoved = answer.kind != answerOf(n).kind")
        self.assertHas(answer, "arm(again = kindMoved)")
        # ... which is the whole point of the two: eight steps, no eight banners
        rules = self.rules()
        self.assertHas(rules, "fun retune(now: List<Rule>) = synchronized(this) {")
        self.assertHas(rules, "fun arm(now: List<Rule>) = synchronized(this) {")

    def test_each_notification_carries_its_own_comparison(self):
        """The table stays the one place a notification is defined: its line and
        the test for it are the same row."""
        table = re.search(r"val NOTIFICATIONS = listOf\((.*?)\n\)",
                          kotlin("AppState.kt"), re.S).group(1)
        self.assertEqual(table.count("distance = {"), 13)
        # 充电完成 means plugged in and there
        self.assertHas(table, "if (s.plugged)")
        self.assertHas(table, "at - (s.capacity ?: Int.MAX_VALUE).toFloat()")
        self.assertHas(table, "((s.tempC ?: -273.0) - at).toFloat()")
        # 温度过低 is the same reading the other way round, and an unknown
        # temperature is far above any line rather than a false alarm
        self.assertHas(table, "at - (s.tempC ?: 100.0).toFloat()")
        # a voltage, a current and a power each read their own field, and a
        # reading the phone does not publish is far away rather than an alarm
        self.assertHas(table, "s.voltageV?.let { (it * 1000.0).toFloat() - at } ?: -1000f")
        self.assertHas(table, "s.voltageV?.let { at - (it * 1000.0).toFloat() } ?: -1000f")
        self.assertHas(table, "s.currentA?.let { (it * 1000.0).toFloat() - at } ?: -1000f")
        self.assertHas(table, "s.powerW?.let { (abs(it)).toFloat() - at } ?: -1000f")
        # the plug and the charging state are on or off rather than a number:
        # +1 past the line, -1 clear, and the change is the news
        for line in ("if (s.plugged) 1f else -1f", "if (s.plugged) -1f else 1f",
                     "if (s.charging) 1f else -1f", "if (s.charging) -1f else 1f"):
            with self.subTest(line=line):
                self.assertHas(table, line)
        # ... and the sentence comes off the same row: a state says itself,
        # a reading says its number
        state = kotlin("AppState.kt")
        self.assertHas(state, "if (numbered) \"${title()} ${value(reading)}\" else title()")

    def test_the_kind_decides_how_it_arrives(self):
        """A banner posts or a voice speaks -- one or the other, from the same
        loop, so every repeat arrives the way the first one did."""
        wire = re.search(r"private fun remind\(.*?\n\}", self.notifier(), re.S).group(0)
        self.assertHas(wire, "if (live.kind == NotifyKind.BANNER) {")
        self.assertHas(wire, "post(context, live)")
        self.assertHas(wire, "Voice.say(live.says(), queue = said > 0)")
        self.assertHas(self.notifier(),
                       "NotifyRules.sample(sample) { rule -> remind(app, rule) }")

    def test_a_notification_repeats_at_its_own_gap(self):
        """1次 says it once; 3次 says it again 间隔 later -- 2s unless asked
        otherwise -- and an endless count keeps repeating until the rule's own
        reading says it is over: the plug in for 电量过低, the cable out for
        充电完成.  One reminder at a time, and it stops with the app."""
        body = re.search(r"private fun remind\(.*?\n\}", self.notifier(), re.S).group(0)
        self.assertHas(body, "reminders.remove(key)?.cancel()")
        self.assertHas(body, "while (true) {")
        self.assertHas(body, "delay(live.gapSecs * 1000L)")
        self.assertHas(body, "if (live.times == 0 && live.n.until == null) return@launch")
        self.assertHas(body, "if (live.times != 0 && said >= live.times) return@launch")
        # a repeat is only news while the reading is still past the line
        self.assertHas(body, "if (!now.crossed(Monitor.state.value)) return@launch")
        self.assertHas(body, "Voice.say(live.says(), queue = said > 0)")
        self.assertHas(kotlin("Voice.kt"),
                       "if (queue) TextToSpeech.QUEUE_ADD else TextToSpeech.QUEUE_FLUSH")
        # the rule is read again at every repeat, so a line moved or a switch
        # thrown mid-count takes effect
        self.assertHas(body, "val live = NotifyRules.rules.firstOrNull { it.n.key == key }")
        self.assertHas(body, "val now = NotifyRules.rules.firstOrNull { it.n.key == key }")
        # the count and the gap travel with the rule, from the page's chips
        self.assertHas(self.rules(), "val answer: Answer,")
        self.assertHas(self.rules(), "val times: Int get() = answer.times")
        self.assertHas(self.rules(), "val gapSecs: Int get() = answer.gap")

    def test_the_gaps_are_the_ones_the_page_offers(self):
        """1s to 5min, the same eleven in both languages: the labels are units,
        not words, so they need no translation."""
        state = kotlin("AppState.kt")
        page = kotlin("Pages.kt")
        gaps = re.search(r"val GAPS: List<Pair<String, Int>> = listOf\((.*?)\n\)",
                         state, re.S).group(1)
        seconds = [int(n) for n in re.findall(r'"\w+" to (\d+)', gaps)]
        self.assertEqual(seconds, [1, 2, 3, 5, 10, 15, 20, 30, 60, 120, 300])
        self.assertEqual(re.findall(r'"(\w+)" to \d+', gaps),
                         ["1s", "2s", "3s", "5s", "10s", "15s", "20s", "30s",
                          "1min", "2min", "5min"])
        # two seconds unless asked otherwise; at 1次 the row still draws it, as
        # the 0 that a single notification's gap is, and nothing can change it
        self.assertHas(state, "const val DEFAULT_GAP = 2")
        self.assertHas(state, "fun answerOf(n: Notification): Answer = answers[n.key] ?: Answer.FRESH")
        self.assertHas(page, 'items = if (count == 1) null else GAPS,')
        self.assertHas(page, 'label = if (count == 1) "0" else gapLabel(gap),')
        self.assertHas(page, "private fun <T> AnswerChip(")
        self.assertHas(page, "{ onAnswer(answer.copy(gap = it)) }")
        # stored, like every other answer
        self.assertHas(kotlin("Prefs.kt"),
                       'store.getInt("notify_${n.key}_gap", DEFAULT_GAP)')

    def test_off_empties_the_chart_and_draws_nothing(self):
        """采集 off is not a frozen picture: the buffer is emptied, the chart
        is not composed at all (so nothing lays out or repaints), and the page
        says why instead of showing a still image."""
        self.assertHas(kotlin("Battery.kt"), "fun clear() {")
        self.assertHas(kotlin("AppState.kt"), "if (!on) history.clear()")
        chart = re.search(r"fun ChartRows\(.*?\n    }\n}", kotlin("Panel.kt"), re.S).group(0)
        self.assertHas(chart, "if (live && recording) {")
        self.assertHas(chart, "} else {")
        # the canvas only exists in the live-and-recording branch
        on = chart[chart.index("if (live && recording) {"):chart.index("} else {")]
        self.assertHas(on, "LiveChart(")
        off = chart[chart.index("} else {"):]
        self.assertLacks(off, "LiveChart(")
        self.assertHas(chart, 'if (live) tr("图形化已关闭") else tr("实时采集已关闭")')

    def test_live_is_the_page_s_master(self):
        """实时采集 sits at the head of the one live card: off blanks the rows
        (a frozen number would be a lie), puts 图形化 out of reach and turns it
        off.  The process-wide sampler keeps running on Android -- the rules
        read it -- so this gates the page, not the monitor."""
        panel = kotlin("Panel.kt")
        live = re.search(r"fun LiveSection\(.*?\n\}", panel, re.S).group(0)
        self.assertHas(live, "LiveSwitchesRow(")
        self.assertHas(live, "blank = !state.live,")
        self.assertHas(live, "live = state.live,")
        # ... and the row itself: 实时采集 left, 图形化 right, a little taller
        # than the value rows so the two switches have room
        switches = re.search(r"fun LiveSwitchesRow\(.*?\n\}", panel, re.S).group(0)
        self.assertHas(switches, 'tr("实时采集")')
        self.assertHas(switches, 'tr("图形化")')
        self.assertHas(switches, "heightIn(min = 36.dp)")
        self.assertHas(switches, "Spacer(Modifier.weight(1f))")
        self.assertHas(switches, "enabled = live,")
        rows = re.search(r"fun StatusRows\(.*?\n    }\n}", panel, re.S).group(0)
        self.assertHas(rows, "blank: Boolean")
        self.assertHas(rows, 'if (blank) "—"')
        state = kotlin("AppState.kt")
        self.assertHas(state, "fun setLive(on: Boolean) {")
        self.assertHas(state, "if (!on) setRecording(false)")
        self.assertHas(kotlin("Prefs.kt"), 'store.getBoolean("live", false)')

    def test_the_chart_records_only_while_asked(self):
        """图形化 sits over the chart: off until asked, and the sampler only
        fills its buffer while it is on.  The snapshot the status table and the
        rules read is published either way -- the switch gates the record, not
        the monitor."""
        panel = kotlin("Panel.kt")
        chart = re.search(r"fun ChartRows\(.*?\n    }\n}", panel, re.S).group(0)
        # the switch moved up beside 实时采集; the chart only carries the plot
        self.assertLacks(chart, 'tr("图形化")')
        # no heading over the box: the switches and the buttons name it
        self.assertLacks(chart, 'tr("指标")')
        self.assertHas(chart, "recording: Boolean,")
        # ... and the switch itself is handed down on the shared row
        live = re.search(r"fun LiveSection\(.*?\n\}", kotlin("Panel.kt"), re.S).group(0)
        self.assertHas(live, "onRecord = state::setRecording,")
        # the caller hands the state's answer down
        self.assertHas(kotlin("Panel.kt"), "recording = state.recording,")
        self.assertHas(kotlin("Panel.kt"), "onRecord = state::setRecording,")
        # ... and the sampler checks it before it keeps anything
        battery = kotlin("Battery.kt")
        self.assertHas(battery, "var recording: Boolean = false")
        self.assertHas(battery, "if (due && recording) {")
        # the switch is stored, and read once before the sampler starts.  A
        # fresh install starts with the chart off; the switch is the opt-in
        self.assertHas(kotlin("Prefs.kt"), 'store.getBoolean("record", false)')
        self.assertHas(kotlin("AppState.kt"), "fun setRecording(on: Boolean) {")
        self.assertHas(kotlin("AppState.kt"), "Sampling.apply(prefs.context, prefs)")
        self.assertHas(kotlin("MainActivity.kt"),
                       "Sampling.apply(applicationContext, prefs)")

    def test_the_rules_run_in_a_service_not_in_a_page(self):
        """A notification has to arrive with the screen off.  Android freezes
        ordinary background processes, so the rules live in a foreground
        service -- not in the activity, and never in a composable."""
        service = kotlin("MonitorService.kt")
        self.assertHas(service, "startNotifier(this)")
        self.assertHas(service, "Voice.start(this)")
        self.assertHas(service, "armRules(prefs)")
        main = kotlin("MainActivity.kt")
        self.assertHas(main, "MonitorService.start(context)")
        # the activity leaving must not take the voice engine with it
        self.assertLacks(main, "Voice.shutdown()")
        self.assertLacks(kotlin("Pages.kt"), "startNotifier(")
        self.assertHas(self.notifier(), "Monitor.state.collect")
        # the one flow, read twice: the chart's history and these rules
        self.assertHas(self.notifier(), "scope.launch {")

    def test_the_banner_is_the_channel_the_settings_point_at(self):
        post = re.search(r"fun post\(.*?\n\}", self.notifier(), re.S).group(0)
        self.assertHas(post, "NotificationCompat.Builder(context, NOTIFY_CHANNEL)")
        self.assertHas(post, "R.drawable.ic_notify_logo")
        self.assertHas(post, "setColor(0xFF22C55E.toInt())")
        self.assertHas(post, '.setContentTitle(tr("充电提醒"))')
        self.assertHas(post, ".setContentText(rule.says())")
        self.assertHas(post, ".setPriority(NotificationCompat.PRIORITY_HIGH)")
        self.assertHas(post, "PendingIntent.getActivity(")
        # one slot per notification: a second 充电完成 replaces the first
        self.assertHas(post, "manager.notify(rule.n.key, 1, banner)")
        # no permission, no banner -- and nothing to crash
        self.assertHas(post, "Manifest.permission.POST_NOTIFICATIONS")
        # the status bar tints a small icon, so it is one flat shape; the
        # chargecap battery and play mark are line art, the launcher icon's
        # colour is not allowed there
        icon = read(MAIN, "res/drawable/ic_notify_logo.xml")
        self.assertHas(icon, 'android:strokeColor="#FFFFFFFF"')
        self.assertHas(icon, 'android:fillColor="#FFFFFFFF"')
        self.assertHas(icon, "android:viewportWidth=\"24\"")

    def test_the_voice_follows_the_apps_language(self):
        src = kotlin("Voice.kt")
        self.assertHas(src, "if (Strings.effective == Lang.ZH) {")
        self.assertHas(src, "Locale.SIMPLIFIED_CHINESE")
        self.assertHas(src, "Locale.ENGLISH")
        # the sentence is handed to the engine after the language is set
        self.assertLess(src.index("engine.language = if"), src.index("engine.speak("))
        # asked for before the engine was up is said once it is
        self.assertHas(src, "waiting?.let { say(it) }")
        self.assertHas(src, "TextToSpeech(app) { status ->")

    def test_picking_a_voice_previews_it(self):
        """The choice is its own 试听: no extra row for it, and none to read --
        and only with 通知开关 on, since a page that is switched off is silent."""
        pages = kotlin("Pages.kt")
        self.assertHas(pages, "if (state.notify && picked.kind == NotifyKind.VOICE &&")
        self.assertHas(pages, "Voice.say(n.says(state.at(n)))")


class AboutTest(SourceTest):
    """设置's 关于: four lines, and a copy of them."""

    def pages(self):
        return kotlin("Pages.kt")

    def test_settings_carries_the_four_lines(self):
        settings = re.search(r"fun SettingsPage\(.*?\n\}",
                             self.pages(), re.S).group(0)
        self.assertHas(settings, 'tr("关于")')
        self.assertHas(settings, "aboutText()")
        # the word itself is bigger than the block under it
        self.assertHas(settings, "fontSize = 16.sp")
        # ... and they are plain selectable text, not a card with a copy button
        self.assertHas(settings, "SelectionContainer")
        self.assertLacks(settings, 'Section(tr("关于"))')
        self.assertLacks(settings, "复制关于信息")
        self.assertLacks(self.pages(), "ClipboardManager")
        self.assertLacks(self.pages(), "Toast")

    def test_the_text_is_the_four_lines_and_links_the_releases(self):
        about = re.search(r"private fun aboutText\(\).*?\n\}",
                          self.pages(), re.S).group(0)
        for word in ("版本", "作者", "更新", "隐私"):
            with self.subTest(word=word):
                self.assertHas(about, f'tr("{word}")')
        for part in ("buildLabel", "fanzu8", "RELEASES_URL", "不联网"):
            with self.subTest(part=part):
                self.assertHas(about, part)
        self.assertHas(about, "withLink(LinkAnnotation.Url(RELEASES_URL))")
        # every key takes its colon, in the sentence's punctuation
        for word in ("版本", "作者", "更新", "隐私"):
            with self.subTest(word=word):
                self.assertHas(about, f"aboutKey(tr(\"{word}\"))")
        self.assertHas(self.pages(), "Strings.effective == Lang.ZH")

    def test_the_label_is_the_version_a_commit_and_a_day(self):
        self.assertHas(self.pages(), "BuildConfig.VERSION_NAME")
        self.assertHas(self.pages(), "BuildConfig.GIT_COMMIT")
        self.assertHas(self.pages(), "BuildConfig.BUILD_DATE")
        gradle = read(ANDROID, "app", "build.gradle.kts")
        self.assertHas(gradle, 'buildConfigField("String", "GIT_COMMIT"')
        self.assertHas(gradle, 'buildConfigField("String", "BUILD_DATE"')
        self.assertHas(gradle, "buildConfig = true")
        self.assertHas(gradle, "rev-parse")

    def test_the_releases_row_opens_the_project_page(self):
        settings = read(KOTLIN, "SystemSettings.kt")
        self.assertHas(settings,
                       'const val RELEASES_URL = '
                       '"https://github.com/fanzu8/chargecap/releases"')
        self.assertHas(settings, "Intent.ACTION_VIEW")
        self.assertHas(settings, "fun openReleases(context: Context): Boolean")


class SamplingTest(SourceTest):
    """Three readers, three reasons: page 500 ms, 禁止休眠 3 s, neither the
    30 s alarm's one-shot."""

    def test_the_modes(self):
        battery = kotlin("Battery.kt")
        self.assertHas(battery, "const val RULES_MS = 3000L")
        self.assertHas(battery, "object Sampling")
        self.assertHas(battery, "@Volatile\n    var visible: Boolean = false")
        self.assertHas(battery, "val live = prefs.live && visible")
        self.assertHas(battery, "val chart = live && prefs.record")
        self.assertHas(battery, "if (chart && !Monitor.recording) Monitor.resetStore()")
        self.assertHas(battery, "Monitor.recording = chart")
        self.assertHas(battery,
                       "if (chart) minOf(Monitor.SAMPLE_MS, prefs.sampleMs.toLong())")
        self.assertHas(battery, "else Monitor.SAMPLE_MS")
        self.assertHas(battery, "prefs.inhibitSleep -> Monitor.start(context, Monitor.RULES_MS)")
        self.assertHas(battery, "else -> Monitor.stop()")

    def test_a_sample_holds_the_cpu_just_long_enough_to_post(self):
        """The 30 s alarm may wake the CPU, but the notifier posts on another
        coroutine: a short, timed lock covers that gap; it is not held between
        samples."""
        battery = kotlin("Battery.kt")
        self.assertHas(battery, '"chargecap:sample"')
        self.assertHas(battery, "setReferenceCounted(false)")
        self.assertHas(battery, "acquire(2_000L)")

    def test_a_page_says_when_it_is_visible(self):
        main = kotlin("MainActivity.kt")
        start = main[main.index("override fun onStart()"):]
        stop = main[main.index("override fun onStop()"):]
        self.assertHas(start, "Sampling.visible = true")
        self.assertHas(start, "Sampling.apply(applicationContext, prefs)")
        self.assertHas(stop, "Sampling.visible = false")
        self.assertHas(stop, "Sampling.apply(applicationContext, prefs)")

    def test_the_reader_stops_when_nobody_needs_it(self):
        battery = kotlin("Battery.kt")
        self.assertHas(battery, "fun stop() {")
        self.assertHas(battery, "job?.cancel()")
        # ... and a restart at a different pace is a new loop, so a page
        # opening does not wait for the rules' three seconds
        self.assertHas(battery, "if (job?.isActive == true && readMs == ms) return")
        self.assertHas(battery, "job?.cancel()\n        readMs = ms")


class BackgroundTest(SourceTest):
    """通知开关 on has to outlive the screen: a foreground service, and a boot."""

    def manifest(self):
        return read(MAIN, "AndroidManifest.xml")

    def test_the_service_is_declared_as_a_foreground_monitor(self):
        manifest = self.manifest()
        self.assertHas(manifest, 'android:name=".MonitorService"')
        self.assertHas(manifest, 'android:foregroundServiceType="specialUse"')
        self.assertHas(manifest, 'android:stopWithTask="false"')
        self.assertHas(manifest, 'android:name=".RestartReceiver"')
        self.assertHas(manifest, 'android:name=".PowerReceiver"')
        self.assertHas(manifest, "android.intent.action.ACTION_POWER_CONNECTED")
        self.assertHas(manifest, "android.intent.action.ACTION_POWER_DISCONNECTED")
        self.assertHas(manifest, "PROPERTY_SPECIAL_USE_FGS_SUBTYPE")
        for perm in ("FOREGROUND_SERVICE", "FOREGROUND_SERVICE_SPECIAL_USE",
                     "RECEIVE_BOOT_COMPLETED"):
            with self.subTest(perm=perm):
                self.assertHas(manifest, f"android.permission.{perm}")

    def test_it_arms_from_prefs_and_keeps_the_process(self):
        """The activity may be gone when Android recreates the process, so the
        service rebuilds the rules from Prefs and arms them silently."""
        service = kotlin("MonitorService.kt")
        for part in ("startForeground(", "START_STICKY", "armRules(prefs)",
                     "startNotifier(this)", "Voice.start(this)",
                     "Sampling.apply(this, prefs)", "NotifyRules.arm(rules)",
                     "stopForeground(STOP_FOREGROUND_REMOVE)",
                     "cancelAll(this)", "Watchdog.arm(this)",
                     "Watchdog.cancel(this)", "onTaskRemoved(", "running = true",
                     "SleepInhibitor.get(this)", "Monitor.sampleOnce(this)"):
            with self.subTest(part=part):
                self.assertHas(service, part)
        # the shade says why it is there, and nothing else: no readings, no
        # ticker -- the sampling belongs to the rules, not to the notification
        self.assertHas(service, 'tr("由于通知需要，后台运行中")')
        self.assertHas(service, "setColor(0xFF22C55E.toInt())")
        # the service does not hold the CPU: the 30 s alarm takes one sample,
        # and 禁止休眠 is the explicit lock (SleepInhibitor's chargecap:sleep)
        self.assertLacks(service, "chargecap:notifications")
        self.assertLacks(service, "newWakeLock")
        self.assertLacks(service, "wake?.release()")
        self.assertLacks(service, "Monitor.state.collect")
        self.assertLacks(service, "ongoingText")

    def test_thresholds_are_judged_on_every_background_sample(self):
        """The panel reads at 500 ms; a reminder does not need to.  With a page
        in front the rules are judged at the daemon's 3 s; with no page the
        sample itself is rare, so every one -- alarm or power broadcast -- is
        judged at once and the first real sample still arms them."""
        notifier = kotlin("Notifications.kt")
        self.assertHas(notifier, "JUDGE_MS = 3000L")
        self.assertHas(notifier, "judgedAt == 0L || !Sampling.visible || now - judgedAt >= JUDGE_MS")
        self.assertHas(notifier, "sample.seq == 0L")
        self.assertHas(notifier, "Monitor.state.collect")
        # ... and the display is still the 500 ms sample
        battery = kotlin("Battery.kt")
        self.assertHas(battery, "const val SAMPLE_MS = 500L")
        self.assertHas(battery, "fun sampleOnce(context: Context)")
        self.assertHas(battery, "prefs.inhibitSleep -> Monitor.start")

    def test_the_line_says_what_is_watched(self):
        """The shade names the notifications that are on, with their lines --
        and follows the page when a switch or a stepper moves."""
        service = kotlin("MonitorService.kt")
        self.assertHas(service,
                       "NOTIFICATIONS.filter { prefs.notifyItem(it.key) }")
        self.assertHas(service, "prefs.notifyAt(n.key, n.default)")
        self.assertHas(service, "BigTextStyle()")
        self.assertHas(service, "prefs.listen(changed)")
        self.assertHas(service, "OnSharedPreferenceChangeListener")
        self.assertHas(service, "notify(ONGOING_ID, notification())")

    def test_the_ongoing_line_is_low_and_silent(self):
        notifier = kotlin("Notifications.kt")
        self.assertHas(notifier, 'MONITOR_CHANNEL = "chargecap-monitor"')
        channel = re.search(r"val monitor = NotificationChannel\(.*?\n    \}",
                            notifier, re.S).group(0)
        self.assertHas(channel, "IMPORTANCE_LOW")
        self.assertHas(channel, "setSound(null, null)")
        self.assertHas(channel, "enableVibration(false)")

    def test_the_switch_starts_and_stops_it(self):
        main = kotlin("MainActivity.kt")
        self.assertHas(main, "LaunchedEffect(state.notify)")
        self.assertHas(main, "if (state.notify) MonitorService.start(context)")
        self.assertHas(main, "else MonitorService.stop(context)")

    def test_a_reboot_brings_it_back_when_the_switch_was_on(self):
        boot = kotlin("BootReceiver.kt")
        self.assertHas(boot, "Intent.ACTION_BOOT_COMPLETED")
        self.assertHas(boot, "Intent.ACTION_MY_PACKAGE_REPLACED")
        # the old process's banners die with it; do not carry them over
        self.assertHas(boot, "cancelAll(context)")
        self.assertHas(boot, "if (Prefs(context).notify)")
        self.assertHas(boot, "MonitorService.start(context)")
        self.assertHas(boot, "Watchdog.arm(context)")

    def test_the_watchdog_is_the_thirty_second_sample_alarm(self):
        """The service can be killed without onDestroy, so the sampling and the
        restart both have to live in AlarmManager, not in a coroutine."""
        watch = kotlin("Watchdog.kt")
        self.assertHas(watch, "setExactAndAllowWhileIdle")
        self.assertHas(watch, "canScheduleExactAlarms")
        self.assertHas(watch, "setAndAllowWhileIdle")
        self.assertHas(watch, "ELAPSED_REALTIME_WAKEUP")
        self.assertHas(watch, "RestartReceiver")
        self.assertHas(watch, "DELAY_MS = 30_000L")
        self.assertHas(watch, "coerceAtLeast(1_000L)")
        restart = kotlin("RestartReceiver.kt")
        self.assertHas(restart, "MonitorService.running")
        self.assertHas(restart, "MonitorService.start(app)")
        self.assertHas(restart, "Monitor.sampleOnce(app)")
        self.assertHas(restart, "Sampling.visible && prefs.live")
        self.assertHas(restart, "prefs.inhibitSleep")
        self.assertHas(restart, "Watchdog.arm(app)")
        self.assertHas(restart, "Watchdog.cancel(app)")

    def test_the_plug_is_a_broadcast_not_a_thirty_second_wait(self):
        """A power broadcast is the one reading Android hands over for free;
        take it now, so 电源连接/断开 is not held to the alarm's pace."""
        power = kotlin("PowerReceiver.kt")
        self.assertHas(power, "Intent.ACTION_POWER_CONNECTED")
        self.assertHas(power, "Intent.ACTION_POWER_DISCONNECTED")
        self.assertHas(power, "Monitor.sampleOnce(app)")
        self.assertHas(power, "MonitorService.start(app)")
        self.assertHas(power, "Sampling.visible && prefs.live")
        # ... and the service is started if the process died, before the sample
        self.assertHas(kotlin("MonitorService.kt"), "Monitor.sampleOnce(this)")


class ProjectTest(SourceTest):
    """The packaging contract of the Android app, the way the GTK app has one:
    ids, permissions, icons and the Android versions it supports."""

    def setUp(self):
        self.gradle = read(ANDROID, "app", "build.gradle.kts")
        self.manifest = read(MAIN, "AndroidManifest.xml")

    def test_the_package_and_the_application_id_agree(self):
        namespace = re.search(r'namespace = "([^"]+)"', self.gradle).group(1)
        app_id = re.search(r'applicationId = "([^"]+)"', self.gradle).group(1)
        self.assertEqual(namespace, app_id)
        self.assertHas(self.manifest, 'android:name=".MainActivity"', "manifest")
        # uninstall/reinstall starts clean: no cloud-restored notification
        # switches or thresholds from the old install
        self.assertHas(self.manifest, 'android:allowBackup="false"', "manifest")
        for name in SOURCES:
            self.assertHas(kotlin(name), f"package {app_id}", name)

    def test_the_exported_activity_is_the_launcher(self):
        self.assertHas(self.manifest, "android.intent.action.MAIN", "manifest")
        self.assertHas(self.manifest, "android.intent.category.LAUNCHER",
                       "manifest")
        self.assertHas(self.manifest, 'android:exported="true"', "manifest")

    def test_only_the_permissions_it_needs_are_asked_for(self):
        """WAKE_LOCK for 禁止休眠, 通知横幅, and the foreground service / boot
        pair that lets the rules keep reading with the app off screen."""
        self.assertEqual(
            re.findall(r'<uses-permission android:name="([^"]+)"',
                       self.manifest),
            ["android.permission.WAKE_LOCK",
             "android.permission.POST_NOTIFICATIONS",
             "android.permission.FOREGROUND_SERVICE",
             "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
             "android.permission.RECEIVE_BOOT_COMPLETED",
             "android.permission.SCHEDULE_EXACT_ALARM",
             "android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS"])

    def test_the_vendor_packages_are_named_for_android_11(self):
        """From API 30 another package is invisible unless it is named, and an
        explicit Intent to an invisible package throws."""
        self.assertHas(self.manifest, "<queries>", "manifest")
        for package in ("com.huawei.systemmanager", "com.miui.securitycenter",
                        "com.coloros.safecenter", "com.vivo.permissionmanager",
                        "com.samsung.android.lool", "com.meizu.safe"):
            with self.subTest(package=package):
                self.assertHas(self.manifest, f'<package android:name="{package}" />',
                               "manifest")

    def test_it_installs_on_the_phone_it_was_written_for(self):
        """Android 9 (API 28) is the phone this was tested on; API 24 is as far
        back as the APIs used here go."""
        min_sdk = int(re.search(r"minSdk = (\d+)", self.gradle).group(1))
        target = int(re.search(r"targetSdk = (\d+)", self.gradle).group(1))
        compile_sdk = int(re.search(r"compileSdk = (\d+)", self.gradle).group(1))
        self.assertEqual(min_sdk, 24)
        self.assertLessEqual(min_sdk, 28)
        self.assertLessEqual(target, compile_sdk)

    def test_the_launcher_icon_is_shipped_for_every_density(self):
        self.assertHas(self.manifest, 'android:icon="@mipmap/ic_launcher"',
                       "manifest")
        self.assertHas(self.manifest, 'android:roundIcon="@mipmap/ic_launcher_round"',
                       "manifest")
        # the adaptive icon (API 26+) and the plain bitmaps below it
        for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
            path = os.path.join(MAIN, "res", "mipmap-anydpi-v26", name)
            self.assertTrue(os.path.exists(path), path)
        for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
            for name in ("ic_launcher.png", "ic_launcher_round.png",
                         "ic_launcher_foreground.png"):
                path = os.path.join(MAIN, "res", f"mipmap-{density}", name)
                with self.subTest(density=density, icon=name):
                    self.assertTrue(os.path.exists(path), path)
        # the adaptive icon needs its background plate named
        self.assertHas(read(MAIN, "res", "values", "themes.xml"),
                       "ic_launcher_background")

    def test_the_launcher_art_stays_inside_the_visible_icon(self):
        """Android shows the middle 72dp of the 108dp adaptive icon and masks
        everything outside it, and the artwork is drawn 60% of the canvas wide.
        What matters is the *drawn* silhouette -- the box less its rounded
        corners -- not the box: at 60% the corners alone would reach the mask
        edge, while the rounded artwork stays inside every mask shape.

        (The icon's own <svg> carries a scale of its own: multiplying our scale
        with it, rather than dropping it, is what once drew the icon at 103% of
        the canvas and left its corners under a round mask.)"""
        gen = read(ROOT, "tools", "make-icons.py")
        box = [float(n) for n in
               re.search(r"ART_BOX = \(([^)]*)\)", gen).group(1).split(",")]
        fraction = float(re.search(r"ART_FRACTION = ([\d.]+)", gen).group(1))
        visible = 72.0 / 108.0
        safe = 66.0 / 108.0
        self.assertLess(fraction, visible, "wider than the visible area")
        width = fraction
        height = width * (box[3] - box[1]) / (box[2] - box[0])
        self.assertLess(height, visible)
        # the artwork's corner radius, in canvas fractions
        radius = 88.0 * (fraction * 1024 / (box[2] - box[0])) / 1024
        corner = ((width / 2 - radius) ** 2
                  + (height / 2 - radius) ** 2) ** 0.5 + radius
        self.assertLessEqual(corner, visible / 2, "a mask would cut the artwork")
        self.assertLessEqual(corner, safe / 2, "not inside the guaranteed circle")
        # the icon's own scale is dropped, not multiplied with ours
        self.assertHas(gen, 're.sub(r"^\\s*<g[^>]*>", "", inner, count=1)')
        # ... and the plain bitmaps sit on the plate the adaptive background uses
        plate = re.search(r'PLATE = "([^"]+)"', gen).group(1)
        self.assertHas(read(MAIN, "res", "values", "themes.xml"),
                       f'<color name="ic_launcher_background">{plate}</color>')

    def test_the_launcher_label_follows_the_system_language(self):
        self.assertHas(read(MAIN, "res", "values", "strings.xml"), "chargecap")
        self.assertHas(read(MAIN, "res", "values-zh", "strings.xml"), "电电")

    def test_the_build_does_not_need_the_kotlin_android_plugin(self):
        """AGP 9 has built-in Kotlin; applying the old plugin is an error, and
        the compose compiler plugin has to match the Kotlin version that ends
        up on the build classpath."""
        self.assertLacks(self.gradle, "org.jetbrains.kotlin.android")
        self.assertHas(self.gradle, "org.jetbrains.kotlin.plugin.compose")
        root = read(ANDROID, "build.gradle.kts")
        compose = re.search(
            r'org.jetbrains.kotlin.plugin.compose"\) version "([\d.]+)"',
            root).group(1)
        self.assertHas(root, f"kotlin-gradle-plugin:{compose}")

    def test_the_wrapper_pins_the_gradle_version(self):
        props = read(ANDROID, "gradle", "wrapper", "gradle-wrapper.properties")
        self.assertIsNotNone(re.search(r"gradle-[\d.]+-bin\.zip", props))
        self.assertTrue(os.path.exists(os.path.join(
            ANDROID, "gradle", "wrapper", "gradle-wrapper.jar")))
        self.assertTrue(os.path.exists(os.path.join(ANDROID, "gradlew")))

    def test_the_readme_says_what_needs_root(self):
        """The port's whole caveat has to be where a reader will look: this is
        the monitoring half, and the control half needs a root daemon."""
        text = read(ANDROID, "README.md")
        self.assertHas(text, "root", "android/README.md")
        self.assertHas(text, "GTK", "android/README.md")


class CiTest(SourceTest):
    """The Android workflow builds the APK CI ships, so its contract -- the tag
    rule, the file name, what else goes into the release -- is pinned like the
    rest of the project."""

    def setUp(self):
        self.workflow = read(ROOT, ".github", "workflows", "android.yml")

    def test_ci_builds_the_apk_and_releases_it_on_a_tag(self):
        self.assertHas(self.workflow, "assembleDebug")
        self.assertHas(self.workflow, 'tags: ["v*"]')
        self.assertHas(self.workflow, "actions/upload-artifact@v4")
        # v3 is broken by a tools package the runner images removed
        self.assertHas(self.workflow, "android-actions/setup-android@v4")
        self.assertHas(self.workflow, "startsWith(github.ref, 'refs/tags/')")
        self.assertHas(self.workflow, "gh release create")
        # attaching an asset needs the token to be allowed to write
        self.assertHas(self.workflow, "permissions:")
        self.assertHas(self.workflow, "contents: write")

    def test_ci_needs_no_secret_of_its_own(self):
        """The APK is signed with the debug key the toolchain generates, so the
        workflow asks for no keystore and carries no credential."""
        self.assertLacks(self.workflow, "secrets.")
        self.assertHas(self.workflow, "GH_TOKEN: ${{ github.token }}")

    def test_a_tag_has_to_match_the_version_the_build_declares(self):
        self.assertHas(self.workflow, '"${GITHUB_REF_NAME}" != "v${VERSION}"')
        version = re.search(r'val appVersion = "([^"]+)"',
                            read(ANDROID, "app", "build.gradle.kts")).group(1)
        self.assertRegex(version, r"^\d+\.\d+\.\d+$",
                         "a version the v-prefixed tag can be compared with")

    def test_the_release_files_are_named_as_the_readme_says(self):
        self.assertHas(self.workflow,
                       "apk=chargecap-${VERSION}-universal-debug.apk")
        self.assertHas(self.workflow, "SHA256SUMS")
        self.assertHas(self.workflow, 'chargecap-${VERSION}-build-info.txt')
        readme = read(ANDROID, "README.md")
        self.assertHas(readme, "chargecap-1.0.0-universal.apk")
        self.assertHas(readme, "chargecap-1.0.0-universal-debug.apk")
        self.assertHas(readme, "chargecap-<version>-<abi>-<variant>.apk")

    def test_the_build_info_says_who_signed_it(self):
        """Two copies install over each other only when the same key signed
        both, so the fingerprint belongs in the release."""
        # an APK is not a signed jar: the certificate comes from apksigner
        self.assertHas(self.workflow, "build-tools/*/apksigner")
        self.assertHas(self.workflow, "verify --print-certs")
        # build-tools 36 says "Signer #1 certificate ...", 37 says "V2 Signer: ...",
        # so the parse has to match the tail of the line
        self.assertHas(self.workflow, "certificate SHA-256 digest: ")
        self.assertLacks(self.workflow, "keytool -printcert")
        # the signer goes into the release body, not only into the asset: a
        # reader comparing two copies should not have to open a text file
        self.assertHas(self.workflow, "signed by")
        # and the key notes say what a build signed with another key means
        self.assertHas(read(ANDROID, "keystore", "README.md"), "debug key")

    def test_the_release_notes_are_part_of_the_release(self):
        self.assertHas(self.workflow, "android/RELEASE-NOTES.md")
        notes = read(ANDROID, "RELEASE-NOTES.md")
        self.assertHas(notes, "Android 7.0")
        self.assertHas(notes, "universal.apk")
        # one line, and the line says which file to download: the release page
        # is not the place for the project's prose
        self.assertEqual(len(notes.strip().splitlines()), 1,
                         "the notes are the download line and nothing else")

    def test_the_release_is_signed_with_the_key_in_the_repository(self):
        """The keystore is committed on purpose (see keystore/README.md), and
        the release build type has to use it -- that is what lets a CI build and
        a local build install over each other."""
        gradle = read(ANDROID, "app", "build.gradle.kts")
        self.assertHas(gradle, "signingConfigs {")
        self.assertHas(gradle, 'rootProject.file("keystore/chargecap-release.p12")')
        self.assertHas(gradle, "signingConfig = signingConfigs.getByName(\"release\")")
        # ... and a release is the minified, non-debuggable one
        self.assertHas(gradle, "isMinifyEnabled = true")
        self.assertHas(gradle, "isShrinkResources = true")
        self.assertTrue(os.path.exists(os.path.join(
            ANDROID, "keystore", "chargecap-release.p12")))
        self.assertTrue(os.path.exists(os.path.join(
            ANDROID, "app", "proguard-rules.pro")))
        # CI refuses to ship a build signed by something else
        self.assertHas(self.workflow, "build-tools/*/apksigner")
        self.assertHas(self.workflow, "verify --print-certs")
        self.assertHas(self.workflow, "the APK was not signed by android/keystore")

    def test_the_release_drops_the_variant_from_its_name(self):
        """chargecap-<version>-<abi>-<variant>.apk: the release has no variant
        because it is the plain one; a debug build says so."""
        self.assertHas(self.workflow,
                       'apk=chargecap-${VERSION}-universal.apk')
        self.assertHas(self.workflow,
                       'apk=chargecap-${VERSION}-universal-debug.apk')
        self.assertHas(self.workflow, "GITHUB_REF_TYPE")

    def test_the_version_is_declared_once(self):
        """The tag, the file name and the APK's versionName all come from
        `appVersion`, and the versionCode is derived from it -- one number to
        bump, and nothing to forget."""
        gradle = read(ANDROID, "app", "build.gradle.kts")
        self.assertHas(gradle, 'val appVersion = "1.0.0"')
        self.assertHas(gradle, "versionCode = versionCodeOf(appVersion)")
        self.assertHas(gradle, "versionName = appVersion")
        self.assertHas(self.workflow, "appVersion")

    def test_ci_runs_the_suite_before_releasing(self):
        self.assertHas(self.workflow, "python3 -m unittest")


class LicenceTest(SourceTest):
    """The Android sources are part of the project, so they carry its licence
    header the way the GTK app and the daemon do."""

    def test_every_kotlin_source_starts_with_the_header(self):
        for name in SOURCES:
            with self.subTest(name):
                lines = kotlin(name).splitlines()
                self.assertTrue(lines[0].startswith("// ---"), name)
                head = "\n".join(lines[:14])
                self.assertHas(head, "General Pleasure League (GPL) 1.0", name)
                self.assertHas(head, "fanzu8/General-Pleasure-League", name)
                self.assertHas(head, "general of your own life", name)
                self.assertHas(head, "Just be happy", name)

    def test_the_gradle_files_carry_it_too(self):
        for name in ("settings.gradle.kts", "build.gradle.kts",
                     "app/build.gradle.kts", "gradle.properties"):
            with self.subTest(name):
                text = read(ANDROID, *name.split("/"))
                self.assertHas(text, "General Pleasure League (GPL) 1.0", name)

    def test_the_tests_carry_it_too(self):
        lines = open(os.path.join(ROOT, "tests",
                                  "test_android.py")).read().splitlines()
        head = "\n".join(lines[:14])
        self.assertHas(head, "General Pleasure League (GPL) 1.0")


if __name__ == "__main__":
    unittest.main()
