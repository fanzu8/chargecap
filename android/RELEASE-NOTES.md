# chargecap for Android

Keep a plugged-in phone's battery inside a charge window: the GTK app's
monitoring half, rewritten in Kotlin + Jetpack Compose.

The charging control itself needs root -- the GTK app gets it from its daemon --
so on a phone without root this app reads the battery, holds a wake lock, and
shows the controls it cannot use greyed out with the reason next to them.

## Install

Open the APK on the phone (allowing installs from this source), or

```sh
adb install -r chargecap-0.0.1-universal-debug.apk
```

- **Android 7.0 (API 24) or newer.**  The one file carries every ABI
  (arm64-v8a, armeabi-v7a, x86, x86_64).
- The only permission it asks for is `WAKE_LOCK`.
- Nothing to set up: it opens in dark mode, follows the system language, and
  starts monitoring.

## Signing

Releases are signed with `android/keystore/chargecap-release.p12`, which is **in
the repository** (with its passwords) on purpose: this app is only ever
sideloaded, and a key in the open is what lets a build made by CI and a build
made by anyone else install over each other.

```
SHA-256  16:79:B2:6C:02:47:F2:AA:99:FB:B0:F4:66:FF:AA:53:B5:4B:E0:52:16:4B:87:99:B7:AB:62:C2:6C:6E:54:CE
DN       CN=fanzu8
```

The build info repeats that fingerprint, so it is what to check before
installing an upgrade from anywhere but this repository -- a different key
cannot be installed over an existing copy (Android refuses it outright).

Debug builds (what a branch or PR run produces) are signed with the debug key of
the machine that built them instead, so they cannot be installed over a release
or over each other: uninstall first when switching between the two kinds.

## What it can and cannot do without root

See [`android/README.md`](https://github.com/fanzu8/chargecap/blob/main/android/README.md)
in the source tree for the full list, including what the platform does and does
not publish about the battery, and how the current is measured when the
vendor's own reading cannot be trusted.
