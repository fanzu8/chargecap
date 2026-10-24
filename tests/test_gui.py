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

"""Static checks on the GUI.

The GUI cannot be imported here (it needs GTK and has no .py suffix), so these
tests read its source: the constants, the translation tables and the call
sites.  That keeps the whole suite runnable in CI with nothing but python3.
"""
import ast
import os
import re
import unittest

from tests.helpers import (GUI_SRC, SMALLEST_SCREEN, gui_constant,
                           gui_source, gui_source_strings, gui_tree,
                           notify_strings)
from tests import helpers

import daemon
import notifications


class DeviceContractTest(unittest.TestCase):
    def test_gui_looks_for_the_same_nodes_as_the_daemon(self):
        """Both halves find the gauge/charger by the same attributes and fall
        back to the same names, so they always talk about the same hardware."""
        self.assertEqual(gui_constant("SUPPLY_ROOT"), daemon.SUPPLY_ROOT)
        self.assertEqual(tuple(gui_constant("GAUGE_ATTRS")),
                         tuple(daemon.GAUGE_ATTRS))
        self.assertEqual(tuple(gui_constant("CHARGER_ATTRS")),
                         tuple(daemon.CHARGER_ATTRS))
        self.assertEqual(gui_constant("GAUGE_FALLBACK"), daemon.GAUGE_FALLBACK)
        self.assertEqual(gui_constant("CHARGER_FALLBACK"),
                         daemon.CHARGER_FALLBACK)
        self.assertIn("find_supply", gui_source())

    def test_gui_and_daemon_agree_on_the_ipc_files(self):
        """The GUI writes the request file the daemon consumes, and reads the
        state file the daemon publishes."""
        want = helpers.daemon_default_args()
        # the daemon's defaults are absolute paths for the device's user; the
        # GUI writes the same file through ~ (it runs as that user)
        self.assertEqual(want["request"],
                         "/home/user/.config/chargecap/request.json")
        self.assertEqual(want["config"], "/var/lib/chargecap/config.json")
        self.assertEqual(want["state"], "/run/chargecap/state.json")
        src = gui_source()
        self.assertIn("~/.config/chargecap/request.json", src)
        self.assertIn('"/run/chargecap/state.json"', src)

    def test_sysfs_files_the_gui_reads_exist_in_the_stub_tree(self):
        """The names are the device's own: a typo would silently show a dash."""
        src = gui_source()
        for name in ("capacity", "voltage_now", "current_now", "temp",
                     "constant_charge_current_max", "charge_full",
                     "online", "status", "usb_type", "current_max"):
            self.assertTrue(name in src, f"{name} is not read anywhere")


class VersionTest(unittest.TestCase):
    """Which chargecap this is: the number, and the build 关于 names."""

    def test_the_two_apps_agree_on_the_version(self):
        import version
        gradle = helpers.source("android/app/build.gradle.kts")
        app_version = re.search(r'val appVersion = "([^"]+)"', gradle).group(1)
        self.assertEqual(version.VERSION, app_version)

    def test_about_names_the_commit_and_the_day(self):
        """1.0.0 (a1b2c3d4-20261021): the number, eight characters, the build
        day -- and only the number when neither git nor an install can say."""
        import tempfile
        import version
        had_info, had_git = version.BUILD_INFO, version._git
        try:
            with tempfile.NamedTemporaryFile("w", delete=False) as f:
                f.write("a1b2c3d4 20261021\n")
            version.BUILD_INFO = f.name
            version._git = lambda: None
            self.assertEqual(version.build_label(),
                             version.VERSION + " (a1b2c3d4-20261021)")
            os.unlink(f.name)
            version.BUILD_INFO = "/nonexistent/build-info"
            self.assertEqual(version.build_label(), version.VERSION)
        finally:
            version.BUILD_INFO, version._git = had_info, had_git

    def test_install_writes_the_build_info_beside_the_panel(self):
        installer = helpers.source("install.sh")
        self.assertIn("version.py /usr/local/lib/chargecap/version.py", installer)
        self.assertIn("git rev-parse --short=8 HEAD", installer)
        self.assertIn("/usr/local/lib/chargecap/build-info", installer)


class TranslationTest(unittest.TestCase):
    def setUp(self):
        self.en = gui_constant("EN")
        self.scale = gui_constant("SCALE")

    def test_every_translated_string_has_a_translation(self):
        # the panel's own _() calls, and the words the notification table asks
        # for when it is read (it is written in Chinese, translated on use)
        used = gui_source_strings() | notify_strings()
        missing = sorted(s for s in used if s not in self.en)
        self.assertEqual(missing, [], f"untranslated: {missing}")

    def test_no_stale_translations(self):
        """An entry nobody asks for is dead weight (or a renamed string)."""
        used = gui_source_strings() | notify_strings()
        unused = sorted(k for k in self.en if k not in used)
        self.assertEqual(unused, [], f"unused entries: {unused}")

    def test_every_language_declares_a_complete_type_scale(self):
        languages = {"zh", "en"}
        self.assertEqual(set(self.scale), languages)
        keys = {"title", "key", "small", "value", "sub", "spin", "btn",
                "btnpad", "big", "heading"}
        for lang, entry in self.scale.items():
            self.assertEqual(set(entry), keys, f"{lang} scale is incomplete")
            for k, v in entry.items():
                self.assertIsInstance(v, int, f"{lang}.{k}")
        # the wide language steps down, which is the whole point of the scale
        self.assertLess(self.scale["en"]["value"], self.scale["zh"]["value"])
        self.assertLess(self.scale["en"]["btn"], self.scale["zh"]["btn"])

    def test_scale_is_actually_applied(self):
        src = gui_source()
        self.assertIn("load_from_string(CSS + metric_css() + scale_css())", src)
        for rule in ("row.key-chip label.title", "row.key-chip label",
                     ".key-label", ".small-label", "row.unit-row label.subtitle",
                     "spinbutton.limit-spin text", "row.metric-row label",
                     "row.switch-row.compact-status label.title",
                     "row.power-row.compact-status label"):
            self.assertIn(rule, src, f"scale_css is missing {rule}")

    def test_language_follows_the_system_unless_overridden(self):
        src = gui_source()
        self.assertIn("GLib.get_language_names()", src)
        self.assertIn('want if want in ("zh", "en") else None', src)


