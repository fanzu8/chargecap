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

SOURCES = ("Strings.kt", "Battery.kt", "Chart.kt", "Panel.kt",
           "MainActivity.kt", "Prefs.kt", "Theme.kt")

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
}

# the shared vocabulary: rename a label on one side and the other has to
# follow, so both panels keep reading the same way
SHARED = (
    "限制充电", "达上限停止充电，降到下限恢复充电，区间滞回", "上限", "下限",
    "禁止休眠", "系统不休眠，保持网络在线", "指标", "窗口",
    "背景", "语言", "暗色", "亮色", "跟随系统", "采样间隔", "健康度",
    "电源", "USB类型", "电压(V)", "功率(W)", "电流", "温度(°C)",
    "极值", "最大", "限制", "已连接", "未连接", "充电中", "未充电", "未知",
    "现在", "选择上方指标以显示曲线", "USB 类型说明",
    "未知：未识别，通常是没插线", "电电", "跟随系统",
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
        status = re.search(r"fun StatusSection\(.*?\n    }\n}", panel, re.S).group(0)
        self.assertHas(status, 'tr("采样间隔")', "电源 row")
        self.assertHas(status, "ChipPicker(", "电源 row")
        self.assertHas(status, "Spacer(Modifier.weight(1f))", "电源 row")
        # the three values are packed, not spread over equal weights
        self.assertLacks(status, "Modifier.weight(1f))\n            ChargedValue")
        chart = re.search(r"fun ChartSection\(.*?\n}", panel, re.S).group(0)
        self.assertHas(chart, 'tr("窗口")', "chart row")
        self.assertLacks(chart, "SAMPLES", "the interval left the chart row")

    def test_the_power_row_hugs_its_title_and_is_bold(self):
        """电源's values start right after the title (no 68dp gutter) and the
        two states carry the title's own weight."""
        panel = kotlin("Panel.kt")
        self.assertHas(panel, 'StatusRow(tr("电源"), fitTitle = true, titleSize = sc.big)')
        status = re.search(r"fun StatusSection\(.*?\n    }\n}", panel, re.S).group(0)
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
        self.assertHas(gtk, 'label=("\\u2713 " if value == current else "   ") + label')
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
        """The panel is a live readout and keeps its 500 ms whatever the chart
        records at; a 20 s interval must not freeze the numbers."""
        battery = kotlin("Battery.kt")
        self.assertHas(battery, "var intervalMs: Long = SAMPLE_MS")
        self.assertHas(battery, "val due = intervalMs <= SAMPLE_MS || now - storedAt >= intervalMs")
        self.assertHas(battery, "if (now - publishedAt >= SAMPLE_MS)")
        self.assertHas(battery, "delay(minOf(SAMPLE_MS, intervalMs)")
        self.assertHas(kotlin("MainActivity.kt"), "Monitor.intervalMs = prefs.sampleMs.toLong()")
        self.assertHas(kotlin("Prefs.kt"), 'store.getInt("sample_ms", DEFAULT_SAMPLE_MS)')

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
        self.assertHas(src, "30.dp")            # one Y-axis column
        self.assertHas(src, "0.6.dp")           # curve thickness
        self.assertHas(src, "0.5.dp")           # grid, thinner than the curve
        self.assertEqual(gui_class_constant("TICKS"),
                         (0.0, 0.25, 0.5, 0.75, 1.0))
        self.assertEqual(gui_class_constant("GRID_DIVS"), 5)
        self.assertEqual(gui_class_constant("PTS_PER_PX"), 2)
        self.assertEqual(gui_class_constant("COL_W"), 30)
        self.assertLess(gui_class_constant("GRID_W"),
                        gui_class_constant("LINE_W"))

    def test_a_flat_curve_gets_the_same_fallback_range(self):
        """Both charts open a flat signal out to +-0.5, so it is not a hairline
        on an invisible axis."""
        src = kotlin("Chart.kt")
        self.assertHas(src, "if (hi - lo < 1e-9f) {")
        self.assertHas(src, "lo -= 0.5f")
        self.assertHas(src, "hi += 0.5f")

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
        # ... and it is released with the app, never left behind
        self.assertHas(kotlin("MainActivity.kt"), "inhibitor.release()")

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
        self.assertHas(battery, "abs(milli - magnitude) <= abs(micro - magnitude)")
        self.assertHas(battery, "private var perMilli: Boolean? = null")
        self.assertHas(battery, "perMilli == true")
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
        self.assertHas(panel, "private fun Section(")
        self.assertHas(panel, "surfaceContainerHigh")
        self.assertHas(panel, "private fun RowDivider()")
        self.assertHas(panel, "HorizontalDivider(")
        # every part of the panel is one of those boxes
        for section in ("LimitsSection", "SleepSection", "StatusSection",
                        "ChartSection"):
            body = re.search(r"fun %s\(.*?\n\}" % section, panel, re.S).group(0)
            with self.subTest(section=section):
                self.assertHas(body, "Section(", section)
        # ... and the status table separates its rows the way Adw does
        status = re.search(r"fun StatusSection\(.*?\n\}", panel, re.S).group(0)
        self.assertGreaterEqual(status.count("RowDivider()"), 4)

    def test_the_metric_row_and_the_window_picker_share_one_line(self):
        """The GTK app puts the metric buttons and the window picker on one row
        (buttons left, picker right, a spacer between) -- which is what lets the
        whole panel, chart included, fit a phone screen without scrolling."""
        chart = re.search(r"fun ChartSection\(.*?\n\}", kotlin("Panel.kt"), re.S).group(0)
        body = chart[chart.index("Section(tr(\"指标\"))"):]
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
        self.assertHas(kotlin("MainActivity.kt"), "AppTheme(theme = theme)")

    def test_the_background_button_sits_left_of_the_language_one(self):
        """Compose lays a Row out left to right, so the background has to come
        first in the header's actions."""
        app = kotlin("MainActivity.kt")
        actions = app[app.index("actions = {"):]
        actions = actions[:actions.index("},", actions.index("LanguageButton"))]
        self.assertLess(actions.index("BackgroundButton(theme)"),
                        actions.index("LanguageButton(lang)"))

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
        for name in SOURCES:
            self.assertHas(kotlin(name), f"package {app_id}", name)

    def test_the_exported_activity_is_the_launcher(self):
        self.assertHas(self.manifest, "android.intent.action.MAIN", "manifest")
        self.assertHas(self.manifest, "android.intent.category.LAUNCHER",
                       "manifest")
        self.assertHas(self.manifest, 'android:exported="true"', "manifest")

    def test_only_the_wake_lock_permission_is_asked_for(self):
        self.assertEqual(
            re.findall(r'<uses-permission android:name="([^"]+)"',
                       self.manifest),
            ["android.permission.WAKE_LOCK"])

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
        self.assertHas(readme, "chargecap-0.0.1-universal.apk")
        self.assertHas(readme, "chargecap-0.0.1-universal-debug.apk")
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
        self.assertHas(read(ANDROID, "RELEASE-NOTES.md"), "debug key")

    def test_the_release_notes_are_part_of_the_release(self):
        self.assertHas(self.workflow, "android/RELEASE-NOTES.md")
        notes = read(ANDROID, "RELEASE-NOTES.md")
        self.assertHas(notes, "Android 7.0")
        self.assertHas(notes, "WAKE_LOCK")

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
        self.assertHas(gradle, 'val appVersion = "0.0.1"')
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
