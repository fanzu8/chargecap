#!/usr/bin/env python3

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

# Battery chargecap daemon for postmarketOS (OnePlus 6 / 6T, sdm845,
# pmi8998-charger + bq27411 fuel gauge).
#
# Two states, controlled from the GUI:
#   limit_enabled = true  -> "限制中": stop charging at `upper`, resume at `lower`
#   limit_enabled = false -> "已取消": behave as if the service did not exist
#                            (charging allowed, no suspend inhibition)
# It also asserts the USB input current limit (mA) whenever the input is on;
# that knob is independent of the charge limit switch.
# The GUI (normal user) only writes ~/.config/chargecap/request.json;
# this daemon (root) owns the authoritative config and writes state.json for the GUI.
#
# The charging control is *stateless and idempotent*: each loop it computes the
# desired state and writes it.  regmap_update_bits() skips unchanged writes, so
# this is cheap, and it is correct across daemon restarts (no in-memory flag to
# lose).

import argparse
import json
import os
import signal
import subprocess
import sys
import time

# sysfs nodes: found by the attributes they expose rather than by name, so the
# same build works on the OnePlus 6T (fajita) and other mainline Qualcomm
# phones.  The names at the bottom are the fallback for the device this was
# written on.
SUPPLY_ROOT = "/sys/class/power_supply"
GAUGE_ATTRS = ("capacity", "voltage_now", "current_now", "temp",
               "constant_charge_current_max")
CHARGER_ATTRS = ("online", "status", "usb_type", "current_max")
GAUGE_FALLBACK = "/sys/class/power_supply/bq27411-0"
CHARGER_FALLBACK = "/sys/class/power_supply/pmi8998-charger"


def find_supply(required, root=SUPPLY_ROOT):
    """The first power_supply directory exposing all of `required`."""
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return None
    for name in names:
        path = os.path.join(root, name)
        if all(os.path.exists(os.path.join(path, a)) for a in required):
            return path
    return None


def _detected():
    return (find_supply(GAUGE_ATTRS) or GAUGE_FALLBACK,
            find_supply(CHARGER_ATTRS) or CHARGER_FALLBACK)


BAT, CHG = _detected()

POLL = 3                  # main loop period (s)
PROBE_EVERY = 1           # probe cadence in polls, while the input is held off
PROBE_WAIT = 0.05         # how long to re-enable the input while probing (s)
                          # (the driver reports VBUS in <20ms, measured)

DEFAULT = {
    # a fresh install does nothing to the system until it is switched on:
    # no charge limit, no USB input current limit, no sleep inhibition
    "limit_enabled": False,
    "upper": 70,
    "lower": 68,
    "inhibit_sleep": False,       # global: hold the sleep block whenever on
    "current_limit": 0,           # USB input limit (mA); 0 = no limit (rated max)
}

# Fallback for the rated maximum charge current when the gauge does not report
# it: the loop writes this when the limit is 0 (no limit), so a limit set
# earlier cannot linger.
RATED_MAX_MA = 1800

def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, file=sys.stderr, flush=True)

def read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except Exception:
        return None