class MetricTest(unittest.TestCase):
    def setUp(self):
        self.metrics = gui_constant("METRICS")
        self.keys = [m[0] for m in self.metrics]

    def test_metrics_are_the_five_expected_ones(self):
        self.assertEqual(self.keys, ["voltage_v", "current_mA", "power_w",
                                     "temp_c", "capacity"])

    def test_button_and_axis_abbreviations_cover_every_metric(self):
        """Adding a metric without its abbreviations would KeyError at draw
        time on an English phone."""
        for name in ("METRIC_BTN_EN", "METRIC_AXIS_EN", "METRIC_BRIGHT"):
            table = gui_constant(name)
            self.assertEqual(sorted(table), sorted(self.keys), name)

    def test_english_abbreviations_are_short(self):
        for name in ("METRIC_BTN_EN", "METRIC_AXIS_EN"):
            for key, text in gui_constant(name).items():
                self.assertLessEqual(len(text), 4, f"{name}[{key}] = {text}")

    def test_metric_colours_are_the_documented_ones(self):
        by_key = {m[0]: m for m in self.metrics}
        self.assertEqual(by_key["voltage_v"][3], "#3584e4")
        self.assertEqual(by_key["current_mA"][3], "#e01b24")
        self.assertEqual(by_key["power_w"][3], "#9141ac")
        self.assertEqual(by_key["temp_c"][3], "#e5a50a")
        self.assertEqual(by_key["capacity"][3], "#2ec27e")

    def test_capacity_has_a_fixed_zero_to_hundred_axis(self):
        by_key = {m[0]: m for m in self.metrics}
        self.assertEqual(by_key["capacity"][6], (0.0, 100.0))


class LayoutTest(unittest.TestCase):
    """The cells' size requests are the window's *minimum* width.  If they ever
    ask for more than the screen, the shell cannot shrink the panel after a
    rotation: it stays landscape-wide and the right-hand values fall off the
    screen.  That was a real bug -- this is the guard."""

    def test_status_rows_always_fit_the_smallest_screen(self):
        inner = max(120, SMALLEST_SCREEN - gui_constant("PAGE_MARGIN"))
        gap = gui_constant("TITLE_GAP")
        cap = gui_constant("MAX_SUFFIX")
        for title_w in range(0, 200, 2):
            suffix = min(max(80, inner - (title_w + gap)), cap)
            row_min = title_w + 30 + suffix       # Adw leaves 30px for cells
            self.assertLessEqual(row_min, SMALLEST_SCREEN,
                                 f"a {title_w}px title needs {row_min}px")

    def test_title_reserve_covers_the_chip_padding(self):
        """The chip behind a title is wider than the measured text; leaving
        that out squeezed English titles into "Voltag…"."""
        src = gui_source()
        self.assertIn("TITLE_CHIP_PAD", src)
        self.assertIn("+ TITLE_CHIP_PAD", src)

    def test_current_row_separator_and_signs(self):
        """大电流 (4 digit) values have to keep fitting: the range is written
        without "+" and separated by a bar."""
        src = gui_source()
        self.assertIn('f"{self.i_min:.0f} | {self.i_max:.0f}"', src)
        self.assertNotIn(':+.0f} | ', src)

    def test_compact_row_height_is_kept(self):
        src = gui_source()
        self.assertIn("min-height: 28px", src)

    def test_help_icon_stays_small(self):
        """The ⓘ next to the USB type is a hint, not a button-sized target."""
        m = re.search(r"help_icon\.set_pixel_size\((\d+)\)", gui_source())
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 10)

    def test_save_ui_does_not_clobber_other_settings(self):
        """The chart settings are written back read-modify-write: the language
        choice lives in the same file."""
        src = gui_source()
        self.assertIn("d = load_ui()", src)
        self.assertIn("d.update({", src)


if __name__ == "__main__":
    unittest.main()


class SizeTest(unittest.TestCase):
    """The sizes that were tuned on the phone.

    They are pinned on purpose: these numbers are what makes the panel fit a
    360px screen and read well on it, so changing one has to be a deliberate
    edit here as well (update the value *and* this test together).
    """

    def setUp(self):
        self.src = gui_source()

    def rule(self, pattern):
        m = re.search(pattern, self.src, re.S)
        self.assertIsNotNone(m, f"not found: {pattern}")
        return m

    def test_rows_stay_compact(self):
        """28px rows instead of Adw's default is what makes the page fit."""
        self.rule(r"row\.compact-status > box \{[^}]*min-height: 28px[^}]*\}")

    def test_group_spacing_is_tight_and_the_first_group_is_lifted(self):
        self.rule(r"preferencesgroup \{ margin-top: 0px; margin-bottom: 12px; \}")
        self.rule(r"preferencesgroup:not\(:first-child\) "
                  r"\{ margin-top: -24px; \}")
        self.rule(r"preferencesgroup:first-child \{ margin-top: -14px; \}")

    def test_chart_height(self):
        m = self.rule(r"self\.set_size_request\(-1, (\d+)\)")
        self.assertEqual(int(m.group(1)), 139)

    def test_the_chart_row_carries_no_extra_padding(self):
        self.assertIn('row_chart.add_css_class("compact-status")', self.src)

    def test_unselected_metric_buttons_are_deliberately_faint(self):
        m = self.rule(r"button\.metric-btn \{ color: "
                      r"alpha\(@window_fg_color, ([\d.]+)\); \}")
        self.assertEqual(float(m.group(1)), 0.30)
        # ... and a selected one still takes its own colour
        self.assertIn(".k-{key}:checked", self.src)

    def test_the_metric_row_is_sized_by_the_language_scale(self):
        self.assertIn('row_ctl.add_css_class("metric-row")', self.src)
        self.assertIn("row.metric-row label", self.src)

    def test_window_size_and_the_screen_it_must_fit(self):
        self.assertIn("self.set_default_size(360, 720)", self.src)
        self.assertEqual(SMALLEST_SCREEN, 360)

    def test_the_band_keeps_a_two_percent_hysteresis(self):
        self.assertEqual(gui_constant("MIN_GAP"), 2)

    def test_chart_draws_curves_thicker_than_its_grid(self):
        m = self.rule(r"LINE_W = ([\d.]+)\s+# curve thickness")
        line = float(m.group(1))
        m = self.rule(r"GRID_W = ([\d.]+)")
        grid = float(m.group(1))
        self.assertEqual((line, grid), (0.6, 0.5))
        self.assertGreater(line, grid)

    def test_the_capacity_row_follows_the_power_row(self):
        """电源's three values and the gauge's mAh are the same kind of answer,
        so they sit together -- ahead of the per-reading rows."""
        power = self.src.index("self._power_row()")
        capacity = self.src.index("self._capacity_row()")
        usb = self.src.index('info_row(((_("USB类型")')
        self.assertLess(power, capacity)
        self.assertLess(capacity, usb)

    def test_off_empties_the_chart_and_stops_its_repaint(self):
        """采集 off is not a frozen picture: the curve is thrown away, the
        chart says so, and refresh() stops repainting it (the live table above
        still updates -- that is a look, the chart is a record)."""
        self.assertIn("def clear(self):", self.src)
        self.assertIn("del self._ts[:]", self.src)
        self.assertIn("if not self.recording:", self.src)
        self.assertIn('self.message or _("图形化已关闭")', self.src)
        self.assertIn('self.chart.message = None if self.live else _("实时采集已关闭")',
                      self.src)
        self.assertIn("self.chart.recording = self.record", self.src)
        self.assertIn("self.chart.clear()", self.src)
        self.assertIn("if paint and self.record:", self.src)

    def test_the_chart_records_only_while_asked(self):
        """采集 is the chart's master switch: off on a fresh page, and while
        it is off nothing is kept.  The live table above reads only once
        实时采集 is asked for too -- neither switch starts on its own."""
        self.assertIn('self.live = bool(load_ui().get("live", False))',
                      self.src)
        self.assertIn('self.record = bool(load_ui().get("record", False))',
                      self.src)
        self.assertIn('if self.record and self._sample_due(now):', self.src)
        # 图形化 lives on 实时采集's row now, as a switch of its own
        self.assertIn('record_label = Gtk.Label(label=_("图形化"))', self.src)
        self.assertIn("self.sw_record = Gtk.Switch()", self.src)
        # the pair starts at the row's left edge, not pushed to the right
        self.assertIn("pair.set_margin_start(12)", self.src)
        self.assertIn("self.row_live.set_child(pair)", self.src)
        # ... and stands as tall as 上限 / 下限
        self.assertIn("row.live-row.compact-status, "
                      "row.live-row.compact-status > box { min-height: 40px; }",
                      self.src)
        self.assertNotIn('subtitle=_("开启后记录曲线")', self.src)
        self.assertIn('d["record"] = self.record', self.src)
        # the live read is untouched by the switch
        self.assertIn('if paint:', self.src)

    def test_chart_keeps_five_divisions(self):
        self.assertEqual(int(self.rule(
            r"GRID_DIVS = (\d+)\s+# divisions of the time axis").group(1)), 5)
        m = self.rule(r"TICKS = \(([^)]*)\)")
        self.assertEqual(len([t for t in m.group(1).split(",") if t.strip()]), 5)

    def test_window_choices_are_the_documented_range(self):
        windows = gui_constant("WINDOWS")
        self.assertEqual(windows[0], ("15s", 15))
        self.assertEqual(windows[-1], ("48h", 172800))
        self.assertEqual(len(windows), 16)


