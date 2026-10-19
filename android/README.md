# chargecap for Android

<img src="../icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

The GTK app's **monitoring half**, in Kotlin + Jetpack Compose: same panel, same
chart, same words.  The GTK app controls charging by having a **root daemon**
write the charger's nodes; SELinux denies those to apps and Android has no daemon
to ask, so an unrooted phone can only be read.

## What it cannot do

| | |
|---|---|
| **Limit charging** (上限 / 下限 / 启动) | needs root to write the charger's sysfs; the rows are the GTK app's own, shown with the daemon's defaults and switched off |
| **USB input current limit** (限制) | same: no writable node without root, so the box stays empty |
| **Rated maximum current** (最大) | Android does not publish it |
| **Health percentage** | Android gives the health *state*, never `charge_full`, so the percentage cannot be computed |

禁止休眠 *does* work: it is a partial wake lock where the daemon holds a
`systemd-inhibit`.  Everything else that can be read is read, including the
chart -- samples in memory only, 48 hours at 2 Hz, taken off the UI thread so it
keeps filling while the screen is off (until Android reclaims the process).

The notes behind the ⓘs are the app's own wherever the platforms differ: the
charger type is the port (AC / USB / wireless / dock) rather than
SDP / DCP / CDP, and 健康度 is the state the system reports (良好 / 过热 / ...)
rather than the GTK app's wear percentage (`charge_full / charge_full_design`).

The mAh row is the one place the numbers need that note: the first of the two is
the gauge's coulomb counter -- charge that has flowed through it, *not* what is
left.  On the P20 Pro it resets when the battery reaches full (1,546,000 µAh
became 4,000 in one step) and its absolute value never matched the percentage
anyway, so `54/4000` must not be read as 1.35%.  Its *rate* is trustworthy, and
that is what calibrates the current.

## The current

Android promises `BATTERY_PROPERTY_CURRENT_NOW` in microamps but answers in
milliamps on some phones (the P20 Pro this was tested on reports a 0.3 A
discharge as `-297`), and the value itself does not say which.  The charge
counter's slope does: its deltas are µAh on every device, so its *magnitude* says
which scale the HAL is using -- while its *sign* is worthless (this phone's
counter only ever counts up, charging or discharging).  So the HAL supplies the
current and its sign, the counter supplies the unit, and the answer is
remembered, because the counter stops moving once the battery is full.  Its 1 mAh
steps also mean a reset looks like a 500 A spike, so an impossible slope is
treated as a gauge reset rather than believed.

## Build and install

```sh
cd android
./gradlew assembleDebug                      # needs a JDK 17+ and the Android SDK
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

`org.chargecap.android`, Android 7.0 (API 24) and up, its only permission
`WAKE_LOCK`; written and tested on Android 9 (EMUI 9.1).  Built with AGP 9.0.1
(which compiles Kotlin itself -- `kotlin-android` is not applied), Kotlin 2.3.20
and Compose BOM 2026.03.01.

## Releases

CI (`.github/workflows/android.yml`) builds the APK on every change to it, and on
a `v*` tag attaches the result to a release.  A tag has to match the version the
build declares (`v0.0.1` needs `appVersion = "0.0.1"`), so a download can always
be traced back to its commit.

One file per release, `chargecap-<version>-<abi>-<variant>.apk`: `<version>` is
the tag without its `v`, `<abi>` is `universal` -- all four in one file, since
splitting them would save 36 KB of a 3.4 MB download -- and `<variant>` is
dropped for the release and `debug` when it really is one.

| | |
|---|---|
| `chargecap-0.0.1-universal.apk` | the release: signed with the key in `keystore/`, minified, not debuggable |
| `chargecap-0.0.1-universal-debug.apk` | what a branch or PR build produces (attached to the run, never released) |
| `SHA256SUMS` | the APK's hash, for `sha256sum -c` |
| `chargecap-0.0.1-build-info.txt` | tag, commit, build time, ABIs, toolchain, and **who signed it** |

The release is signed with the key committed in `keystore/`, which is what lets a
build made on any machine and a build made by CI install over each other; that
key must never be rotated.  The build info repeats the signer's fingerprint, and
CI fails the build if the APK it produced was signed by anything else.

## Development

`tests/test_android.py` holds the Kotlin sources to the GTK app the way
`tests/test_gui.py` holds the GTK source: the metric table, the window list, the
type scale, the tick formats, the colours and every translated string have to
match, and the two apps have to keep saying the same thing in the same words.

```sh
cd .. && python3 -m unittest        # the whole suite, no phone and no SDK needed
```

## Licence

[General Pleasure League (GPL) 1.0](https://github.com/fanzu8/General-Pleasure-League)
