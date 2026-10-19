**Download [`chargecap-<version>-universal.apk`](https://github.com/fanzu8/chargecap/releases/download/<tag>/chargecap-<version>-universal.apk) and open it on the phone** — or `adb install -r chargecap-<version>-universal.apk`.

**Android 7.0+**, no root, one file for every phone.  Without root it only
monitors: the charge limit stays greyed out.  Its one permission is `WAKE_LOCK`.

`SHA256SUMS` checks the download.  A debug build (branch, PR) is signed with the
builder's own debug key instead, so uninstall before switching.