class HeaderTest(unittest.TestCase):
    """The header's two switches: the background, then the language.

    Dark is the default on both apps (the Android port opens dark too), and the
    background has to sit left of the language switch -- `pack_end` puts each
    button left of the one packed before it, which is easy to get backwards.
    """

    def setUp(self):
        self.src = gui_source()

    def test_the_background_is_dark_by_default(self):
        self.assertEqual(gui_constant("SCHEMES"), ("dark", "light", "auto"))
        self.assertIn('return want if want in SCHEMES else "dark"', self.src)
        self.assertIn("Adw.ColorScheme.FORCE_DARK", self.src)
        self.assertIn("Adw.StyleManager.get_default().set_color_scheme", self.src)
        # ... and it is applied before the window is built, so nothing flashes
        self.assertIn("apply_scheme(SCHEME_CHOICE)", self.src)

    def test_the_header_reads_background_language_gear(self):
        """pack_end packs right to left: the gear is packed first so it sits
        last, after the language, as in the Android header."""
        pack = re.findall(r"header\.pack_end\(self\.(\w+)\(\)\)", self.src)
        self.assertEqual(pack, ["_settings_button", "_language_button",
                                "_background_button"],
                         "pack_end packs right to left")

    def test_the_background_applies_without_a_restart(self):
        """Only the strings need a new process; the scheme is live."""
        body = self.src[self.src.index("def _on_background("):]
        body = body[:body.index("\n    def ")]
        self.assertIn("apply_scheme(want)", body)
        self.assertNotIn("_relaunch", body)

    def test_the_background_choice_is_written_down(self):
        body = self.src[self.src.index("def _on_background("):]
        body = body[:body.index("\n    def ")]
        self.assertIn('d["scheme"] = want', body)
        self.assertIn("save_ui(d)", body)

    def test_the_button_shows_the_scheme_in_both_languages(self):
        labels = gui_constant("SCHEME_LABEL")
        self.assertEqual(set(labels), {"zh", "en"})
        for lang in ("zh", "en"):
            self.assertEqual(sorted(labels[lang]), ["auto", "dark", "light"])
        # short enough for a header bar, like the language switch's 中 / EN
        for entry in labels["zh"].values():
            self.assertEqual(len(entry), 1)


class SamplingTest(unittest.TestCase):
    """The chart's recording interval, and the clock it runs on.

    The panel reads at 500 ms because it is a live number; the history is
    written at whatever interval is set.  One timeout, re-armed each pass, so a
    slower interval cannot slow the panel down with it.
    """

    def setUp(self):
        self.src = gui_source()

    def test_the_intervals_are_the_documented_list(self):
        samples = gui_constant("SAMPLES")
        self.assertEqual(samples[0], ("0.01s", 10))
        self.assertEqual(samples[-1], ("20s", 20000))
        self.assertEqual(len(samples), 13)
        self.assertEqual(gui_constant("SAMPLE_MS"), 500)
        # 0.5 s is both the panel's readout and what a fresh install records
        self.assertIn(("0.5s", 500), samples)

    def test_a_new_interval_stores_at_once(self):
        """Changing the interval must not leave the curve frozen for the rest
        of the old one: the next refresh stores a point."""
        sample = self.src[self.src.index("def _on_sample("):]
        sample = sample[:sample.index("\n    def ")]
        self.assertIn("self._stored_at = 0", sample)
        record = self.src[self.src.index("def _on_record("):]
        record = record[:record.index("\n    def ")]
        self.assertIn("if self.record:", record)
        self.assertIn("self._stored_at = 0", record)
        # the two header words are smaller and closer than the tabs
        self.assertIn("button.lang-btn label { font-size: 9px; }", self.src)
        self.assertIn("button.lang-btn { min-width: 0px; min-height: 0px; "
                      "padding: 1px 3px; }", self.src)

    def test_the_interval_is_remembered(self):
        self.assertIn('d["sample_ms"] = want', self.src)
        self.assertIn('.get("sample_ms")', self.src)
        self.assertIn("SAMPLE_MS_CHOICE", self.src)

    def test_the_tick_is_the_charts_interval_while_it_records(self):
        """The chart may want samples faster than 500 ms; with it off, 0.01 s
        must not make a 100 Hz reader and 20 s must not freeze the numbers."""
        self.assertIn("def _tick_ms(self):", self.src)
        self.assertIn("if self.live and self.record:", self.src)
        self.assertIn("return max(10, min(SAMPLE_MS, SAMPLE_MS_CHOICE))", self.src)
        self.assertIn("return SAMPLE_MS", self.src)
        self.assertIn("GLib.timeout_add(self._tick_ms(), self.refresh)", self.src)
        # ... and every way out re-arms it: 实时采集 off returns early, so the
        # chain is armed there too (still one chain -- each pass arms the next)
        self.assertEqual(self.src.count("GLib.timeout_add(self._tick_ms()"), 2)

    def test_a_sample_is_stored_only_when_it_is_due(self):
        self.assertIn("def _sample_due(self, now):", self.src)
        # ... and only while 采集 is on
        self.assertIn("if self.record and self._sample_due(now):", self.src)
        self.assertIn("or now - self._stored_at >= SAMPLE_MS_CHOICE / 1000.0", self.src)

    def test_the_panel_repaints_at_its_own_pace(self):
        self.assertIn("paint = now - self._painted_at >= SAMPLE_MS / 1000.0", self.src)
        # ... and 采集 off means no repaint at all: an empty chart is not a
        # reason to wake the screen up five times a second
        self.assertIn("if paint and self.record:", self.src)
        self.assertIn("self.chart.queue_draw()", self.src)


