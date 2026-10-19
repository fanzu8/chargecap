# chargecap

<img src="icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

**English** | [中文](README.zh.md)

Keep a plugged-in phone's battery inside a charge window: a small **root
daemon** plus an **unprivileged GTK4/libadwaita app** for **postmarketOS**
(written on the **OnePlus 6 / 6T**), and the same panel, chart and words in a
**Kotlin + Jetpack Compose app for Android**.  Its Chinese name is **电电**
(diàndiàn).

**Core features**
- limit how full the battery gets
- limit the USB input current
- status panel (voltage, power, current, the current's range and maximum,
  temperature, full / design capacity, health %, USB type, charging state,
  plugged state, charge %)
- overlaid chart: voltage / current / power / temperature / charge, with a
  selectable time window
- inhibit sleep


<img src="docs/demo-en.gif" width="49%" alt="chargecap"> <img src="docs/demo-zh.gif" width="49%" alt="chargecap">

## Supported devices

| Device | Status |
|---|---|
| OnePlus 6 (enchilada) | tested — the device this was written on |
| OnePlus 6T (fajita) | expected to work unchanged: mainline gives both the same gauge (`ti,bq27411`) and charger (`pmi8998_charger`) in the shared `sdm845-oneplus-common.dtsi`, and the app finds those nodes by the attributes they expose |
| Huawei P20 Pro (CLT-AL00), Android 9 | tested — the Android app, no root needed |

Other mainline Qualcomm phones should work too as long as their charger exposes
`online` / `status` / `usb_type` / `current_max` — see `TODO.md`.

The Android app is not tied to those charger nodes: it reads what the platform
publishes, so it runs on **any phone with Android 7.0 (API 24) or newer** — see
[Android](#android).

## What it does

- **Hysteresis**: charging stops at the **upper** limit and resumes at the
  **lower** one; in between nothing changes. Defaults 50 / 45 (%).
- **Master switch**: with it off, charging is left completely alone
  (a non-zero input current limit is still applied).
- **USB input current limit**: `limit` is writable, `max` is the rated value it
  cannot exceed. `0` means no limit.
- **Inhibit sleep**: holds a logind sleep block for as long as this switch is
  on, so the **network stays up** (a suspended system would drop it). It is not
  tied to the charger; switching it off only means chargecap stops blocking
  suspend -- whether the system then suspends is up to the system's own policy.
- **Status panel**: `Power` (plugged / charging state / charge %), **USB type**
  (SDP / DCP / CDP / unknown, with an ⓘ explaining them), **temperature**,
  **voltage**, **power** and **current** — live value, this session's **range**
  (min | max), the rated **max** and the writable `limit` — plus
  **full / design capacity** and the resulting health percentage. Names and
  values take the colour of the matching curve; everything refreshes every
  500 ms.
- **Chart**: overlay any of voltage / current / power / temperature / charge as
  **metrics**, over a **window** from 15 seconds to 48 hours. Samples live in
  memory only, for as long as the app is open.
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

## How it works

The GUI needs no privileges: it writes a request file, the daemon applies it and
publishes a state file.

| | |
|---|---|
| gauge | `bq27411-0/{capacity,voltage_now,current_now,temp,constant_charge_current_max}` |
| charger | `pmi8998-charger/{online,usb_type}` |
| suspend / allow charging | write `pmi8998-charger/status` |
| USB input current limit | write `pmi8998-charger/current_max` |

The daemon polls every 3 s, the GUI every 500 ms.

## Android

`android/` holds the **monitoring half** of the same app, rewritten in Kotlin +
Jetpack Compose for Android phones, with the same panel, the same chart, the
same windows, colours and words.

Android denies apps the charger's sysfs (SELinux) and has no daemon to ask, so
the control half stays where the GTK app's root daemon is: the charge-limit rows
are shown but switched off, labelled with the reason.  **禁止休眠** does work --
it is a partial wake lock, Android's answer to `systemd-inhibit`.  See
[`android/README.md`](android/README.md) for what the platform does and does not
publish, and how the current is measured without `current_now` being trustworthy.

```sh
cd android && ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

CI builds the APK on every change and attaches it to a release when a version
tag is pushed, named `chargecap-<version>-universal.apk` (see
[`android/README.md`](android/README.md#releases)).

## Install

```sh
doas apk add py3-cairo     # also expects python3, GTK4 + libadwaita and systemd
git clone <repo> && cd chargecap
sudo ./install.sh          # must run from the repository directory
```

GUI → `/usr/local/bin/chargecap`, daemon → `/usr/local/lib/chargecap/`, service →
`/etc/systemd/system/chargecap.service`, app entry → `/usr/share/applications/`.
A fresh install changes nothing: limit off, sleep inhibition off, input current
limit 0.

```sh
sudo ./uninstall.sh        # removes everything and releases the charger
```

Android is an APK rather than a build from source: see [Android](#android).

## Development

Stdlib Python, no pip dependencies; the tests need neither a phone nor GTK (nor,
for the Android sources they also check, an Android SDK):

```sh
python3 -m unittest        # 124 tests
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

The gauge and charger nodes are found by the attributes they expose (the
OnePlus 6's names are the fallback), so the same build should work on the
**6T** and other mainline Qualcomm phones; porting notes are in `TODO.md`.
