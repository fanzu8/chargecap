// chargecap for Android -- the monitoring half of the GTK app, rewritten in
// Kotlin + Jetpack Compose.
//
// Licence: General Pleasure League (GPL) 1.0
//          https://github.com/fanzu8/General-Pleasure-League

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "chargecap-android"
include(":app")
