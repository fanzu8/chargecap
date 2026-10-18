// chargecap for Android -- the monitoring half of the GTK app, rewritten in
// Kotlin + Jetpack Compose.
//
// Licence: General Pleasure League (GPL) 1.0
//          https://github.com/fanzu8/General-Pleasure-League

import org.jetbrains.kotlin.gradle.dsl.JvmTarget

// The project's version, and the tag it ships as: CI refuses to release a v*
// tag that does not match this string.
val appVersion = "0.0.1"

/** 0.0.1 -> 1, 1.2.3 -> 10203: the number Android orders upgrades by, derived. */
fun versionCodeOf(version: String): Int {
    val (major, minor, patch) = version.split(".").map { it.toInt() }
    return major * 10000 + minor * 100 + patch
}

plugins {
    id("com.android.application")
    // no kotlin-android: AGP 9 has built-in Kotlin support, and the old plugin
    // is not compatible with its DSL
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "org.chargecap.android"
    compileSdk = 36

    defaultConfig {
        applicationId = "org.chargecap.android"
        minSdk = 24
        targetSdk = 36
        versionCode = versionCodeOf(appVersion)
        versionName = appVersion
    }

    signingConfigs {
        // The release key is here on purpose: the app is only ever sideloaded,
        // and a key in the open is what lets a build made here and a build made
        // by CI install over each other.  See keystore/README.md -- it also says
        // why the key must never be rotated.
        create("release") {
            storeFile = rootProject.file("keystore/chargecap-release.p12")
            storePassword = "chargecap"
            keyAlias = "chargecap"
            keyPassword = "chargecap"
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            // a release should be the small, non-debuggable one, and it is what
            // the download is named after (no "-debug" in the file name)
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    buildFeatures {
        compose = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.03.01")
    implementation(composeBom)

    implementation("androidx.core:core-ktx:1.18.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")

    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-text")
}
