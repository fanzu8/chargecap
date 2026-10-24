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

"""chargecap's notifier: the rules, while nobody is looking at the panel.

The panel draws the page and writes the answers to ui.json; the daemon
publishes the readings to state.json.  This service is the half that stays up
with the panel closed: it reads both, says what crosses, and keeps saying it
for as long as a reminder asks.  It also keeps the record of the system's own
sleeps, which is the one thing the panel cannot count by itself -- the panel
is closed exactly when the sleeps happen.

It runs in the user's own session (a systemd user service), so a banner is the
app's banner -- same id, same icon -- and the voice is the phone's.
"""
import json
import os
import signal
import subprocess
import sys
import time

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

# notifications.py lives beside this script in the repository and in
# /usr/local/lib/chargecap once installed
for _path in (os.path.dirname(os.path.abspath(__file__)),
              "/usr/local/lib/chargecap"):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import notifications as rules  # noqa: E402

APP_ID = "org.postmarketos.Chargecap"
UI_FILE = os.path.expanduser("~/.config/chargecap/ui.json")
STATE_FILE = "/run/chargecap/state.json"

TICK_MS = 500          # how often the readings are looked at
STALE_S = 15           # older than this and state.json says nothing we trust

# the words this service says, in the app's English (the panel's EN table is
# the master; the tests keep the two honest).  A sentence is the title and the
# number -- a state's sentence is the title alone.
EN = {
    "充电完成": "Charging complete",
    "电量过低": "Battery low",
    "电源连接": "Power connected",
    "电源断开": "Power disconnected",
    "充电中": "Charging",
    "未充电": "Idle",
    "温度过高": "Too hot",
    "温度过低": "Too cold",
    "电压过高": "Voltage high",
    "电压过低": "Voltage low",
    "充电电流过高": "High charge current",
    "放电电流过高": "High discharge current",
    "功率过高": "High power",
}


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def translator(ui):
    """How this phone says things: the panel's choice, or the system's."""
    lang = ui.get("lang")
    if lang not in ("zh", "en"):
        names = GLib.get_language_names()
        lang = "zh" if any(n.startswith("zh") for n in names) else "en"
    if lang == "zh":
        return lambda text: text
    return lambda text: EN.get(text, text)


