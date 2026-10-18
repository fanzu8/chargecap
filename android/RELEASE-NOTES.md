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

These APKs are signed with the **debug key of the machine that built them** --
no keystore is kept in the repository, so a release built by CI and a build made
by hand on someone's laptop carry *different* signatures.  Android refuses to
install one over the other: uninstall first when switching between them (and
expect that whenever the key changes, which is also why the build info lists the
signer's fingerprint -- it is what tells two copies apart).

## What it can and cannot do without root

See [`android/README.md`](https://github.com/fanzu8/chargecap/blob/main/android/README.md)
in the source tree for the full list, including what the platform does and does
not publish about the battery, and how the current is measured when the
vendor's own reading cannot be trusted.