class ChoiceListTest(unittest.TestCase):
    """The list behind every chip: the tick follows the value that was picked.

    A popover is built once and reopened after each choice, so a tick written
    only while it was built went stale: 采样间隔's chip moved to the new
    interval while its list still ticked the old one.  The shared builder has
    to move the tick itself, or every caller would need a copy of the same
    fix.
    """

    def setUp(self):
        self.src = gui_source()
        self.pop = self._body("choice_popover")

    def _body(self, name):
        """One function's source, nested defs included."""
        for node in ast.walk(gui_tree()):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return ast.get_source_segment(self.src, node)
        raise AssertionError(f"{name} is not in the GUI")

    def test_the_tick_moves_with_the_pick(self):
        # the row labels are kept, so an already built list can be rewritten
        self.assertIn("rows.append((value, text, label))", self.pop)
        self.assertIn("def tick(chosen):", self.pop)
        self.assertIn(r'"\u2713 " if value == chosen else "   "', self.pop)
        # a tap goes through the shared handler, which ticks and then tells
        # the caller -- not straight to the caller as it used to
        self.assertIn('btn.connect("clicked", picked, value)', self.pop)
        self.assertIn("tick(value)", self.pop)
        self.assertIn("on_pick(btn, value)", self.pop)
        # and the first open ticks the value the list was built with
        self.assertIn("tick(current)", self.pop)

    def test_every_choice_chip_still_uses_the_shared_list(self):
        """The fix lives in the builder: a caller with its own popover would
        silently lose it."""
        for name in ("chip_button", "_sample_button", "_window_button",
                     "_background_button", "_language_button"):
            with self.subTest(name=name):
                self.assertIn("choice_popover(", self._body(name))


