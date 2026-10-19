# chargecap for Android

<img src="../icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

The GTK app's **monitoring half**, in Kotlin + Jetpack Compose: same panel, same
chart, same words.  Charging control needs a **root daemon** writing the
charger's nodes, which SELinux denies to apps, so an unrooted phone can only be
read.

## What it cannot do

| | |
|---|---|
| **Limit charging** (上限 / 下限 / 启动) | needs root: the rows are the GTK app's own, shown switched off |
| **USB input current limit** (限制) | no writable node without root, so the box is empty |
| **Rated maximum current** (最大) | Android does not publish it |
| **Health percentage** | Android reports a health *state*, never `charge_full` |

禁止休眠 works -- a partial wake lock, where the daemon holds a
`systemd-inhibit` -- as does everything else that can be read, the chart
included: samples in memory only (48 hours at 2 Hz), taken off the UI thread, so
it keeps filling while the screen is off.

Where the platforms differ, the ⓘ next to a value says how: the charger type is
the port (AC / USB / wireless / dock), 健康度 is the state the system reports,
and the mAh row's first number is the gauge's coulomb counter -- charge that has
flowed through it, *not* what is left, so `54/4000` is not 1.35% (it resets when
the battery reaches full).

## The current

`BATTERY_PROPERTY_CURRENT_NOW` is documented in µA but answered in mA on some
phones (the P20 Pro reports a 0.3 A discharge as `-297`), and nothing in the
value says which -- so the coulomb counter's slope, µAh on every device, picks
the unit, the HAL supplies the current and its sign (the counter's own sign is
worthless), and the answer is remembered.  A 1 mAh step, i.e. a 500 A spike, is a
gauge reset rather than a reading.

## Build and install

```sh
cd android
./gradlew assembleDebug                      # needs a JDK 17+ and the Android SDK
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

`org.chargecap.android`, Android 7.0 (API 24) and up, only permission
`WAKE_LOCK`; tested on Android 9 (EMUI 9.1).  AGP 9.0.1 (which compiles Kotlin
itself), Kotlin 2.3.20, Compose BOM 2026.03.01.  `tests/test_android.py` holds it
to the GTK app -- metric table, windows, type scale, tick formats, colours and
every translated string -- and `cd .. && python3 -m unittest` needs no phone and
no SDK.

## Releases

CI builds on every change to `android/`, and on a `v*` tag attaches the result to
a release; the tag has to match the version the build declares (`v0.0.1` needs
`appVersion = "0.0.1"`).  One file per release,
`chargecap-<version>-<abi>-<variant>.apk`:

| | |
|---|---|
| `chargecap-0.0.1-universal.apk` | the release: signed with `keystore/`, minified, not debuggable |
| `chargecap-0.0.1-universal-debug.apk` | a branch or PR build: attached to the run, never released |
| `SHA256SUMS` | the APK's hash, for `sha256sum -c` |
| `chargecap-0.0.1-build-info.txt` | commit, build time, ABIs, toolchain, signer |

`<version>` is the tag without its `v`, `<abi>` is `universal` (all four ABIs in
one file: splitting them would save 36 KB of a 3.4 MB download).  The `keystore/`
key is what lets a local and a CI build install over each other, so it must never
be rotated; CI refuses a release it did not sign.

## Licence

[General Pleasure League (GPL) 1.0](https://github.com/fanzu8/General-Pleasure-League)
