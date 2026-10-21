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

"""Shared bits for the tests: paths, a fake sysfs tree, a stub inhibitor."""
import os
import shutil
import sys
import tempfile
import types

# the repository root, so the tests can import the daemon / read the GUI
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# the device this app is written for (OnePlus 6, mainline kernel)
BAT_PATH = "/sys/class/power_supply/bq27411-0"
CHG_PATH = "/sys/class/power_supply/pmi8998-charger"

# what the daemon reads from the gauge, and from the charger
GAUGE_FILES = ("capacity", "voltage_now", "current_now", "temp",
               "constant_charge_current_max", "charge_full", "health")
CHARGER_FILES = ("online", "status", "usb_type", "current_max")

# a screen this small has to keep working (portrait, logical pixels)
SMALLEST_SCREEN = 360


class FakeSysfs:
    """A temp directory tree that stands in for the device's sysfs."""

    def __init__(self, capacity=50, cc_max=1800000, online=1,
                 status="Charging"):
        self.root = tempfile.mkdtemp(prefix="chargecap-test-")
        self.bat = os.path.join(self.root, "bq27411-0")
        self.chg = os.path.join(self.root, "pmi8998-charger")
        os.makedirs(self.bat)
        os.makedirs(self.chg)
        self.set("bat", "capacity", capacity)
        self.set("bat", "voltage_now", 4000000)
        self.set("bat", "current_now", -500000)
        self.set("bat", "temp", 280)
        self.set("bat", "constant_charge_current_max", cc_max)
        self.set("bat", "charge_full", 2700000)
        self.set("bat", "health", 83)
        self.set("chg", "online", online)
        self.set("chg", "status", status)
        self.set("chg", "usb_type", "Unknown SDP [DCP] CDP")
        self.set("chg", "current_max", 0)

    def path(self, which, name):
        return os.path.join(self.bat if which == "bat" else self.chg, name)

    def set(self, which, name, value):
        with open(self.path(which, name), "w") as f:
            f.write(str(value))

    def get(self, which, name):
        try:
            with open(self.path(which, name)) as f:
                return f.read().strip()
        except OSError:
            return None

    def remove(self):
        shutil.rmtree(self.root, ignore_errors=True)


class StubInhibitor:
    """Stands in for the systemd-inhibit child."""

    def __init__(self):
        self.active = False
        self.calls = []

    def acquire(self):
        self.active = True
        self.calls.append("acquire")

    def release(self):
        self.active = False
        self.calls.append("release")


def args_for(fake, tmpdir):
    """The parsed-arguments stand-in the daemon's step() takes."""
    return types.SimpleNamespace(
        state=os.path.join(tmpdir, "state.json"),
        config=os.path.join(tmpdir, "config.json"),
        request=os.path.join(tmpdir, "request.json"))


def read_json(path):
    import json
    with open(path) as f:
        return json.load(f)


# ---- reading the GUI without importing it -------------------------------
# The GUI is a GTK script (and has no .py suffix), so the tests read its source
# instead of importing it: that way the whole suite runs in CI with nothing but
# python3 installed.

GUI_SRC = os.path.join(ROOT, "chargecap")


def source(name):
    """A file from the repository as text: the GUI, the notifier, a unit."""
    with open(os.path.join(ROOT, name)) as f:
        return f.read()


def gui_source():
    return source("chargecap")


def gui_tree():
    import ast
    return ast.parse(gui_source())


def _value(node):
    """Evaluate a literal, treating _("x") as the source string "x"."""
    import ast
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_":
        return _value(node.args[0])
    if isinstance(node, ast.Tuple):
        return tuple(_value(e) for e in node.elts)
    if isinstance(node, ast.List):
        return [_value(e) for e in node.elts]
    if isinstance(node, ast.Dict):
        return {_value(k): _value(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.JoinedStr):      # f-string: not a literal we need
        raise ValueError("f-string is not a literal")
    raise ValueError(f"cannot evaluate {type(node).__name__}")


def gui_constant(name):
    """The value of a module level constant in the GUI's source."""
    import ast
    for node in gui_tree().body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if getattr(target, "id", None) == name:
                    return _value(node.value)
    raise AssertionError(f"{name} is not a module level constant")


def gui_source_strings():
    """Every string passed to _() in the GUI's source."""
    import ast
    out = set()
    for node in ast.walk(gui_tree()):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_"
                and node.args and isinstance(node.args[0], ast.Constant)):
            out.add(node.args[0].value)
    return out


def notify_strings():
    """Every word the notification table asks for, in either language.

    The table is written in Chinese and translated where it is read, so the
    words are collected by reading it with a translator that records what it is
    asked for -- the same way the panel asks.
    """
    import notifications
    seen = set()
    previous = notifications._translate

    def record(text):
        seen.add(text)
        return text

    voice, notifications.VOICE_CMD = notifications.VOICE_CMD, "/usr/bin/spd-say"
    notifications.set_translator(record)
    try:
        for n in notifications.NOTIFICATIONS:
            n.title()
            n.short()
            n.label()
            n.says(n.default)
            n.until_label()
            n.counts()
        for group in notifications.GROUPS:
            group.title()
        # with a voice in the house, so the ways that need one are collected
        # too -- the panel offers them wherever spd-say is installed
        notifications.spoken_kinds()
    finally:
        notifications.set_translator(previous)
        notifications.VOICE_CMD = voice
    return seen


def daemon_default_args():
    """The daemon's --config/--request/--state defaults, read from its source."""
    import re
    with open(os.path.join(ROOT, "daemon.py")) as f:
        src = f.read()
    return {name: path for name, path in re.findall(
        r'add_argument\("--(\w+)", default="([^"]+)"\)', src)}
