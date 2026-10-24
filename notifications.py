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

"""The notifications, in one place, for both halves of the app.

The panel draws the page and writes the answers; the notifier (a systemd user
service) reads them and keeps watching while the panel is closed.  What they
share is here: the table, the one comparison each notification makes, and the
memory of what has already been said.

The words are kept in Chinese, the language the source is written in, and
translated where they are used -- set_translator() -- so the same table can be
read in either language by either process.
"""
import json
import os
import shutil
import time

# how many times a notification says it -- a banner and a voice alike -- and 0
# for an endless count (see Notify.until)
TIMES = ((1, "1次"), (2, "2次"), (3, "3次"), (5, "5次"), (10, "10次"))

# how long it waits between those repeats; the labels are units, not words, so
# they are the same in both languages and are never translated
GAPS = ((1, "1s"), (2, "2s"), (3, "3s"), (5, "5s"), (10, "10s"), (15, "15s"),
        (20, "20s"), (30, "30s"), (60, "1min"), (120, "2min"), (300, "5min"))
DEFAULT_GAP = 2

# how it arrives: a banner or a voice, one or the other, never both
KINDS = (("banner", "横幅"), ("voice", "语音"))

# How the phone says a sentence out loud.  The voice picked in the tuning
# window: espeak-ng's female f3 Mandarin, direct to its own audio output.
# spd-say stays as the fallback for a machine without espeak-ng.
VOICE_ENGINES = ("espeak-ng", "espeak", "spd-say")
VOICE_VOICE = "cmn+f3"
VOICE_RATE = 200
VOICE_PITCH = 99
VOICE_AMP = 130
VOICE_GAP = 0


def _find_voice():
    for name in VOICE_ENGINES:
        path = shutil.which(name)
        if path:
            return path
    return None


VOICE_CMD = _find_voice()


def voice_command(text, lang=None):
    """The command that says [text], or None when there is no engine.

    A Chinese sentence is spoken by espeak-ng directly; English takes the
    default voice.  spd-say, when it is all the phone has, asks for the same
    female variant and leaves the audio path to the dispatcher.
    """
    if not VOICE_CMD:
        return None
    zh = (lang or "").startswith("zh")
    name = os.path.basename(VOICE_CMD)
    if name in ("espeak", "espeak-ng"):
        if zh:
            return [VOICE_CMD, "-v", VOICE_VOICE,
                    "-s", str(VOICE_RATE), "-p", str(VOICE_PITCH),
                    "-a", str(VOICE_AMP), "-g", str(VOICE_GAP), text]
        return [VOICE_CMD, text]
    if name == "spd-say":
        base = [VOICE_CMD, "-N", "chargecap", "-n", "main"]
        if zh:
            return base + ["-y", "Chinese (Mandarin, latin as English)+f3",
                           "-r", "20", "-p", "40", "-w", text]
        return base + ["-w", text]
    return [VOICE_CMD, text]


def _plain(text):
    return text


_translate = _plain


def set_translator(func):
    """How to say a word: the app's _(), once it knows its language."""
    global _translate
    _translate = func


def spoken_kinds():
    """The ways of arriving this phone can actually deliver."""
    return [(key, _translate(text)) for key, text in KINDS
            if key == "banner" or VOICE_CMD]


def gap_label(secs):
    """The interval's own word: a unit, the same in both languages."""
    for value, label in GAPS:
        if value == secs:
            return label
    return GAPS[0][1]


def answers(ui, n):
    """One notification's three answers, as the page stored them.

    Read and checked here rather than in each reader: the panel draws them,
    the notifier repeats by them, and a value the table no longer offers -- an
    unknown kind, a count this notification does not carry, a gap outside
    GAPS, a hand-edited number -- falls back to the fresh answer.  So the two
    halves disagree about nothing, not even about a ui.json someone edited.
    """
    kind = ui.get(f"notify_{n.key}_kind")
    times = ui.get(f"notify_{n.key}_times")
    gap = ui.get(f"notify_{n.key}_gap")
    try:
        times = int(times)
    except (TypeError, ValueError):
        times = 1
    try:
        gap = int(gap)
    except (TypeError, ValueError):
        gap = DEFAULT_GAP
    # an unknown kind is the fresh answer (语音); a kind this phone cannot
    # deliver falls back to one it can -- 语音 on a phone without an engine
    # would be a notification nobody ever hears, so it becomes 横幅
    kinds = [k for k, _t in spoken_kinds()]
    kind = kind if kind in [k for k, _t in KINDS] else "voice"
    if kind not in kinds:
        kind = "banner" if "banner" in kinds else kinds[0]
    return {
        "kind": kind,
        "times": times if times in [c for c, _t in n.counts()] else 1,
        "gap": gap if gap in [g for g, _l in GAPS] else DEFAULT_GAP,
    }


