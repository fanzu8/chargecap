**Download [`chargecap-<version>-universal.apk`](https://github.com/fanzu8/chargecap/releases/download/<tag>/chargecap-<version>-universal.apk) and open it on the phone.**

One file, every phone. **Android 7.0 (API 24) or newer**, no root needed.

```sh
adb install -r chargecap-<version>-universal.apk
```

- Its only permission is `WAKE_LOCK`.
- Nothing to set up: it opens in dark mode, follows the system language, and
  starts monitoring.
- Without root the charge limit stays greyed out, with the reason next to it
  (charging control needs the GTK app's root daemon).

`SHA256SUMS` verifies the download.  A branch or PR build is signed with the
builder's own **debug key** instead of the release key below, so uninstall
before switching between the two.
