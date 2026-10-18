# R8 rules for the release build.
#
# The app reflects on one thing, and it is a platform class, not ours:
# com.android.internal.os.PowerProfile, for the design capacity Android does not
# publish (Battery.kt).  R8 has nothing of ours to keep for it, and the Compose
# and Kotlin rules come with their Gradle plugins, so this file stays empty on
# purpose -- if it ever needs an entry, the entry should say what breaks without
# it.
