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

"""The daemon's device contract and control logic.

Everything runs against a fake sysfs tree: the daemon's paths are module level
and its loop body is one function (daemon.step), so these tests can drive a
whole pass and then look at exactly what was written and what was published.
"""
import json
import os
import shutil
import tempfile
import time
import unittest

from tests.helpers import (BAT_PATH, CHG_PATH, FakeSysfs, StubInhibitor,
                           args_for, read_json)

import daemon  # noqa: E402  (helpers put the repository root on sys.path)


class DaemonTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeSysfs()
        self.tmp = tempfile.mkdtemp(prefix="chargecap-cfg-")
        self.args = args_for(self.fake, self.tmp)
        self.inh = StubInhibitor()
        self.st = daemon.LoopState()
        self.saved = (daemon.BAT, daemon.CHG, daemon.PROBE_WAIT)
        daemon.BAT, daemon.CHG = self.fake.bat, self.fake.chg
        daemon.PROBE_WAIT = 0            # no need to actually wait in a test
        self.writes = []
        self.real_set_charger = daemon.set_charger
        daemon.set_charger = self._record_charger

    def tearDown(self):
        daemon.BAT, daemon.CHG, daemon.PROBE_WAIT = self.saved
        daemon.set_charger = self.real_set_charger
        self.fake.remove()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _record_charger(self, allow):
        self.writes.append("1" if allow else "0")
        return self.real_set_charger(allow)

    def cfg(self, **over):
        cfg = dict(daemon.DEFAULT)
        cfg.update(over)
        return cfg

    def run_step(self, **over):
        self.writes = []          # only this pass's writes are asserted on
        return daemon.step(self.args, self.cfg(**over), self.st, self.inh)

    # ---- the machine-specific contract -------------------------------
    def test_device_paths_are_the_ones_this_app_was_written_for(self):
        self.assertEqual(BAT_PATH, "/sys/class/power_supply/bq27411-0")
        self.assertEqual(CHG_PATH, "/sys/class/power_supply/pmi8998-charger")

    def test_the_known_names_are_only_the_fallback(self):
        self.assertEqual(daemon.GAUGE_FALLBACK, BAT_PATH)
        self.assertEqual(daemon.CHARGER_FALLBACK, CHG_PATH)

    def test_supplies_are_found_by_their_attributes(self):
        """The OnePlus 6T exposes the same gauge/charger under the same driver,
        but the directory names are the driver's business -- so they are found
        by what they expose, not by name."""
        root = tempfile.mkdtemp(prefix="charge-limit-supply-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        # a decoy that only looks a bit like a charger
        os.makedirs(os.path.join(root, "usb"))
        open(os.path.join(root, "usb", "online"), "w").write("1")
        gauge = os.path.join(root, "bq27411-1")
        charger = os.path.join(root, "pmi8998_charger")
        os.makedirs(gauge)
        os.makedirs(charger)
        for attr in daemon.GAUGE_ATTRS:
            open(os.path.join(gauge, attr), "w").write("1")
        for attr in daemon.CHARGER_ATTRS:
            open(os.path.join(charger, attr), "w").write("1")
        self.assertEqual(daemon.find_supply(daemon.GAUGE_ATTRS, root), gauge)
        self.assertEqual(daemon.find_supply(daemon.CHARGER_ATTRS, root),
                         charger)
        # nothing there -> None, and the caller falls back
        self.assertIsNone(daemon.find_supply(daemon.GAUGE_ATTRS,
                                             os.path.join(root, "nope")))

    def test_an_empty_tree_falls_back_to_the_known_paths(self):
        root = tempfile.mkdtemp(prefix="charge-limit-supply-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.assertIsNone(daemon.find_supply(daemon.GAUGE_ATTRS, root))
        self.assertIsNone(daemon.find_supply(daemon.CHARGER_ATTRS, root))

    def test_reads_and_writes_only_the_expected_files(self):
        """A wrong file name reads as None and silently does nothing: the
        fake tree holds only the real names, and the state has to come out
        complete."""
        state = self.run_step()
        self.assertEqual(state["capacity"], 50)
        self.assertEqual(state["voltage_v"], 4.0)
        self.assertEqual(state["current_a"], -0.5)
        self.assertEqual(state["temp_c"], 28.0)
        self.assertEqual(state["status"], "Charging")
        self.assertEqual(state["current_limit_max"], 1800)
        # the two files it writes
        self.assertEqual(self.fake.get("chg", "status"), "1")
        self.assertEqual(self.fake.get("chg", "current_max"), "1800000")

    def test_state_keys_are_the_interface_the_gui_reads(self):
        state = self.run_step()
        self.assertEqual(set(state), {
            "capacity", "voltage_v", "current_a", "power_w", "temp_c",
            "status", "plugged", "limit_enabled", "upper", "lower", "mode",
            "charging_stopped", "inhibit", "inhibit_sleep", "current_limit",
            "current_limit_max", "updated"})
        self.assertEqual(state["power_w"], 4.0 * -0.5)

    def test_state_file_is_written_valid_and_world_readable(self):
        self.run_step()
        with open(self.args.state) as f:
            self.assertEqual(read_json(self.args.state), json.load(f))
        mode = os.stat(self.args.state).st_mode & 0o777
        self.assertEqual(mode, 0o644)
        self.assertEqual(self.fake.get("chg", "status"), "1")

    # ---- the control loop --------------------------------------------
    def test_defaults_leave_charging_alone(self):
        """A fresh install: no limit, no input limit of its own, no
        inhibition -- but it still writes the rated max, so nothing lingers."""
        state = self.run_step()
        self.assertEqual(state["mode"], "disabled")
        self.assertFalse(state["limit_enabled"])
        self.assertFalse(state["inhibit"])
        self.assertEqual(self.writes, ["1"])
        self.assertEqual(self.fake.get("chg", "current_max"), "1800000")

    def test_stop_at_upper_and_resume_at_lower(self):
        self.fake.set("bat", "capacity", 70)
        state = self.run_step(limit_enabled=True, upper=70, lower=68)
        self.assertEqual(state["mode"], "stop")
        self.assertTrue(state["charging_stopped"])
        self.assertEqual(self.fake.get("chg", "status"), "0")
        self.assertTrue(self.st.input_off)

        self.fake.set("bat", "capacity", 68)
        state = self.run_step(limit_enabled=True, upper=70, lower=68)
        self.assertEqual(state["mode"], "charge")
        self.assertEqual(self.fake.get("chg", "status"), "1")
        self.assertFalse(self.st.input_off)

    def test_in_band_holds_and_never_turns_charging_on(self):
        """The whole point of the hysteresis: in the band the input is left
        exactly as it is, so a stop is not undone at 69%."""
        self.fake.set("bat", "capacity", 69)
        self.fake.set("chg", "status", 0)
        self.st.input_off = True
        self.st.last_probe = time.time()   # probe cadence is tested elsewhere
        state = self.run_step(limit_enabled=True, upper=70, lower=68)
        self.assertEqual(state["mode"], "hold")
        self.assertEqual(self.writes, [])                  # nothing written
        self.assertEqual(self.fake.get("chg", "status"), "0")   # still off

        self.st.input_off = False
        self.fake.set("chg", "status", 1)
        state = self.run_step(limit_enabled=True, upper=70, lower=68)
        self.assertEqual(state["mode"], "hold")
        self.assertEqual(self.writes, [])
        self.assertEqual(self.fake.get("chg", "status"), "1")   # still on

    def test_decide_mode_table(self):
        decide = daemon.decide_mode
        self.assertEqual(decide(False, 99, 70, 68, True), ("disabled", False))
        self.assertEqual(decide(True, 70, 70, 68, False), ("stop", True))
        self.assertEqual(decide(True, 71, 70, 68, False), ("stop", True))
        self.assertEqual(decide(True, 68, 70, 68, False), ("charge", False))
        self.assertEqual(decide(True, 50, 70, 68, False), ("charge", False))
        self.assertEqual(decide(True, 69, 70, 68, True), ("hold", True))
        self.assertEqual(decide(True, 69, 70, 68, False), ("hold", False))
        self.assertEqual(decide(True, None, 70, 68, True), (None, True))

    # ---- USB input current limit -------------------------------------
    def test_no_limit_is_written_as_the_rated_maximum(self):
        """0 means "no limit", and it is written out (not skipped) so an
        earlier limit cannot linger in the charger.  The UI still sees 0."""
        state = self.run_step(current_limit=0)
        self.assertEqual(self.fake.get("chg", "current_max"), "1800000")
        self.assertEqual(state["current_limit"], 0)

    def test_limit_is_clamped_to_the_rated_maximum(self):
        state = self.run_step(current_limit=2500)
        self.assertEqual(self.fake.get("chg", "current_max"), "1800000")
        self.assertEqual(state["current_limit"], 1800)

    def test_limit_below_rated_is_used_as_is(self):
        state = self.run_step(current_limit=300)
        self.assertEqual(self.fake.get("chg", "current_max"), "300000")
        self.assertEqual(state["current_limit"], 300)

    def test_limit_is_reasserted_every_pass(self):
        """The driver forgets it when the input is detached."""
        self.run_step(current_limit=500)
        self.fake.set("chg", "current_max", 0)
        self.run_step(current_limit=500)
        self.assertEqual(self.fake.get("chg", "current_max"), "500000")

    def test_limit_is_independent_of_the_limit_switch(self):
        self.run_step(limit_enabled=False, current_limit=400)
        self.assertEqual(self.fake.get("chg", "current_max"), "400000")

    # ---- plugged detection -------------------------------------------
    def test_online_is_used_while_charging_is_allowed(self):
        self.st.input_off = False        # the input is on: no probing needed
        self.fake.set("chg", "online", 1)
        state = self.run_step()
        self.assertTrue(state["plugged"])
        self.assertEqual(self.writes, ["1"])       # no probing happened
        self.fake.set("chg", "online", 0)
        state = self.run_step()
        self.assertFalse(state["plugged"])

    def test_suspended_input_is_probed_and_the_result_remembered(self):
        """With the input held off, online is 0 by construction, so the only
        way to see VBUS is to re-enable it for PROBE_WAIT."""
        self.fake.set("bat", "capacity", 70)
        self.fake.set("chg", "online", 1)
        self.st.input_off = True
        state = self.run_step(limit_enabled=True, upper=70, lower=68)
        self.assertTrue(state["plugged"])
        self.assertIn("1", self.writes)            # the probe re-enabled it
        self.assertEqual(self.writes[-1], "0")     # and put it back
        self.assertTrue(self.st.probe_plugged)

        # unplugged: the probe keeps reporting 未连接
        self.fake.set("chg", "online", 0)
        self.st.last_probe = 0
        state = self.run_step(limit_enabled=True, upper=70, lower=68)
        self.assertFalse(state["plugged"])
        self.assertFalse(self.st.probe_plugged)

    def test_no_probing_when_nothing_would_resume_charging(self):
        """Below 下限 the loop charges anyway, so there is nothing to probe."""
        self.fake.set("bat", "capacity", 50)
        self.st.input_off = False
        self.run_step(limit_enabled=True, upper=70, lower=68)
        self.assertEqual(self.writes, ["1"])

    # ---- config: defaults, clamping, requests ------------------------
    def test_defaults_do_not_touch_the_system(self):
        cfg = daemon.load_config(os.path.join(self.tmp, "missing.json"))
        self.assertFalse(cfg["limit_enabled"])
        self.assertFalse(cfg["inhibit_sleep"])
        self.assertEqual(cfg["current_limit"], 0)
        self.assertEqual((cfg["upper"], cfg["lower"]), (70, 68))

    def test_config_is_clamped(self):
        path = os.path.join(self.tmp, "config.json")
        cfg = daemon.load_config(path)          # writes nothing
        with open(path, "w") as f:
            json.dump({"upper": 500, "lower": 499, "current_limit": 99999,
                       "limit_enabled": 1, "inhibit_sleep": 0}, f)
        cfg = daemon.load_config(path)
        self.assertEqual(cfg["upper"], 100)
        self.assertEqual(cfg["lower"], 98)      # upper - 2, never above
        self.assertEqual(cfg["current_limit"], 3000)
        self.assertTrue(cfg["limit_enabled"])
        self.assertFalse(cfg["inhibit_sleep"])

    def test_a_request_is_applied_persisted_and_consumed(self):
        cfg = daemon.load_config(self.args.config)
        with open(self.args.request, "w") as f:
            json.dump({"command": "set", "limit_enabled": True, "upper": 80,
                       "lower": 70, "current_limit": 700,
                       "inhibit_sleep": True}, f)
        cfg = daemon.apply_request(self.args.config, self.args.request, cfg)
        self.assertTrue(cfg["limit_enabled"])
        self.assertEqual((cfg["upper"], cfg["lower"]), (80, 70))
        self.assertEqual(cfg["current_limit"], 700)
        self.assertTrue(cfg["inhibit_sleep"])
        self.assertFalse(os.path.exists(self.args.request))    # consumed
        self.assertEqual(read_json(self.args.config)["upper"], 80)  # persisted

    def test_a_request_cannot_widen_the_band_or_the_limit(self):
        cfg = daemon.load_config(self.args.config)
        with open(self.args.request, "w") as f:
            json.dump({"command": "set", "upper": 40, "lower": 90,
                       "current_limit": -5}, f)
        cfg = daemon.apply_request(self.args.config, self.args.request, cfg)
        self.assertLessEqual(cfg["lower"], cfg["upper"] - 2)
        self.assertGreaterEqual(cfg["current_limit"], 0)

    def test_a_broken_request_is_ignored(self):
        cfg = daemon.load_config(self.args.config)
        before = dict(cfg)
        with open(self.args.request, "w") as f:
            f.write("{not json")
        cfg = daemon.apply_request(self.args.config, self.args.request, cfg)
        self.assertEqual(cfg, before)
        self.assertFalse(os.path.exists(self.args.request))

    def test_unknown_command_changes_nothing(self):
        cfg = daemon.load_config(self.args.config)
        before = dict(cfg)
        with open(self.args.request, "w") as f:
            json.dump({"command": "nonsense", "upper": 10}, f)
        cfg = daemon.apply_request(self.args.config, self.args.request, cfg)
        self.assertEqual(cfg, before)

    # ---- inhibit ------------------------------------------------------
    def test_sleep_is_inhibited_only_while_the_toggle_is_on(self):
        self.run_step(inhibit_sleep=True)
        self.assertEqual(self.inh.calls, ["acquire"])
        self.assertTrue(self.inh.active)
        self.run_step(inhibit_sleep=True)
        self.assertEqual(self.inh.calls, ["acquire"])      # idempotent
        self.run_step(inhibit_sleep=False)
        self.assertEqual(self.inh.calls, ["acquire", "release"])
        self.assertFalse(self.inh.active)

    # ---- the loop must survive a broken device ------------------------
    def test_missing_metrics_do_not_crash_the_loop(self):
        for name in ("capacity", "voltage_now", "current_now", "temp",
                     "constant_charge_current_max"):
            os.remove(self.fake.path("bat", name))
        state = self.run_step(current_limit=500)
        self.assertIsNone(state["capacity"])
        self.assertIsNone(state["voltage_v"])
        self.assertIsNone(state["mode"])
        self.assertEqual(self.writes, [])          # nothing decided
        self.assertEqual(self.fake.get("chg", "current_max"), "500000")