def read_str(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return None

def set_charger(allow):
    """Idempotent: write 1 to allow charging, 0 to suspend USB input."""
    try:
        with open(os.path.join(CHG, "status"), "w") as f:
            f.write("1" if allow else "0")
        return True
    except Exception as e:
        log(f"charger write failed: {e}")
        return False

# Last input current limit we wrote, for logging only.
_last_limit = None

def set_input_current_limit(ma):
    """Idempotent: set the USB input current limit (mA).

    The charger only keeps this value while an input is really attached (it
    reads back 0 with nothing plugged in), so callers re-assert it on every
    loop that leaves the input enabled rather than once at startup.
    """
    global _last_limit
    try:
        with open(os.path.join(CHG, "current_max"), "w") as f:
            f.write(str(int(ma) * 1000))
        if ma != _last_limit:
            log(f"input current limit -> {ma} mA")
    except Exception as e:
        if ma != _last_limit:
            log(f"input current limit {ma} mA failed: {e}")
    _last_limit = ma

class Inhibitor:
    """Hold a logind sleep-block inhibitor via a systemd-inhibit child."""
    def __init__(self):
        self.proc = None

    def acquire(self):
        if self.proc and self.proc.poll() is None:
            return
        try:
            self.proc = subprocess.Popen(
                ["systemd-inhibit", "--what=sleep", "--mode=block",
                 "--who=chargecap",
                 "--why=Sleep blocked by chargecap",
                 "cat"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log("suspend inhibitor acquired")
        except Exception as e:
            log(f"inhibitor acquire failed: {e}")
            self.proc = None

    def release(self):
        if not self.proc:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            pass
        self.proc = None
        log("suspend inhibitor released")

    @property
    def active(self):
        return bool(self.proc and self.proc.poll() is None)

def clampi(v, lo, hi, d):
    try:
        v = int(v)
    except Exception:
        return d
    return max(lo, min(hi, v))

def load_config(path):
    cfg = dict(DEFAULT)
    try:
        with open(path) as f:
            user = json.load(f)
        if isinstance(user, dict):
            for k in ("upper", "lower", "inhibit_sleep", "limit_enabled",
                      "current_limit"):
                if k in user:
                    cfg[k] = user[k]
    except FileNotFoundError:
        pass
    except Exception as e:
        log(f"config load error: {e}")
    cfg["limit_enabled"] = bool(cfg["limit_enabled"])
    cfg["inhibit_sleep"] = bool(cfg["inhibit_sleep"])
    cfg["upper"] = clampi(cfg["upper"], 5, 100, 70)
    cfg["lower"] = clampi(cfg["lower"], 5, 100, 68)
    cfg["current_limit"] = clampi(cfg["current_limit"], 0, 3000, 0)
    if cfg["lower"] > cfg["upper"] - 2:
        cfg["lower"] = max(5, cfg["upper"] - 2)
    return cfg

def save_config(path, cfg):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path)

def apply_request(cfg_path, request_path, cfg):
    """If a request file exists, merge it into cfg, persist, and delete it."""
    if not os.path.exists(request_path):
        return cfg
    try:
        with open(request_path) as f:
            req = json.load(f)
    except Exception as e:
        log(f"request parse error: {e}")
        req = None
    try:
        os.unlink(request_path)
    except Exception:
        pass
    if not isinstance(req, dict):
        return cfg
    cmd = req.get("command")
    log(f"request: {cmd}")
    if cmd == "set":
        if "limit_enabled" in req:
            cfg["limit_enabled"] = bool(req["limit_enabled"])
        if "upper" in req:
            cfg["upper"] = clampi(req["upper"], 5, 100, cfg["upper"])
        if "lower" in req:
            cfg["lower"] = clampi(req["lower"], 5, 100, cfg["lower"])
        if cfg["lower"] > cfg["upper"] - 2:
            cfg["lower"] = max(5, cfg["upper"] - 2)
        if "inhibit_sleep" in req:
            cfg["inhibit_sleep"] = bool(req["inhibit_sleep"])
        if "current_limit" in req:
            cfg["current_limit"] = clampi(req["current_limit"], 0, 3000,
                                          cfg["current_limit"])
    save_config(cfg_path, cfg)
    return cfg

def decide_mode(enabled, cap, upper, lower, input_off):
    """The chargecap state machine, as a pure function.

    Returns the mode and the new "we hold the input off ourselves" flag.  In
    the band it is "hold": charging is left exactly as it is, so crossing back
    into the band never turns it on -- only dropping to 下限 does.  With the
    limit switched off charging is always allowed (idempotent, so a restart
    fixes a charger we suspended before).
    """
    if cap is None:
        return None, input_off
    if not enabled:
        return "disabled", False
    if cap >= upper:
        return "stop", True
    if cap <= lower:
        return "charge", False
    return "hold", input_off


def input_limit(cfg, cc_max):
    """The USB input current limit to write, and the value to publish.

    A setting of 0 means "no limit", and then the rated maximum is written out
    rather than skipped: a value set earlier would otherwise stay in the
    charger until the next re-plug.  The gauge's rated maximum is a hard
    ceiling, so a stale or hand-edited config cannot exceed it either.
    """
    limit = cfg["current_limit"]
    rated = (cc_max // 1000) if cc_max else RATED_MAX_MA
    applied = rated if limit <= 0 else min(limit, rated)
    return applied, (0 if limit <= 0 else applied)


class LoopState:
    """The little bits of state the control loop carries between passes."""

    def __init__(self):
        self.input_off = True       # we may have suspended the input before starting
        self.probe_plugged = False  # last VBUS probe result while it is off
        self.last_probe = 0.0
        self.last_mode = None


def step(args, cfg, st, inh):
    """One pass of the control loop; returns the state dict it published.

    Everything device specific goes through the module level BAT / CHG paths,
    so a test can point those at a fake sysfs tree and then check exactly what
    was written and what came out in state.json.
    """
    now = time.time()
    upper, lower = cfg["upper"], cfg["lower"]
    enabled = cfg["limit_enabled"]

    cap = read_int(os.path.join(BAT, "capacity"))
    v = read_int(os.path.join(BAT, "voltage_now"))
    i = read_int(os.path.join(BAT, "current_now"))
    t = read_int(os.path.join(BAT, "temp"))
    online = read_int(os.path.join(CHG, "online"))
    status = read_str(os.path.join(CHG, "status"))
    cc_max = read_int(os.path.join(BAT, "constant_charge_current_max"))

    # --- plugged detection ------------------------------------------------
    # "online" is the driver's power path state: it is 1 only while the input
    # is enabled *and* a charger really feeds it.  So it reads 0 whenever
    # nothing is attached -- and also while we hold the input off ourselves,
    # which is why a suspended input is briefly re-enabled to look for VBUS.
    # That probe result has to be remembered: the charger goes back to 0 as
    # soon as we re-suspend, so a direct read can only ever be fresh while we
    # are actually allowing charging.
    # usb0's carrier must not be used as a fallback: on this device it stays 1
    # with nothing attached, which made the UI claim 已连接 forever.  A probe
    # runs every poll (3s) and only lasts PROBE_WAIT (50ms), so plug/unplug
    # shows up within a few seconds while the stray charge the probe lets
    # through stays ~1.7% of the time.
    if st.input_off:
        plugged = st.probe_plugged
        if (enabled and cap is not None and cap > lower
                and now - st.last_probe >= PROBE_EVERY * POLL):
            st.last_probe = now
            set_charger(True)             # briefly re-enable to probe VBUS
            time.sleep(PROBE_WAIT)
            st.probe_plugged = read_int(os.path.join(CHG, "online")) == 1
            set_charger(False)            # re-suspend, as it was
            plugged = st.probe_plugged
    else:
        plugged = online == 1

    # --- charging control: stateless, idempotent ---
    mode, st.input_off = decide_mode(enabled, cap, upper, lower, st.input_off)
    if mode is not None and mode != "hold":
        set_charger(mode != "stop")
    if mode != st.last_mode:
        log(f"mode -> {mode} (cap={cap}, {lower}-{upper})")
        st.last_mode = mode

    # --- USB input current limit (independent of the limit switch) ---
    applied, published = input_limit(cfg, cc_max)
    set_input_current_limit(applied)

    # --- inhibit sleep whenever the toggle is on (global) ---
    want_inhibit = cfg["inhibit_sleep"]
    if want_inhibit and not inh.active:
        inh.acquire()
    elif not want_inhibit and inh.active:
        inh.release()

    # --- publish state ---
    state = {
        "capacity": cap,
        "voltage_v": (v / 1e6) if v is not None else None,
        "current_a": (i / 1e6) if i is not None else None,
        "power_w": (v * i / 1e12) if (v is not None and i is not None) else None,
        "temp_c": (t / 10.0) if t is not None else None,
        "status": status,
        "plugged": bool(plugged),
        "limit_enabled": enabled,
        "upper": upper,
        "lower": lower,
        "mode": mode,
        "charging_stopped": (mode == "stop"),
        "inhibit": inh.active,
        "inhibit_sleep": cfg["inhibit_sleep"],
        # the user's setting: 0 reads as "不限制" (the rated max is what the
        # charger was actually told, it is not a limit the user asked for)
        "current_limit": published,
        # rated maximum charge current the gauge reports (read-only)
        "current_limit_max": (cc_max // 1000) if cc_max else None,
        "updated": int(now),
    }
    try:
        tmp = args.state + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.chmod(tmp, 0o644)
        os.replace(tmp, args.state)
    except Exception as e:
        log(f"state write failed: {e}")
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="/var/lib/chargecap/config.json")
    ap.add_argument("--request", default="/home/user/.config/chargecap/request.json")
    ap.add_argument("--state", default="/run/chargecap/state.json")
    args = ap.parse_args()

    log("chargecap daemon starting")
    log(f"gauge: {BAT}, charger: {CHG}")
    os.makedirs(os.path.dirname(args.state), exist_ok=True)

    cfg = load_config(args.config)
    save_config(args.config, cfg)

    st = LoopState()
    inh = Inhibitor()

    running = True

    def _stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    while running:
        cfg = apply_request(args.config, args.request, cfg)
        step(args, cfg, st, inh)
        time.sleep(POLL)

    inh.release()
    log("chargecap daemon stopped")
    return 0

if __name__ == "__main__":
    sys.exit(main())