class NotifyTableTest(unittest.TestCase):
    """The 通知 table, as the panel and the notifier both read it.

    Everything here is plain Python -- notifications.py has no gi -- so the
    tests hold the rules themselves rather than a copy of them.
    """

    def setUp(self):
        notifications.set_translator(lambda text: text)
        self.n = notifications.NOTIFY_BY_KEY

    def tearDown(self):
        notifications.set_translator(lambda text: text)

    def test_the_thirteen_are_the_android_thirteen_in_the_same_order(self):
        self.assertEqual([n.key for n in notifications.NOTIFICATIONS],
                         ["done", "low", "plugged", "unplugged", "charging",
                          "idle", "hot", "cold", "vhigh", "vlow", "iin",
                          "drain", "power"])

    def test_defaults_and_ranges_are_the_documented_ones(self):
        want = {
            "done": (100, 1, 0, 100),
            "low": (10, 1, 0, 100),
            "plugged": (0, 1, 0, 0),
            "unplugged": (0, 1, 0, 0),
            "charging": (0, 1, 0, 0),
            "idle": (0, 1, 0, 0),
            "hot": (45, 1, -60, 100),
            "cold": (-20, 1, -60, 100),
            "vhigh": (4300, 100, 3000, 5000),
            "vlow": (3400, 100, 2500, 4500),
            "iin": (3000, 100, 0, 10000),
            "drain": (1000, 100, 0, 5000),
            "power": (20, 1, 0, 100),
        }
        self.assertEqual(sorted(want), sorted(self.n))
        # every switch waits to be asked: the master switch decides whether
        # anything fires at all, and a fresh install arms nothing
        for key, (default, step, low, high) in want.items():
            with self.subTest(key):
                n = self.n[key]
                self.assertEqual((n.default, n.step, n.low, n.high, n.on),
                                 (default, step, low, high, False))

    def test_a_row_wears_a_short_word_and_the_sentence_keeps_the_name(self):
        """电源连接 reads 连接 under the 电源 heading, 温度过高 reads 过高 -- but
        the banner and the voice still say the full sentence, because that is
        what leaves the app."""
        self.assertEqual(self.n["plugged"].short(), "连接")
        self.assertEqual(self.n["unplugged"].short(), "断开")
        self.assertEqual(self.n["hot"].short(), "过高")
        self.assertEqual(self.n["cold"].short(), "过低")
        self.assertEqual(self.n["iin"].short(), "充电过高")
        self.assertEqual(self.n["drain"].short(), "放电过高")
        self.assertEqual(self.n["power"].short(), "过高")
        # the base pair has no shorter word, and a sentence never uses one
        self.assertEqual(self.n["done"].short(), "充电完成")
        self.assertEqual(self.n["hot"].says(45), "温度过高 45 °C")
        self.assertEqual(self.n["plugged"].says(0), "电源连接")

    def test_a_line_reads_as_the_sentence_it_says(self):
        self.assertEqual(self.n["done"].says(100), "充电完成 100%")
        self.assertEqual(self.n["low"].says(10), "电量过低 10%")
        self.assertEqual(self.n["hot"].value(45), "45 °C")
        self.assertEqual(self.n["cold"].value(-20), "-20 °C")
        self.assertEqual(self.n["vhigh"].value(4300), "4300 mV")
        self.assertEqual(self.n["iin"].value(3000), "3000 mA")
        self.assertEqual(self.n["power"].value(20), "20 W")
        # a state has no number, and its sentence is the name alone
        self.assertEqual(self.n["plugged"].says(0), "电源连接")
        self.assertEqual(self.n["unplugged"].says(0), "电源断开")
        self.assertEqual(self.n["charging"].says(0), "充电中")
        self.assertEqual(self.n["idle"].says(0), "未充电")

    def test_a_state_is_on_or_off_not_a_reading(self):
        for key in ("plugged", "unplugged", "charging", "idle"):
            with self.subTest(key):
                self.assertFalse(self.n[key].numbered)
        for key in ("done", "low", "hot", "cold", "vhigh", "vlow", "iin",
                    "drain", "power"):
            with self.subTest(key):
                self.assertTrue(self.n[key].numbered)

    def test_only_the_two_with_something_to_wait_for_have_an_endless_count(self):
        counts = self.n["done"].counts()
        self.assertEqual([c for c, _ in counts], [1, 2, 3, 5, 10, 0])
        self.assertEqual(counts[-1][1], "直到电源断开")
        self.assertEqual(self.n["low"].counts()[-1][1], "直到开始充电")
        for key in ("hot", "cold", "vhigh", "vlow", "iin", "drain", "power",
                    "plugged", "unplugged", "charging", "idle"):
            with self.subTest(key):
                self.assertEqual([c for c, _ in self.n[key].counts()],
                                 [1, 2, 3, 5, 10])

    def test_the_groups_are_the_page_s_order(self):
        """One group per kind of reading: the battery's own charge, the plug
        and the charging state, then temperature, voltage, current and power
        each to itself.  Every notification is in exactly one group, and the
        keys run in the table's order."""
        groups = notifications.GROUPS
        self.assertEqual([g.title() for g in groups],
                         ["基础功能", "电源", "充电", "温度", "电压", "电流",
                          "功率"])
        seen = [k for g in groups for k in g.keys]
        self.assertEqual(seen, [n.key for n in notifications.NOTIFICATIONS])

    def test_the_gaps_are_the_ones_the_page_offers(self):
        """1s to 5min, the same eleven in both languages: the labels are
        units, not words, so they need no translation."""
        self.assertEqual([g for g, _l in notifications.GAPS],
                         [1, 2, 3, 5, 10, 15, 20, 30, 60, 120, 300])
        self.assertEqual([l for _g, l in notifications.GAPS],
                         ["1s", "2s", "3s", "5s", "10s", "15s", "20s", "30s",
                          "1min", "2min", "5min"])
        self.assertEqual(notifications.DEFAULT_GAP, 2)
        self.assertEqual(notifications.gap_label(60), "1min")
        self.assertEqual(notifications.gap_label(7), "1s")

    def test_the_plain_counts_are_the_same_in_both_apps(self):
        self.assertEqual([c for c, _ in notifications.TIMES], [1, 2, 3, 5, 10])

    def test_two_ways_of_arriving(self):
        """One or the other, never both: a count belongs to either."""
        self.assertEqual([k for k, _ in notifications.KINDS],
                         ["banner", "voice"])
        self.assertEqual([t for _, t in notifications.KINDS], ["横幅", "语音"])

    def test_complete_means_plugged_in_and_full(self):
        past = notifications._past_done
        self.assertEqual(past({"capacity": 100, "plugged": True}, 100), 0)
        self.assertEqual(past({"capacity": 99, "plugged": True}, 100), -1)
        # unplugged is never "complete", and unplugging is what lets it fire
        # again on the next charge
        self.assertIsNone(past({"capacity": 100, "plugged": False}, 100))
        self.assertIsNone(past({"capacity": None, "plugged": True}, 100))

    def test_low_is_the_other_way_round(self):
        past = notifications._past_low
        self.assertEqual(past({"capacity": 5}, 10), 5)
        self.assertEqual(past({"capacity": 15}, 10), -5)
        self.assertIsNone(past({"capacity": None}, 10))

    def test_temperature_is_read_the_way_each_line_wants_it(self):
        self.assertEqual(notifications._past_hot({"temp_c": 46.0}, 45), 1)
        self.assertEqual(notifications._past_hot({"temp_c": 20.0}, 45), -25)
        self.assertEqual(notifications._past_cold({"temp_c": -1.0}, 0), 1)
        self.assertIsNone(notifications._past_hot({"temp_c": None}, 45))

    def test_discharge_is_the_size_of_the_signed_current(self):
        past = notifications._past_drain
        self.assertEqual(past({"current_a": -1.5}, 1000), 500)
        # positive current is charging: no discharge to report
        self.assertEqual(past({"current_a": 1.5}, 1000), -2500)
        self.assertIsNone(past({"current_a": None}, 1000))

    def test_charge_current_is_the_other_half_of_the_same_reading(self):
        past = notifications._past_iin
        self.assertEqual(past({"current_a": 3.0}, 3000), 0)
        self.assertEqual(past({"current_a": -1.0}, 3000), -4000)
        self.assertIsNone(past({"current_a": None}, 3000))

    def test_voltage_is_read_in_millivolts_off_a_gauge_that_says_volts(self):
        self.assertEqual(notifications._past_vhigh({"voltage_v": 4.4}, 4300), 100)
        self.assertEqual(notifications._past_vlow({"voltage_v": 3.3}, 3400), 100)
        self.assertIsNone(notifications._past_vhigh({"voltage_v": None}, 4300))

    def test_power_is_the_size_of_it_whichever_way_it_flows(self):
        past = notifications._past_power
        self.assertEqual(past({"power_w": 21.0}, 20), 1.0)
        self.assertEqual(past({"power_w": -21.0}, 20), 1.0)
        self.assertIsNone(past({"power_w": None}, 20))

    def test_a_state_is_one_or_minus_one(self):
        self.assertEqual(notifications.NOTIFY_BY_KEY["plugged"].distance(
            {"plugged": True}, 0), 1.0)
        self.assertEqual(notifications.NOTIFY_BY_KEY["plugged"].distance(
            {"plugged": False}, 0), -1.0)
        self.assertEqual(notifications.NOTIFY_BY_KEY["idle"].distance(
            {"charging": True}, 0), -1.0)

    def test_the_three_answers_are_read_in_one_place(self):
        """通知方式, 次数 and 间隔 are one answer, read by the panel and by the
        notifier through the same function -- so the two can never disagree,
        and a value the table no longer offers is the fresh answer rather than
        a guess."""
        n = self.n["hot"]
        had = notifications.VOICE_CMD
        notifications.VOICE_CMD = "/usr/bin/espeak-ng"   # a phone that speaks
        try:
            self.assertEqual(notifications.answers({}, n),
                             {"kind": "voice", "times": 1, "gap": 2})
            self.assertEqual(notifications.answers(
                {"notify_hot_kind": "banner", "notify_hot_times": 5,
                 "notify_hot_gap": 15}, n),
                {"kind": "banner", "times": 5, "gap": 15})
            # a kind the page dropped, a count this notification does not carry,
            # an interval outside GAPS
            self.assertEqual(notifications.answers(
                {"notify_hot_kind": "both", "notify_hot_times": 7,
                 "notify_hot_gap": 4}, n),
                {"kind": "voice", "times": 1, "gap": 2})
        finally:
            notifications.VOICE_CMD = had
        # ... while 0 is a real count where the notification has an end
        self.assertEqual(notifications.answers(
            {"notify_done_times": 0}, self.n["done"])["times"], 0)
        # and a hand-edited number is not a crash
        self.assertEqual(notifications.answers(
            {"notify_hot_times": "five"}, n)["times"], 1)

    def test_a_line_says_it_once_and_rearms_past_its_step(self):
        rules = notifications.NotifyRules()
        hot = self.n["hot"]

        def fire(temp):
            return rules.sample({"temp_c": temp}, [(hot, 45)])

        self.assertEqual(fire(46), [hot])
        self.assertEqual(fire(47), [])          # still above: quiet
        self.assertEqual(fire(44.9), [])        # inside the step: still quiet
        self.assertEqual(fire(44), [])          # clear, and re-armed
        self.assertEqual(fire(46), [hot])

    def test_arming_says_nothing_about_what_is_already_true(self):
        """Turning 通知开关 on -- or opening the app with it already on -- is
        not a crossing: the readings as they stand are taken as read."""
        rules = notifications.NotifyRules()
        hot = self.n["hot"]
        rules.seed({"temp_c": 50}, [(hot, 45)])
        self.assertEqual(rules.sample({"temp_c": 50}, [(hot, 45)]), [])
        self.assertEqual(rules.sample({"temp_c": 60}, [(hot, 45)]), [])
        self.assertEqual(rules.sample({"temp_c": 44}, [(hot, 45)]), [])
        self.assertEqual(rules.sample({"temp_c": 46}, [(hot, 45)]), [hot])

    def test_a_reading_the_phone_does_not_publish_is_not_a_crossing(self):
        rules = notifications.NotifyRules()
        drain = self.n["drain"]
        self.assertEqual(rules.sample({"current_a": None}, [(drain, 1000)]), [])
        self.assertEqual(rules.sample({}, [(drain, 1000)]), [])

    def test_the_two_percent_lines_never_cross(self):
        keep = notifications.keep_apart
        at = {"done": 100, "low": 10}
        # 电量过低 stops one below 充电完成 ...
        self.assertEqual(keep(self.n["low"], 60, at), 60)
        self.assertEqual(keep(self.n["low"], 100, at), 99)
        # ... and 充电完成 starts one above 电量过低
        self.assertEqual(keep(self.n["done"], 5, at), 11)
        self.assertEqual(keep(self.n["done"], 100, at), 100)
        # every number still stops at its own range
        self.assertEqual(keep(self.n["cold"], -100, at), -60)
        self.assertEqual(keep(self.n["drain"], 99999, at), 5000)

    def test_a_voice_without_an_engine_becomes_a_banner(self):
        """A stored 语音 on a phone with no engine must not go silent: the page
        offers 横幅 alone, and the answer follows the page."""
        had = notifications.VOICE_CMD
        try:
            notifications.VOICE_CMD = None
            self.assertEqual(notifications.answers(
                {"notify_hot_kind": "voice"}, self.n["hot"])["kind"], "banner")
        finally:
            notifications.VOICE_CMD = had

    def test_a_voice_is_only_offered_where_the_phone_can_speak(self):
        had = notifications.VOICE_CMD
        try:
            notifications.VOICE_CMD = None
            self.assertEqual([k for k, _ in notifications.spoken_kinds()],
                             ["banner"])
            notifications.VOICE_CMD = "/usr/bin/spd-say"
            self.assertEqual([k for k, _ in notifications.spoken_kinds()],
                             ["banner", "voice"])
        finally:
            notifications.VOICE_CMD = had

    def test_the_voice_falls_back_past_spd_say(self):
        """spd-say is the session's voice; espeak(-ng) is the engine without
        the daemon, so a phone with either still gets 语音."""
        self.assertEqual(notifications.VOICE_ENGINES,
                         ("espeak-ng", "espeak", "spd-say"))
        had = notifications.VOICE_CMD
        try:
            notifications.VOICE_CMD = "/usr/bin/espeak-ng"
            self.assertEqual(
                notifications.voice_command("充电完成", "zh"),
                ["/usr/bin/espeak-ng", "-v", "cmn+f3",
                 "-s", "200", "-p", "99", "-a", "130", "-g", "0",
                 "充电完成"])
            self.assertEqual(
                notifications.voice_command("Charging complete", "en"),
                ["/usr/bin/espeak-ng", "Charging complete"])
            notifications.VOICE_CMD = "/usr/bin/spd-say"
            self.assertEqual(
                notifications.voice_command("充电完成", "zh"),
                ["/usr/bin/spd-say", "-N", "chargecap", "-n", "main",
                 "-y", "Chinese (Mandarin, latin as English)+f3",
                 "-r", "20", "-p", "40", "-w", "充电完成"])
            notifications.VOICE_CMD = None
            self.assertIsNone(notifications.voice_command("充电完成", "zh"))
        finally:
            notifications.VOICE_CMD = had

    def test_the_words_are_translated_where_they_are_used(self):
        notifications.set_translator(lambda text: {"充电完成": "Charging complete"}.get(text, text))
        self.assertEqual(self.n["done"].title(), "Charging complete")
        self.assertEqual(self.n["done"].says(100), "Charging complete 100%")
        self.assertEqual(self.n["low"].title(), "电量过低")


