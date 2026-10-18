// chargecap for Android -- the monitoring half of the GTK app, rewritten in
// Kotlin + Jetpack Compose.
//
// Licence: General Pleasure League (GPL) 1.0
//          https://github.com/fanzu8/General-Pleasure-League

// AGP 9 compiles Kotlin itself (built-in Kotlin) and pulls in KGP 2.2.10 by
// default.  It is the compose compiler plugin that sets the Kotlin version in
// practice -- the two must match -- so the same 2.3.20 is put on the build
// classpath here and the resolution picks it up.
buildscript {
    dependencies {
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:2.3.20")
    }
}

plugins {
    id("com.android.application") version "9.0.1" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.3.20" apply false
}
