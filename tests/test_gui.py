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
import os
import re
import unittest

from tests.helpers import (GUI_SRC, SMALLEST_SCREEN, gui_constant,
                           gui_source, gui_source_strings, gui_tree)
from tests import helpers

import daemon


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


class TranslationTest(unittest.TestCase):
    def setUp(self):
        self.en = gui_constant("EN")
        self.scale = gui_constant("SCALE")

    def test_every_translated_string_has_a_translation(self):
        used = gui_source_strings()
        missing = sorted(s for s in used if s not in self.en)
        self.assertEqual(missing, [], f"untranslated: {missing}")

    def test_no_stale_translations(self):
        """An entry nobody asks for is dead weight (or a renamed string)."""
        used = gui_source_strings()
        unused = sorted(k for k in self.en if k not in used)
        self.assertEqual(unused, [], f"unused entries: {unused}")

    def test_every_language_declares_a_complete_type_scale(self):
        languages = {"zh", "en"}
        self.assertEqual(set(self.scale), languages)
        keys = {"title", "key", "small", "value", "sub", "spin", "btn",
                "btnpad"}
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
                     "spinbutton.limit-spin text", "row.metric-row label"):
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

    def test_chart_keeps_five_divisions(self):
        self.assertEqual(int(self.rule(
            r"GRID_DIVS = (\d+)\s+# divisions of the time axis").group(1)), 5)
        m = self.rule(r"TICKS = \(([^)]*)\)")
        self.assertEqual(len([t for t in m.group(1).split(",") if t.strip()]), 5)

    def test_window_choices_are_the_documented_range(self):
        windows = gui_constant("WINDOWS")
        self.assertEqual(windows[0], ("30s", 30))
        self.assertEqual(windows[-1], ("48h", 172800))
        self.assertEqual(len(windows), 15)


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

    def test_the_background_button_sits_left_of_the_language_one(self):
        pack = re.findall(r"header\.pack_end\(self\.(\w+)\(\)\)", self.src)
        self.assertEqual(pack, ["_language_button", "_background_button"],
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

    def test_the_interval_is_remembered(self):
        self.assertIn('d["sample_ms"] = want', self.src)
        self.assertIn('.get("sample_ms")', self.src)
        self.assertIn("SAMPLE_MS_CHOICE", self.src)

    def test_the_tick_follows_the_interval_or_the_panel(self):
        self.assertIn("def _tick_ms(self):", self.src)
        self.assertIn('return max(10, min(SAMPLE_MS, SAMPLE_MS_CHOICE))', self.src)
        self.assertIn("GLib.timeout_add(self._tick_ms(), self.refresh)", self.src)
        # ... and only one chain: the first refresh arms it, later ones re-arm it
        self.assertEqual(self.src.count("GLib.timeout_add(self._tick_ms()"), 1)

    def test_a_sample_is_stored_only_when_it_is_due(self):
        self.assertIn("def _sample_due(self, now):", self.src)
        self.assertIn("if self._sample_due(now):", self.src)
        self.assertIn("or now - self._stored_at >= SAMPLE_MS_CHOICE / 1000.0", self.src)

    def test_the_panel_repaints_at_its_own_pace(self):
        self.assertIn("paint = now - self._painted_at >= SAMPLE_MS / 1000.0", self.src)
        self.assertIn("if paint:\n            self.chart.queue_draw()", self.src)