class NotifierTest(unittest.TestCase):
    """The half that stays up with the panel closed."""

    def setUp(self):
        self.src = helpers.source("notifier.py")

    def test_it_reads_the_panel_and_the_daemon(self):
        self.assertIn('UI_FILE = os.path.expanduser("~/.config/chargecap/ui.json")',
                      self.src)
        self.assertIn('STATE_FILE = "/run/chargecap/state.json"', self.src)
        # the master switch gates it, the per-line ones are the table's own
        self.assertIn('if not ui.get("notify", False):', self.src)
        self.assertIn('if ui.get(f"notify_{n.key}", n.on)]', self.src)

    def test_it_says_nothing_from_a_stale_state(self):
        """A daemon that stopped must not leave old readings talking."""
        self.assertIn("STALE_S", self.src)
        self.assertIn('float(s.get("updated") or 0)', self.src)

    def test_the_reading_is_the_daemons_own_snapshot(self):
        for key in ("capacity", "current_a", "temp_c", "plugged",
                    '"charging": s.get("status") == "Charging"'):
            with self.subTest(key):
                self.assertIn(key, self.src)

    def test_a_banner_carries_the_apps_name_and_one_id_per_line(self):
        self.assertIn('APP_ID = "org.postmarketos.Chargecap"', self.src)
        self.assertIn('self.send_notification("chargecap-" + n.key, note)',
                      self.src)
        self.assertIn("Gio.NotificationPriority.HIGH", self.src)

    def test_the_switches_still_stop_what_is_said(self):
        self.assertIn("def silence(self):", self.src)
        self.assertIn("self.voice.stop()", self.src)
        # terminate, then reap: a terminated TTS child that is never waited on
        # becomes a zombie for as long as the notifier lives
        self.assertIn("proc.wait(timeout=1)", self.src)
        self.assertIn("proc.kill()", self.src)
        # the WAV pipeline is a shell plus espeak-ng plus aplay: stop the group
        self.assertIn("start_new_session=True", self.src)
        self.assertIn("os.killpg(group, signal.SIGTERM)", self.src)
        self.assertIn(
            '"spd-say", "-N", "chargecap", "-n", "main", "-S"', self.src)
        # a reminder re-reads the answers at every repeat, so a switch thrown
        # mid-count is honoured without a watcher beside it
        self.assertIn("self.reminders.stop_all()", self.src)
        self.assertIn('not ui.get(f"notify_{key}", False)', self.src)

    def test_a_reminder_repeats_at_its_own_gap(self):
        """The count belongs to the whole notification -- a banner is posted
        again as a voice is said again -- 间隔 apart, and 0 of them repeats
        until the reading it waits for says the job is done.  A repeat that
        wakes to a reading back inside its line says nothing more."""
        self.assertIn("class Reminders", self.src)
        self.assertIn("self.reminders.start(n.key)", self.src)
        for piece in ('answer = rules.answers(ui, n)',
                      'times = answer["times"]',
                      'gap = answer["gap"]',
                      "max(1, gap) * 1000",
                      "if (times == 0 and n.until is None) "
                      "or (times != 0 and said >= times):",
                      "past is None or past < 0",
                      "n.until_done(snap)"):
            with self.subTest(piece=piece):
                self.assertIn(piece, self.src)

    def test_one_way_of_arriving_at_a_time(self):
        self.assertIn('answer["kind"] == "banner"', self.src)
        self.assertIn("self.notifier.post(n, sentence)", self.src)
        self.assertIn("self.notifier.voice.say(sentence,", self.src)
        self.assertNotIn('"both"', self.src)

    def test_the_notifier_speaks_in_the_panels_language(self):
        """The command is the table's, with the language it should speak --
        espeak needs to be told Mandarin, spd-say does not."""
        self.assertIn("def language(self):", self.src)
        self.assertIn(
            "self.notifier.voice.say(sentence, self.notifier.language())",
            self.src)
        self.assertIn("rules.voice_command(text, lang)", self.src)

    def test_a_switch_turned_on_says_nothing_at_once(self):
        """The same rule on this half: arming is a look, not a word."""
        self.assertIn("self.rules.seed(snap, lines)", self.src)
        self.assertIn("def seed(self, snap, rules):",
                      helpers.source("notifications.py"))
        # the pass that seeds does not go on to fire: that is the point
        tick = re.search(r"def tick\(self\).*?\n    def ", self.src, re.S).group(0)
        arm = tick[tick.index("enabled = frozenset"):]
        self.assertIn("self.rules.reset()\n"
                      "            self.rules.seed(snap, lines)\n"
                      "            self.enabled = enabled\n"
                      "            return True", arm)
        # ... and a master switch turned on arms afresh rather than trusting
        # the last set
        self.assertIn("self.enabled = None", tick)

    def test_the_sleep_record_rides_on_the_same_pass(self):
        """The notifier is the half that is up when the sleeps happen, so it
        is the one that counts them -- and the count starts when 禁止休眠 is
        turned on, not when the notifications are: the two are separate
        answers."""
        self.assertIn("self.sleeps.tick()", self.src)
        self.assertIn("def read_inhibit(self):", self.src)
        self.assertIn("inhibit = self.read_inhibit()", self.src)
        self.assertIn("self.sleeps.restart()", self.src)
        # the master switch's turn-on does not touch the record
        tick = re.search(r"def tick\(self\).*?\n    def ", self.src, re.S).group(0)
        self.assertIn("if not self.on:", tick)
        master = tick[tick.index("if not self.on:"):]
        self.assertNotIn("self.sleeps.restart()", master)
        # a service starting under an already-on switch has seen no turn-on
        self.assertIn("if self.inhibit is None:", self.src)

    def test_the_service_says_the_same_english_as_the_panel(self):
        """The notifier carries only the words it says, and they are the
        panel's English -- two spellings of one sentence would show."""
        import ast
        en = None
        for node in ast.parse(self.src).body:
            if (isinstance(node, ast.Assign)
                    and getattr(node.targets[0], "id", "") == "EN"):
                en = ast.literal_eval(node.value)
        self.assertIsNotNone(en)
        panel = gui_constant("EN")
        for key, value in en.items():
            with self.subTest(key):
                self.assertIn(key, panel)
                self.assertEqual(panel[key], value)

    def test_it_is_installed_as_a_user_service(self):
        unit = helpers.source("chargecap-notify.service")
        self.assertIn("ExecStart=/usr/local/bin/chargecap-notify", unit)
        self.assertIn("WantedBy=default.target", unit)
        installer = helpers.source("install.sh")
        self.assertIn("notifications.py", installer)
        self.assertIn("chargecap-notify", installer)
        self.assertIn("chargecap-notify.service", installer)
        uninstaller = helpers.source("uninstall.sh")
        self.assertIn("chargecap-notify", uninstaller)


