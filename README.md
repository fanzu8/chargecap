# chargecap

<img src="icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

**English** | [中文](README.zh.md)

Notifications -- charging complete, low battery, temperature and the rest --
and keeping a plugged-in phone's battery inside a set window; without root it
falls back to plain power / battery monitoring.  Supported:

- **Android 7.0 (API 24) and newer**: every phone, no root needed
- **postmarketOS**: mainline kernels whose charger exposes the interfaces it
  needs (root required -- see [Supported devices](#supported-devices))

The GTK app is a small **root daemon** plus an **unprivileged GTK4/libadwaita
app**; Android gets the same panel, chart and words in **Kotlin + Jetpack
Compose**.  Its Chinese name is **电电** (diàndiàn).

**Core features**
- notifications by banner or voice (an elderly phone's charge reminder)
- limit how full the battery gets
- limit the USB input current
- status panel (voltage, power, current, the current's range and maximum,
  temperature, full / design capacity, health %, USB type, charging state,
  plugged state, charge %)
- overlaid chart: voltage / current / power / temperature / charge
- chart window: 15 s to 48 h
- recording interval: 0.01 s to 20 s
- judge a cable / charger / power bank (how far the voltage sags, how much
  power it will hold out) and what the USB port itself offers
- inhibit sleep
- **13 notifications** in seven groups -- a banner or a voice, a count and an
  interval each; the rules keep running with the panel closed
- **语音通知**: 充电完成 / 电量过低 / 温度过高 and the rest are spoken out loud
  as well as shown, so they are heard without looking at the screen -- made for
  elderly and low-vision users, and handy with the phone in a pocket
- **休眠记录**: whether the 禁止休眠 promise held


<img src="docs/demo-en.gif" width="49%" alt="chargecap"> <img src="docs/demo-zh.gif" width="49%" alt="chargecap">

## Supported devices

### Android

**Every phone with Android 7.0 (API 24) or newer**, no model to pick and no root
needed.  Without root it only monitors: the
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

- **通知**: many thresholds of your own, a reminder when each is crossed --
  banner or voice, and the voice takes a repeat count.  It doubles as an
  elderly phone that speaks the charge state out loud.  On Android, 通知开关
  also starts a low-priority foreground service, with a small ongoing
  后台监控 line in the shade: that is what keeps the readings coming while the
  app is off screen.  Autostart and battery whitelists alone do not do it --
  Android freezes ordinary background processes.
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
- **Cable / charger / power bank**: with the `current` known, the `voltage` says
  how much the path loses -- a thin or tired cable sags visibly; a `current`
  that stops climbing (and the `power` that stops with it) is the charger's or
  the power bank's ceiling; the `USB type` (SDP / DCP / CDP) is what the port
  itself offers.
- **Charge statistics**: charge % or the charged / discharged energy counts.
- **Chart**: one window showing voltage / current / power / temperature / charge,
  any of them overlaid.
- **Window**: 15 seconds to 48 hours; samples live in memory only, for as long as
  the panel is open.
- **Recording interval** (the `采样间隔` chip beside `Power`): how often the
  chart stores a sample, in **13 steps from 0.01 s to 20 s** — 0.01 / 0.03 /
  0.05 / 0.1 / 0.3 / **0.5** / 1 / 2 / 3 / 5 / 10 / 15 / 20 seconds, 0.5 s by
  default. A shorter interval shows more detail over a shorter span; both apps
  offer the same steps and remember the choice.
- **Dark by default**, with a background switch (dark / light / follow the
  system) in the header, just before the language one.
- **Follows the system language** (Chinese / English), switchable from the
  header.
- **休眠记录** (高级, under 禁止休眠): the record of the system's own sleeps,
  counted off the clocks -- boottime against monotonic -- and so a check on
  whether the promise held.  Not a notification (a sleeping system delivers
  nothing) and nothing to do with 通知开关: the count is the last 禁止休眠
  turn-on's, a reboot clears it, and a tap shows the sleeps it kept.

## Install

### Android

Install the APK: take `chargecap-<version>-universal.apk` from
[Releases](https://github.com/fanzu8/chargecap/releases) and open it on the phone
(or `adb install -r` it).  Its permissions are `WAKE_LOCK`, the notification one Android 13 asks for, and
the foreground-service and boot-completed pair that keep the rules alive with
the screen off; it opens in dark mode following the system language.
To build it yourself, see [`android/README.md`](android/README.md).

### postmarketOS

```sh
doas apk add py3-cairo     # also expects python3, GTK4 + libadwaita and systemd
doas apk add speech-dispatcher espeak-ng   # 语音; the app falls back quietly without it
git clone <repo> && cd chargecap
sudo ./install.sh          # must run from the repository directory
```

A fresh install changes nothing: limit off, sleep inhibition off, input current
limit 0.

```sh
sudo ./uninstall.sh        # removes everything and releases the charger
```

## Development

Stdlib Python, no pip dependencies; the tests need neither a phone nor GTK (nor,
for the Android sources they also check, an Android SDK):

```sh
python3 -m unittest        # 269 tests
```

They need neither a phone nor GTK (nor an Android SDK for the sources they
check), and CI runs them on Python 3.10–3.13.

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
