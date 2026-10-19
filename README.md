# chargecap

<img src="icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

**English** | [中文](README.zh.md)

Keep a plugged-in phone's battery inside a charge window -- and fall back to
plain power / battery monitoring where there is no root to change anything.
Supported:

- **Android 7.0 (API 24) and newer**: every phone, no root needed
- **postmarketOS**: mainline kernels whose charger exposes the interfaces it
  needs (root required -- see [Supported devices](#supported-devices))

The GTK app is a small **root daemon** plus an **unprivileged GTK4/libadwaita
app**; Android gets the same panel, chart and words in **Kotlin + Jetpack
Compose**.  Its Chinese name is **电电** (diàndiàn).

**Core features**
- limit how full the battery gets
- limit the USB input current
- status panel (voltage, power, current, the current's range and maximum,
  temperature, full / design capacity, health %, USB type, charging state,
  plugged state, charge %)
- overlaid chart: voltage / current / power / temperature / charge
- chart window: 15 s to 48 h
- recording interval: 0.01 s to 20 s
- inhibit sleep


<img src="docs/demo-en.gif" width="49%" alt="chargecap"> <img src="docs/demo-zh.gif" width="49%" alt="chargecap">

## Supported devices

### Android

**Every phone with Android 7.0 (API 24) or newer**, no model to pick and no root
needed.  Without root it only monitors (see [How it works](#how-it-works)): the
status panel, the chart and 禁止休眠 all work, while the charge-limit rows are
shown as they are but switched off, labelled with the reason.  What the platform
publishes, and how the current is measured, is in
[`android/README.md`](android/README.md).

### postmarketOS

By **kind**, not by model: mainline kernels whose charger exposes
`online` / `status` / `usb_type` / `current_max` and whose gauge reports charge /
voltage / current / temperature -- Qualcomm phones of that kind have been tested.
The control needs root: the GUI itself is unprivileged, and a root daemon is what
touches the charger.  Other platforms should work as long as those interfaces are
there; the nodes are found by the attributes they expose — see `TODO.md`.

## What it does

- **Hysteresis**: charging stops at the **upper** limit and resumes at the
  **lower** one; in between nothing changes.  Defaults 50 / 45 (%).
- **Master switch**: with it off, charging is left completely alone (a non-zero
  input current limit is still applied).
- **Inhibit sleep**: while this switch is on, a logind sleep block is held, so
  the **network stays up** (a suspended system would drop it).  It is not tied
  to the charger; switching it off only means chargecap stops blocking suspend
  -- whether the system then suspends is up to its own policy.
- **Plugged state**: `Power` is plugged / unplugged.
- **Charging state**: `Power` is charging / not charging.
- **Charge**: % of full.
- **USB type** (SDP / DCP / CDP / unknown, with an ⓘ explaining them).
- **Temperature**: °C.
- **Voltage**: V.
- **Power**: W.
- **Current**: mA — the live value, this session's **range** (`min | max`), the
  rated **max**, and the writable `limit`; `max` is the rated value it cannot
  exceed, and `0` means no limit.
- **Charge statistics**: charge % or the charged / discharged energy counts.
- **Chart**: one window showing voltage / current / power / temperature / charge,
  any of them overlaid.
- **Window**: 15 seconds to 48 hours; samples live in memory only, for as long as
  the panel is open.
- **Recording interval** (the `采样间隔` chip beside `Power`): how often the
  chart stores a sample, in **13 steps from 0.01 s to 20 s** — 0.01 / 0.03 /
  0.05 / 0.1 / 0.3 / **0.5** / 1 / 2 / 3 / 5 / 10 / 15 / 20 seconds, 0.5 s by
  default. It is independent of the panel's own 500 ms readout, and the buffer
  holds a fixed 48 hours' worth of 500 ms samples: a shorter interval buys
  detail and spends reach, so 0.01 s keeps about an hour and 20 s about eighty
  days. Both apps offer the same steps and remember the choice.
- **Dark by default**, with a background switch (dark / light / follow the
  system) in the header, just before the language one.
- **Follows the system language** (Chinese / English), switchable from the
  header.

## Install

### Android

Install the APK: take `chargecap-<version>-universal.apk` from
[Releases](https://github.com/fanzu8/chargecap/releases) and open it on the phone
(or `adb install -r` it).  Its only permission is `WAKE_LOCK`, and it opens in
dark mode following the system language.  To build it yourself, see
[`android/README.md`](android/README.md).

### postmarketOS

```sh
doas apk add py3-cairo     # also expects python3, GTK4 + libadwaita and systemd
git clone <repo> && cd chargecap
sudo ./install.sh          # must run from the repository directory
```

A fresh install changes nothing: limit off, sleep inhibition off, input current
limit 0.

```sh
sudo ./uninstall.sh        # removes everything and releases the charger
```

## How it works

The GUI needs no privileges of its own: a root daemon is what touches the
charger.

- **GUI → daemon**: the GUI hands over its request (limit switch, upper and lower
  bound, input current limit), the daemon applies it and reports the state back;
  the GUI refreshes every 500 ms, the daemon reads the gauge and the charger
  every 3 s.
- **Hysteresis**: charging stops at the upper limit and resumes at the lower one,
  and nothing changes in between -- so it does not start and stop around the
  threshold.
- **Inhibit sleep**: holds the system's sleep block (a partial wake lock on
  Android), which keeps the network up.
- **Chart**: samples are kept in memory for as long as the app is open; the
  recording interval and the window are both adjustable (see
  [What it does](#what-it-does)).
- **Android**: the system does not let an app touch the charger, and there is no
  daemon to ask, so the Android app only reads what the platform publishes and
  keeps the control half switched off.

## Development

Stdlib Python, no pip dependencies; the tests need neither a phone nor GTK (nor,
for the Android sources they also check, an Android SDK):

```sh
python3 -m unittest        # 148 tests
```

They drive the real control loop against a fake sysfs tree, check the GUI's
tables and layout invariants from its source, check the packaging, and hold the
Android port to the GTK app -- the same metrics, windows, tick formats and
translations on both sides (`tests/test_android.py`).  CI runs them on Python
3.10–3.13.

To look at the GTK front end without a phone, `tools/gtk-preview.py` points it
at a fake sysfs tree and a fake daemon state, so the whole panel draws with a
device's numbers; `--shot` renders it straight to a PNG.  It needs GTK4 +
libadwaita + PyGObject (`brew install gtk4 libadwaita pygobject3` on a Mac):

```sh
python3 tools/gtk-preview.py                  # the panel, plugged in
python3 tools/gtk-preview.py --off            # discharging, nothing plugged in
python3 tools/gtk-preview.py --scheme light --shot panel.png
```

## License

[General Pleasure League (GPL) 1.0](https://github.com/fanzu8/General-Pleasure-League)
