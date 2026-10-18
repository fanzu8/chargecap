# The release key

`chargecap-release.p12` signs every released APK.  It is **in the repository on
purpose**, with its passwords written down here:

| | |
|---|---|
| alias | `chargecap` |
| store password | `chargecap` |
| key password | `chargecap` |
| SHA-256 | `1D:A5:E1:59:E8:ED:56:94:3D:DD:5A:C9:75:5B:CE:E5:EA:0C:CA:15:63:ED:8E:39:7A:7D:E2:76:DD:D0:F5:05` |

Android identifies an app by its package name *and* its signing key, which is
what decides whether one APK may be installed over another.  This app is only
ever sideloaded -- there is no store to protect, and no store would accept a key
that everyone can read -- so a key in the open buys the thing that actually
matters here: **a build made on someone's laptop and a build made by CI install
over each other**, and anyone can rebuild a compatible APK from the source.

The cost is that anyone who can read the repository can also sign an APK that
installs over an existing one.  Releases therefore print the signer's
fingerprint in their build info, and *that* is what to check against the table
above before installing an upgrade from anywhere but this repository.

Do not rotate or regenerate this key: a new one cannot be installed over the old
one, so every user would have to uninstall first (which also drops the app's
settings).