# the record of the system's own sleeps, written by the notifier (the half
# that is up when the sleeps happen) and read by the panel's row under
# 禁止休眠
SLEEP_FILE = os.path.expanduser("~/.config/chargecap/sleep.json")


def boot_id():
    """This boot's id: a different one means the phone restarted."""
    try:
        with open("/proc/sys/kernel/random/boot_id") as f:
            return f.read().strip()
    except OSError:
        return ""


def load_sleeps(path=SLEEP_FILE):
    """The record as it is written down, cleared when it is not this boot's.

    Returns {"anchor": epoch-or-0, "count": int, "naps": [(at, secs)]} with
    the naps newest first.
    """
    try:
        with open(path) as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    stale = d.get("boot") != boot_id()
    anchor = 0 if stale else int(d.get("anchor") or 0)
    count = 0 if stale else int(d.get("count") or 0)
    naps = [] if stale else [(float(at), int(secs))
                             for at, secs in d.get("naps", [])]
    return {"anchor": anchor, "count": count, "naps": naps}


class Sleeps:
    """The system's own sleeps, counted off two clocks.

    CLOCK_BOOTTIME runs while the system is suspended and CLOCK_MONOTONIC
    does not: the first's excess over the second, across one pass, is how
    long the system slept inside it -- however fast or slow the passes come.

    The count is the last 禁止休眠 turn-on's ([restart] is that moment) and
    has nothing to do with the notifications: the question it answers is
    whether that switch held.  A stretch of a minute or more is one sleep,
    and awake time under two minutes belongs to the stretch it interrupted --
    a night of doze punctuated by alarm wakeups is one event, not a hundred.
    A reboot clears the record: what it answers for is this boot's 禁止休眠,
    not the phone's lifetime.
    """

    MIN_SECS = 60       # a stretch shorter than this is a blink, not a sleep
    MERGE_SECS = 120    # awake time shorter than this joins its stretch
    KEPT = 10           # the sleeps the history card can still list

    def __init__(self, path=SLEEP_FILE):
        self.path = path
        self.anchor = 0
        self.count = 0
        self.naps = []                  # newest first, at most KEPT of them
        self._last_wall = 0.0
        self._last_mono = 0.0
        self._last_boottime = 0.0
        self._stretch_start = 0.0
        self._stretch_last = 0.0
        self._stretch_slept = 0.0
        self._last_save = 0.0
        self._load()

    def _load(self):
        d = load_sleeps(self.path)
        self.anchor = d["anchor"]
        self.count = d["count"]
        self.naps = d["naps"]

    def restart(self):
        """禁止休眠 is on: the record starts over from this moment."""
        self.anchor = time.time()
        self.count = 0
        self.naps = []
        self._stretch_start = self._stretch_last = 0.0
        self._stretch_slept = 0.0
        self.save()

    def tick(self):
        """One pass of the clocks; call it as often as the readings are read."""
        wall = time.time()
        mono = time.clock_gettime(time.CLOCK_MONOTONIC)
        boottime = time.clock_gettime(time.CLOCK_BOOTTIME)
        if self._last_wall:
            slept = (boottime - self._last_boottime) - (mono - self._last_mono)
            if slept > 0:
                # a stretch begins with the pass before the first sleeping
                # one: that is when the system was last seen awake
                if not self._stretch_start:
                    self._stretch_start = self._last_wall
                self._stretch_slept += slept
                self._stretch_last = wall
            elif (self._stretch_start
                    and wall - self._stretch_last > self.MERGE_SECS):
                self._close()
        self._last_wall, self._last_mono, self._last_boottime = wall, mono, boottime
        # the clocks are cheap, the write is not: every ten seconds is often
        # enough for a record whose smallest event is a minute long
        if wall - self._last_save > 10:
            self._last_save = wall
            self.save()

    def _close(self):
        """The stretch is over: long enough counts, short enough never happened."""
        if self.anchor and self._stretch_slept >= self.MIN_SECS:
            self.count += 1
            self.naps = ([(self._stretch_last, int(self._stretch_slept))]
                         + self.naps)[:self.KEPT]
            self.save()
        self._stretch_start = self._stretch_last = 0.0
        self._stretch_slept = 0.0

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump({"boot": boot_id(), "anchor": self.anchor,
                           "count": self.count,
                           "naps": [[at, secs] for at, secs in self.naps]}, f)
        except OSError:
            pass


