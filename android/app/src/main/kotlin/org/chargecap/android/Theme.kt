// ---------------------------------------------------------------------------
// chargecap - keep an always-plugged-in phone inside a charge window
//
// Licence: General Pleasure League (GPL) 1.0
//          https://github.com/fanzu8/General-Pleasure-League
//
//          You are the general of your own life, the master of your own fate:
//          no restrictions, no compulsions - use it, change it, share it, and
//          let pleasure be your primary guide.  Just be happy.
// ---------------------------------------------------------------------------

package org.chargecap.android

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// The GTK app wears the system's Adwaita colours; here the Material 3 scheme
// takes the icon's green as its accent and leaves the rest to the platform.

private val LightScheme = lightColorScheme(
    primary = Color(0xFF128A43),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFB8F0D2),
    onPrimaryContainer = Color(0xFF04331C),
    secondary = Color(0xFF4C6358),
)

private val DarkScheme = darkColorScheme(
    primary = Color(0xFF57E389),
    onPrimary = Color(0xFF00391F),
    primaryContainer = Color(0xFF0C5228),
    onPrimaryContainer = Color(0xFFB8F0D2),
    secondary = Color(0xFFB3CCBF),
)

/** The background the app is drawn on; dark is the default, as on pmOS. */
enum class Theme(val tag: String) {
    DARK("dark"), LIGHT("light"), AUTO("auto");

    companion object {
        fun of(tag: String?): Theme = entries.firstOrNull { it.tag == tag } ?: DARK
    }
}

@Composable
fun AppTheme(
    theme: Theme = Theme.DARK,
    content: @Composable () -> Unit,
) {
    val dark = when (theme) {
        Theme.DARK -> true
        Theme.LIGHT -> false
        Theme.AUTO -> isSystemInDarkTheme()
    }
    MaterialTheme(
        colorScheme = if (dark) DarkScheme else LightScheme,
        content = content,
    )
}