class Voice:
    """The sentence out loud, through spd-say when the phone has a voice.

    It only speaks and stops; when to speak again is the reminder's business.
    """

    def __init__(self):
        self._proc = None
        self._group = None
        self._spd = False

    def say(self, text, lang=None):
        self.stop()
        cmd = rules.voice_command(text, lang)
        if cmd:
            try:
                self._spd = os.path.basename(cmd[0]) == "spd-say"
                # the WAV pipeline is `sh -c espeak-ng ... | aplay`; a process
                # group lets stop take the shell and both children together
                self._proc = subprocess.Popen(cmd, start_new_session=True)
                self._group = self._proc.pid
            except Exception:
                self._proc = None
                self._group = None
                self._spd = False

    def stop(self):
        """Silent now: the switch went off, or the next thing is being said."""
        proc, self._proc = self._proc, None
        group, self._group = self._group, None
        spd, self._spd = self._spd, False
        if proc is not None:
            try:
                if group is not None:
                    os.killpg(group, signal.SIGTERM)
                elif proc.poll() is None:
                    proc.terminate()
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
            try:
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if spd:
            # the dispatcher speaks asynchronously; terminating its client is
            # not enough, so send its own stop message too
            try:
                subprocess.run(
                    ["spd-say", "-N", "chargecap", "-n", "main", "-S"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=1)
            except Exception:
                pass


class Reminders:
    """The repeats: say it again 间隔 later, and stop when it is old news.

    The count belongs to the whole notification rather than to the voice alone
    -- a banner is posted again as a voice is said again -- and 0 of them is
    the notification's own endless one: repeat until the reading it waits for
    says the reminder has done its job (the plug going in for 电量过低, the
    power going off for 充电完成).

    The answers are read again at every repeat rather than carried from the
    first, so a line moved or a switch thrown mid-count takes effect from
    there.  And a repeat is only news while the reading is still past the
    line: if the gap was long enough for the battery to come back -- the phone
    cooled down, the charge came up -- the count ends instead of saying a
    thing that is no longer true.
    """

    def __init__(self, notifier):
        self.notifier = notifier
        self.timers = {}        # key -> [GLib source id, said]

    def start(self, key):
        """A crossing: a new reminder takes over rather than stacking up
        behind the old one."""
        self.stop(key)
        self.timers[key] = [None, 0]
        self._step(key)

    def stop(self, key):
        state = self.timers.pop(key, None)
        if state and state[0] is not None:
            GLib.source_remove(state[0])

    def stop_all(self):
        for key in list(self.timers):
            self.stop(key)

    # ---- one delivery, then the wait that leads to the next --------------
    def _step(self, key):
        state = self.timers.get(key)
        if state is None:
            return False
        ui = self.notifier.read_ui()
        if not ui.get("notify", False) or not ui.get(f"notify_{key}", False):
            # switched off while the count was running: it stops here
            self.stop(key)
            return False
        n = rules.NOTIFY_BY_KEY[key]
        at = line_at(ui, n)
        answer = rules.answers(ui, n)
        sentence = n.says(at)
        # arriving is one or the other, never both
        if answer["kind"] == "banner":
            self.notifier.post(n, sentence)
        else:
            self.notifier.voice.say(sentence, self.notifier.language())
        said = state[1] + 1
        times = answer["times"]
        gap = answer["gap"]
        # nothing says when it is over: say it once and let it go
        if (times == 0 and n.until is None) or (times != 0 and said >= times):
            self.stop(key)
            return False
        state[1] = said
        state[0] = GLib.timeout_add(max(1, gap) * 1000, self._again, key)
        return False

    def _again(self, key):
        state = self.timers.get(key)
        if state is not None:
            state[0] = None
        ui = self.notifier.read_ui()
        snap = self.notifier.read_state()
        n = rules.NOTIFY_BY_KEY[key]
        at = line_at(ui, n)
        past = n.distance(snap, at) if snap is not None else None
        # the gap was long enough for the reading to come back (or the line
        # itself was moved, or the daemon went quiet): what is left of the
        # count is no longer true, so it ends here
        if (not ui.get(f"notify_{key}", False) or past is None or past < 0
                or (n.until is not None and n.until_done(snap))):
            self.stop(key)
            return False
        self._step(key)
        return False


class Notifier(Gio.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        GLib.set_application_name("chargecap")
        self.rules = rules.NotifyRules()
        self.voice = Voice()
        self.reminders = Reminders(self)
        self.sleeps = rules.Sleeps(rules.SLEEP_FILE)
        self.ui = {}
        self.ui_at = ()             # a value no mtime can equal: read once
        self.on = False
        self.enabled = None
        self.inhibit = None         # 禁止休眠 as last seen; None is unknown

    def do_activate(self):
        """No window to open: the timeout is the whole application."""

    def do_startup(self):
        Gio.Application.do_startup(self)
        self.hold()                 # no window: the timeout is the clock
        self.read_ui()
        GLib.timeout_add(TICK_MS, self.tick)

    # ---- what the phone says ---------------------------------------------
    def language(self):
        """The language the notifier speaks: the panel's, or the system's."""
        lang = self.read_ui().get("lang")
        if lang in ("zh", "en"):
            return lang
        names = GLib.get_language_names()
        return "zh" if any(n.startswith("zh") for n in names) else "en"

    def read_ui(self):
        """The panel's answers, re-read only when the file has changed."""
        try:
            at = os.stat(UI_FILE).st_mtime_ns
        except OSError:
            at = None
        if at != self.ui_at:
            self.ui_at = at
            self.ui = read_json(UI_FILE)
            rules.set_translator(translator(self.ui))
        return self.ui

    def read_state(self):
        """One snapshot of the readings, or None while the daemon is quiet."""
        s = read_json(STATE_FILE)
        try:
            if time.time() - float(s.get("updated") or 0) > STALE_S:
                return None
        except (TypeError, ValueError):
            return None
        if "capacity" not in s:
            return None
        return {
            "capacity": s.get("capacity"),
            "voltage_v": s.get("voltage_v"),
            "current_a": s.get("current_a"),
            "power_w": s.get("power_w"),
            "temp_c": s.get("temp_c"),
            "plugged": bool(s.get("plugged")),
            "charging": s.get("status") == "Charging",
        }

    def read_inhibit(self):
        """Is 禁止休眠 on?  The log's anchor, and the one flag it needs from the
        daemon -- the readings may be stale while this is still the truth."""
        return bool(read_json(STATE_FILE).get("inhibit_sleep"))

    # ---- one pass of the rules -------------------------------------------
    def tick(self):
        ui = self.read_ui()
        # the sleep record rides on the same pass: it is the one clock-keeping
        # this process does, and the panel only reads what is written down
        self.sleeps.tick()
        # ... and its count starts when 禁止休眠 is turned on, not when the
        # notifications are: the two are separate answers.  A service that
        # starts under whatever the switch already is has not seen a turn-on,
        # so nothing restarts (the record is still on disk).
        inhibit = self.read_inhibit()
        if self.inhibit is None:
            self.inhibit = inhibit
        elif inhibit != self.inhibit:
            if inhibit:
                self.sleeps.restart()
            self.inhibit = inhibit
        if not ui.get("notify", False):
            self.silence()
            return True

        if not self.on:
            # the master switch just came on: what the rules remember starts
            # from here, and the first readings are learned, not said
            self.rules.reset()
            self.on = True
            self.enabled = None

        snap = self.read_state()
        if snap is None:
            return True

        lines = [(n, line_at(ui, n)) for n in rules.NOTIFICATIONS
                 if ui.get(f"notify_{n.key}", n.on)]

        # a switch moved (or the master just came on, or this service just
        # started under a switch that was already on): the rules are armed
        # against the readings as they are and say nothing.  Turning something
        # on is not a crossing -- only a reading that crosses afterwards is.
        enabled = frozenset(n.key for n, _ in lines)
        if enabled != self.enabled:
            self.rules.reset()
            self.rules.seed(snap, lines)
            self.enabled = enabled
            return True

        for n in self.rules.sample(snap, lines):
            self.reminders.start(n.key)
        return True

    def post(self, n, sentence):
        note = Gio.Notification.new(sentence)
        note.set_priority(Gio.NotificationPriority.HIGH)
        # one id per notification: a second crossing replaces the first
        self.send_notification("chargecap-" + n.key, note)

    def silence(self):
        if self.on:
            self.rules.reset()
            self.on = False
            self.enabled = None
        self.reminders.stop_all()
        self.voice.stop()


def line_at(ui, n):
    """This notification's line, as the page stored it (or the table's own)."""
    try:
        at = int(ui.get(f"notify_{n.key}_at", n.default))
    except (TypeError, ValueError):
        at = n.default
    return max(n.low, min(n.high, at))


if __name__ == "__main__":
    sys.exit(Notifier().run(None))