# Every notification is one comparison, so the table holds the comparison too:
# how far past its line a reading is.  None means the phone does not publish
# that reading at all -- far away, rather than a false alarm.


def _past_done(s, at):
    """充电完成: plugged in and there.  An unplugged phone is never done, and
    unplugging is what lets it be said again on the next charge."""
    cap = s.get("capacity")
    if cap is None or not s.get("plugged"):
        return None
    return cap - at


def _past_low(s, at):
    cap = s.get("capacity")
    return None if cap is None else at - cap


def _past_hot(s, at):
    t = s.get("temp_c")
    return None if t is None else t - at


def _past_cold(s, at):
    t = s.get("temp_c")
    return None if t is None else at - t


def _past_vhigh(s, at):
    v = s.get("voltage_v")
    return None if v is None else v * 1000.0 - at


def _past_vlow(s, at):
    v = s.get("voltage_v")
    return None if v is None else at - v * 1000.0


def _past_iin(s, at):
    """充电电流过高: the positive half of the signed current, so only a phone
    on the charger can cross it."""
    i = s.get("current_a")
    return None if i is None else i * 1000.0 - at


def _past_drain(s, at):
    """放电电流过高: the size of a discharge -- the reading is signed, positive
    while charging, so a phone on the charger goes quiet."""
    i = s.get("current_a")
    return None if i is None else -i * 1000.0 - at


def _past_power(s, at):
    """功率过高: the size of the power, whichever direction it flows."""
    p = s.get("power_w")
    return None if p is None else abs(p) - at


class Notify:
    """One notification: its words, its range and the line it watches."""

    def __init__(self, key, title, label, unit, default, step, low, high,
                 distance, above=None, until=None, numbered=True, short=None):
        self.key = key
        self._title = title         # in the source's language, translated below
        self._short = short         # the row's shorter word, when there is one
        self._label = label         # 达 / 低于 / 高于: how its number reads
        self.unit = unit            # the unit of that number
        self.default = default
        self.step = step            # one press of its stepper
        self.low = low
        self.high = high
        self.distance = distance
        self.above = above          # a line this one has to stay above, by key
        self._until = until         # (words, the reading that ends it) or None
        # the plug and the charging state are on or off, not readings: they
        # have no number to set, and their sentence is the name alone
        self.numbered = numbered

    @property
    def on(self):
        """A fresh install arms nothing: the master switch decides whether
        anything fires at all, and each notification is its owner's choice."""
        return False

    def title(self):
        return _translate(self._title)

    def short(self):
        """The row's own word: 充电完成 stays 充电完成, but 电源连接 is just
        连接 under the 电源 heading.  The sentence it says keeps the full title."""
        if self._short is None:
            return self.title()
        return _translate(self._short)

    def label(self):
        return _translate(self._label)

    def until_label(self):
        return _translate(self._until[0]) if self._until else None

    def until_done(self, snap):
        """Is the reminder's work finished?  (The cable came out, the plug went
        in.)  A notification without an endless count never says yes."""
        return bool(self._until[1](snap)) if self._until else False

    def value(self, reading):
        """The number as the row shows it: "100%" or "45 °C"."""
        return f"{reading}{self.unit}"

    def says(self, reading):
        """The sentence the banner and the voice both use: 充电完成 100% -- or,
        for a state, the state itself."""
        if not self.numbered:
            return self.title()
        return f"{self.title()} {self.value(reading)}"

    def counts(self):
        """The counts on offer: the plain ones, then -- where waiting means
        something -- the one that only stops when the reading says so."""
        out = [(count, _translate(text)) for count, text in TIMES]
        if self._until is not None:
            out.append((0, _translate(self._until[0])))
        return out

    def count_label(self, count):
        for value, label in self.counts():
            if value == count:
                return label
        return TIMES[0][1]


