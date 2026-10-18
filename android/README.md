# chargecap for Android

<img src="../icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

**English** · the GTK app's *monitoring* half, as a Kotlin + Jetpack Compose app.

The GTK app controls charging by asking a **root daemon** to write the charger's
`/sys/class/power_supply/…` nodes.  On Android those nodes are denied to apps by
SELinux, and there is no daemon to ask, so an unrooted phone can only be *read*.
This port keeps everything that can be read, in the same layout, with the same
charts and the same words as the GTK app -- and shows the controls it cannot use,
greyed out, with the reason next to them.

## What it does

- **Status panel**: charge %, plugged / charging state, charger type (AC / USB /
  wireless / dock), temperature, voltage, power, current with this session's
  range, and the charge the counter reports against the design capacity plus the
  platform's health state.  Refreshes twice a second.
- **Chart**: overlay any of voltage / current / power / temperature / charge as
  metrics, over a window from 30 seconds to 48 hours, with the GTK app's colours,
  axis sides, tick formats and time labels.
- **Inhibit sleep** (禁止休眠): the Android equivalent of the daemon's
  `systemd-inhibit` -- a partial wake lock, held while the switch is on, so the
  device does not suspend and the network stays up.  This one *does* work here.
- **Follows the system language** (Chinese / English), switchable from the
  header; the metrics, window and language are remembered.

The sample history lives in memory only and holds 48 hours at 2 Hz, exactly like
the GTK app's arrays.  Sampling runs in the process rather than in the UI, so the
chart keeps filling while the screen is off (until Android reclaims the process).

## What it cannot do

| | |
|---|---|
| **Limit charging** (上限 / 下限 / 启动) | needs root to write the charger's sysfs; the rows are the GTK app's own, shown with the daemon's defaults and switched off |
| **USB input current limit** (限制) | same: no writable node without root, so the box stays empty |
| **Rated maximum current** (最大) | Android does not publish it |
| **Health percentage** | Android gives the health *state*, never `charge_full`, so the percentage cannot be computed |

The one place this port has to be clever is the **current**: Android's
`BATTERY_PROPERTY_CURRENT_NOW` promises microamps, but some phones answer in
milliamps (the Huawei P20 Pro this was tested on reads a 1.6 A charge as 2 mA),
and the charge counter is quantised to whole mAh, which turns a short window into
a staircase.  So the counter's *slope* -- the one signal whose scale is always
the API's own -- decides which unit the HAL is answering in, and the HAL's own
fine-grained reading is what the panel and the chart show.

## Build and install

```sh
cd android
./gradlew assembleDebug                      # needs a JDK 17+ and the Android SDK
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The app is `org.chargecap.android`, needs only `WAKE_LOCK`, and runs on Android
7.0 (API 24) and up; it was written and tested on Android 9 (EMUI 9.1).

Built with the Android Gradle plugin 9.0.1 (which compiles Kotlin itself -- the
old `kotlin-android` plugin is not applied), Kotlin 2.3.20 and Compose BOM
2026.03.01.

## Development

The Kotlin sources are held to the GTK app by `tests/test_android.py`, which
reads them the same way `tests/test_gui.py` reads the GTK source: the metric
table, the window list, the type scale, the tick formats, the colours and every
translated string have to match, and the two apps' strings have to keep saying
the same thing in the same words.

```sh
cd .. && python3 -m unittest        # the whole suite, no phone and no SDK needed
```

## Licence

[General Pleasure League (GPL) 1.0](https://github.com/fanzu8/General-Pleasure-League)
