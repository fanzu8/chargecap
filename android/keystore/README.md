# The release key

`chargecap-release.p12` signs every released APK.  It is **in the repository on
purpose**, with its passwords written down here:

| | |
|---|---|
| subject (DN) | `CN=fanzu8` |
| alias | `chargecap` |
| store password | `chargecap` |
| key password | `chargecap` |
| SHA-256 | `16:79:B2:6C:02:47:F2:AA:99:FB:B0:F4:66:FF:AA:53:B5:4B:E0:52:16:4B:87:99:B7:AB:62:C2:6C:6E:54:CE` |

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

The other direction is the same: a branch or PR build is signed with the
builder's own **debug key** rather than this one, so switching between a debug
build and a release build also means uninstalling first.