NOTIFICATIONS = (
    # 充电完成 has to stay above 电量过低: two lines that cross are two
    # notifications arguing with each other, so each one's range stops at the
    # other (see keep_apart)
    Notify("done", "充电完成", "达", "%", 100, 1, 0, 100, _past_done,
           above="low",
           until=("直到电源断开", lambda s: not s.get("plugged"))),
    Notify("low", "电量过低", "低于", "%", 10, 1, 0, 100, _past_low,
           until=("直到开始充电", lambda s: bool(s.get("charging")))),
    # the plug and the charging state: on or off, so the distance is +1 and -1
    # and the notification fires on the change rather than on a number
    Notify("plugged", "电源连接", "达", "", 0, 1, 0, 0,
           lambda s, at: 1.0 if s.get("plugged") else -1.0, numbered=False,
           short="连接"),
    Notify("unplugged", "电源断开", "达", "", 0, 1, 0, 0,
           lambda s, at: -1.0 if s.get("plugged") else 1.0, numbered=False,
           short="断开"),
    Notify("charging", "充电中", "达", "", 0, 1, 0, 0,
           lambda s, at: 1.0 if s.get("charging") else -1.0, numbered=False),
    Notify("idle", "未充电", "达", "", 0, 1, 0, 0,
           lambda s, at: -1.0 if s.get("charging") else 1.0, numbered=False),
    Notify("hot", "温度过高", "高于", " °C", 45, 1, -60, 100, _past_hot,
           short="过高"),
    Notify("cold", "温度过低", "低于", " °C", -20, 1, -60, 100, _past_cold,
           short="过低"),
    # the gauge reads volts; the row speaks millivolts, so every notification
    # about it is a whole number like the others
    Notify("vhigh", "电压过高", "高于", " mV", 4300, 100, 3000, 5000, _past_vhigh,
           short="过高"),
    Notify("vlow", "电压过低", "低于", " mV", 3400, 100, 2500, 4500, _past_vlow,
           short="过低"),
    Notify("iin", "充电电流过高", "高于", " mA", 3000, 100, 0, 10000, _past_iin,
           short="充电过高"),
    Notify("drain", "放电电流过高", "高于", " mA", 1000, 100, 0, 5000, _past_drain,
           short="放电过高"),
    Notify("power", "功率过高", "高于", " W", 20, 1, 0, 100, _past_power,
           short="过高"),
)
NOTIFY_BY_KEY = {n.key: n for n in NOTIFICATIONS}

class Group:
    """One group of the 通知 page: its word and its notifications' keys.

    The title is a word of the table's, translated where it is read like
    every other one.
    """

    def __init__(self, title, keys):
        self._title = title
        self.keys = keys

    def title(self):
        return _translate(self._title)


# the groups the 通知 page reads in, in the order it shows them: the battery's
# own charge, the plug and the charging state, then one group per kind of
# reading -- a temperature and a voltage are not the same subject
GROUPS = (
    Group("基础功能", ("done", "low")),
    Group("电源", ("plugged", "unplugged")),
    Group("充电", ("charging", "idle")),
    Group("温度", ("hot", "cold")),
    Group("电压", ("vhigh", "vlow")),
    Group("电流", ("iin", "drain")),
    Group("功率", ("power",)),
)


def keep_apart(n, at, lines):
    """Where a number may land: inside the notification's own range, and clear
    of any line it has to stay above -- 充电完成 over 电量过低, since two lines
    that cross are two notifications arguing with each other.

    [lines] is the number each notification holds at the moment, by key; the
    answer is the number this one may take instead.  Typed numbers and stepped
    ones both come through here, so the check lives in one place.
    """
    below = NOTIFY_BY_KEY.get(n.above) if n.above else None
    floor = lines[below.key] + 1 if below else n.low
    above = next((x for x in NOTIFICATIONS if x.above == n.key), None)
    ceiling = lines[above.key] - 1 if above else n.high
    lo = max(n.low, floor)
    hi = min(n.high, ceiling)
    return max(lo, min(hi, at)) if lo <= hi else hi


class NotifyRules:
    """Which notifications have already been said, and which just crossed.

    One comparison a pass, in the notification's own unit: it fires on the way
    in and stays quiet until the reading comes back clear -- past the line by
    more than the notification's own step -- so a value resting on the line says
    its piece once instead of every pass.
    """

    def __init__(self):
        self.spoken = set()

    def reset(self):
        """A switch moved: what the last set of rules remembered is not this
        set's business."""
        self.spoken.clear()

    def seed(self, snap, rules):
        """Arm against what is already true, without saying it.

        Turning 通知开关 (or one notification) on -- or opening the app under a
        switch that was already on -- is not a crossing.  What is past its line
        at that moment is taken as already said, so only a reading that crosses
        afterwards is news.
        """
        for n, at in rules:
            past = n.distance(snap, at)
            if past is not None and past >= 0:
                self.spoken.add(n.key)

    def sample(self, snap, rules):
        out = []
        for n, at in rules:
            past = n.distance(snap, at)
            if past is None:
                continue
            if past >= 0:
                if n.key not in self.spoken:
                    self.spoken.add(n.key)
                    out.append(n)
            elif past <= -n.step:
                self.spoken.discard(n.key)
        return out