class NotifyWiringTest(unittest.TestCase):
    """The panel's half: the page, the words, and where the answers go."""

    def setUp(self):
        self.src = gui_source()

    def test_the_page_is_still_here_but_the_rules_have_moved(self):
        self.assertIn("def _notify_page(self):", self.src)
        # the rules run in the notifier, so the panel keeps none of them: two
        # owners would say everything twice
        for gone in ("NotifyRules", "def _notify_sample", "def _notify_say",
                     "class Voice"):
            with self.subTest(gone):
                self.assertNotIn(gone, self.src)

    def test_the_panel_stores_and_the_notifier_reads(self):
        self.assertIn("def _save_notify(self):", self.src)
        self.assertIn("set_translator(_)", self.src)

    def test_the_master_switch_dims_the_rows_it_gates(self):
        """通知开关 off is a gate, not a reset: every row under it goes
        insensitive and not one answer changes."""
        self.assertIn("def _apply_notify_gate(self):", self.src)
        self.assertIn('row["row"].set_sensitive(on)', self.src)
        self.assertIn('row["answers"].set_sensitive(on)', self.src)
        self.assertIn("self._apply_notify_gate()", self.src)
        # the master's own handler calls it, and so does the first build
        self.assertIn('self._save_notify()\n        self._apply_notify_gate()',
                      self.src)

    def test_the_threshold_stepper_is_roomy_and_centred(self):
        """The 上限-shaped stepper, not the zero-padded one, and the number in
        the middle of the row rather than pushed against the switch."""
        self.assertIn("centre.set_center_widget(box)", self.src)
        # ... and inside the row's own side padding, not on the card's edge
        self.assertIn("centre.set_margin_start(12)", self.src)
        self.assertIn("centre.set_margin_end(12)", self.src)
        # and the answers line starts on the same x as the name above it
        self.assertIn("box.set_margin_start(12)\n        box.set_margin_end(12)",
                      self.src)
        self.assertIn("centre.set_end_widget(sw)", self.src)
        self.assertIn("spinbutton.notify-spin button { padding: 3px 7px; "
                      "min-width: 24px; min-height: 26px; }", self.src)
        self.assertIn("label.notify-name { font-size: %dpx; font-weight: 700; }",
                      self.src)

    def test_the_notification_page_reads_a_size_up(self):
        """Everything on 通知 is a step up except the group headings: names and
        numbers to the heading size, answers a point under, and 通知开关 above
        them -- while 基础功能 / 电源 keep the size that names every group."""
        for rule in ("label.notify-name { font-size: %dpx; font-weight: 700; }",
                     "row.notify-master label.title { font-size: %dpx; }",
                     "spinbutton.notify-spin text { font-size: %dpx; }",
                     "label.answer-caption { font-size: %dpx; }",
                     "label.answer-value { font-size: %dpx; }"):
            self.assertIn(rule, self.src)
        # the sizes come from the type scale, not from numbers sprinkled in the
        # CSS: a name is a heading, an answer a point under it
        self.assertIn('name = s["heading"]', self.src)
        self.assertIn('answer = s["heading"] - 1', self.src)
        self.assertIn("master = name + 3", self.src)
        self.assertIn('self.row_notify.add_css_class("notify-master")',
                      self.src)
        # ... and the 10px that used to sit in CSS is gone: the answers' size
        # has one owner now
        self.assertNotIn("label.answer-caption { font-size: 10px", self.src)
        self.assertNotIn("label.answer-value { font-size: 10px", self.src)

    def test_the_gap_is_the_counts_answer(self):
        """间隔 is always drawn: at 1次 it reads 0 and nothing can change it,
        anywhere else it is the picker."""
        self.assertIn('row["chips"]["gap"][0].set_visible(not once)', self.src)
        self.assertIn('row["gap_fixed"].set_visible(once)', self.src)
        self.assertIn('Gtk.Label(label="0")', self.src)

    def test_a_notification_is_two_rows(self):
        """One notification, one card: its name with the number and the switch
        on one row, its three answers on the next -- the shape Android draws,
        instead of five rows with a label each."""
        page = re.search(r"def _notify_page\(.*?\n    def ", self.src, re.S).group(0)
        self.assertIn("g.add(self._notify_title_row(n, self.notify[n.key]))", page)
        self.assertIn("g.add(self._notify_answers_row(n, self.notify[n.key]))", page)
        row = re.search(r"def _notify_answers_row\(.*?\n    def ", self.src,
                        re.S).group(0)
        # the three chips are one loop, and the only thing each brings is its
        # own list of choices
        self.assertIn("for field, title, items in (", row)
        for part in ('("kind", _("通知方式")', '("times", _("次数")',
                     '("gap", _("间隔")'):
            with self.subTest(part=part):
                self.assertIn(part, row)
        self.assertIn("self._on_notify_answer(", row)
        # the number is a plain spin with its unit beside it: an output
        # formatter plus numeric mode rewrote the value back into the model
        # once, so neither is here
        title = re.search(r"def _notify_title_row\(.*?\n    def ", self.src,
                          re.S).group(0)
        self.assertIn("Gtk.SpinButton.new_with_range(n.low, n.high, n.step)",
                      title)
        self.assertIn("spin.set_numeric(False)", title)
        self.assertIn("Gtk.Switch()", title)
        self.assertNotIn('connect("output"', title)
        # a value we set ourselves is not the user moving it
        self.assertIn("if self._loading or self._spinning:", self.src)

    def test_the_groups_are_the_page_s_own(self):
        self.assertIn("for group in GROUPS:", self.src)
        self.assertIn("Adw.PreferencesGroup(title=group.title())", self.src)
        self.assertIn("for key in group.keys:", self.src)

    def test_a_state_has_no_number_to_set(self):
        self.assertIn("if n.numbered:", self.src)

    def test_the_answers_are_stored_under_the_android_keys(self):
        for key in ("notify", "notify_{n.key}", "notify_{n.key}_at",
                    "notify_{n.key}_kind", "notify_{n.key}_times",
                    "notify_{n.key}_gap"):
            with self.subTest(key):
                self.assertIn(key, self.src)

    def test_a_fresh_install_does_not_start_talking(self):
        self.assertIn('load_ui().get("notify", False)', self.src)

    def test_the_pages_are_the_android_pair_and_a_gear(self):
        """通知 and 高级 are the two tabs; 设置 is the gear after the language,
        as in the Android header -- not a third word."""
        self.assertIn('(("notify", _("通知")), ("panel", _("高级")))', self.src)
        # the pair is at the header's left edge, not centered in the title slot
        self.assertIn("header.pack_start(tabs)", self.src)
        self.assertNotIn("header.set_title_widget(tabs)", self.src)
        # ... and the freed title slot stays empty, not 电电
        self.assertIn("header.set_title_widget(Gtk.Box())", self.src)
        self.assertIn('stack.add_named(self._settings_page(), "settings")',
                      self.src)
        self.assertIn('stack.set_visible_child_name("panel")', self.src)
        self.assertIn("def _settings_button(self):", self.src)
        self.assertIn('Gtk.Button(label="\\u2699")', self.src)
        # a gear is an icon: give it the whole target, not a hairline glyph
        self.assertIn("button.gear-btn { font-size: 24px; min-width: 36px;",
                      self.src)
        self.assertIn("min-height: 36px;", self.src)
        self.assertIn('btn.set_tooltip_text(_("设置"))', self.src)
        # pack_end reverses, so the gear is packed first to sit last
        order = re.search(
            r"header\.pack_end\(self\._settings_button\(\)\)"
            r".*?header\.pack_end\(self\._language_button\(\)\)"
            r".*?header\.pack_end\(self\._background_button\(\)\)",
            self.src, re.S)
        self.assertIsNotNone(order, "the gear comes after the language")
        self.assertIn('self.stack.set_visible_child_name("settings")',
                      self.src)

    def test_the_settings_page_is_only_what_pmos_needs(self):
        """No 自启动 or 通知权限 here: there is no system screen for either,
        so 设置 is 关于, and all of it can be copied."""
        page = re.search(r"def _settings_page\(.*?\n    def ",
                         self.src, re.S).group(0)
        self.assertIn('_("关于")', page)
        self.assertIn('head.add_css_class("about-heading")', page)
        self.assertIn("label.about-heading { font-size: 18px; }", self.src)
        self.assertIn('colon = "：" if LANGUAGE == "zh" else ":"', page)
        self.assertIn('key(_("版本"))', page)
        self.assertIn("build_label()", page)
        self.assertIn("RELEASES_URL", page)
        self.assertIn("_open_releases", page)
        for word in ("版本", "作者", "更新", "隐私"):
            with self.subTest(word=word):
                self.assertIn('_("%s")' % word, page)
        # ... plain text, not a card: one selectable label, the URL a link
        self.assertIn("set_selectable(True)", page)
        self.assertIn('connect("activate-link"', page)
        self.assertNotIn("PreferencesGroup", page)
        self.assertNotIn("复制关于信息", page)
        # ... and nothing Android-only slipped in: no system page to open
        self.assertNotIn("openAutostartSettings", page)
        self.assertNotIn("openNotificationSettings", page)

    def test_the_sleep_record_sits_under_the_promise(self):
        """禁止休眠 promises the system will not sleep; the row under it is
        where that can be caught.  It is a record, not a notification: no
        switch, no 通知方式, no 次数, no 间隔 -- the count is the whole row,
        and a tap opens the history it kept."""
        self.assertIn('Adw.ActionRow(title=_("休眠记录"))', self.src)
        self.assertIn("self.row_sleep.set_activatable(True)", self.src)
        self.assertIn('self.sleep_count.set_text(f\'{rec["count"]}\' + _("次"))',
                      self.src)
        self.assertIn('Adw.MessageDialog(modal=True, transient_for=self,',
                      self.src)
        self.assertIn('heading=_("休眠记录")', self.src)
        self.assertIn('self.row_sleep.set_subtitle(self._sleep_line(rec))', self.src)
