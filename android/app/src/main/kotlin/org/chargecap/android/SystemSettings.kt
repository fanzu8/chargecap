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

import android.app.AlarmManager
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings

// The system screens the 高级 page sends the user to, because the two things a
// notification needs are not the app's to switch:
//
//   通知横幅与声音 -- the app's own notification settings.  The banner and the
//                     sound are the channel's, and the page is the system's;
//                     on Android 13+ the runtime permission comes first.
//   自启动         -- staying alive after a reboot.  There is no API for it and
//                     every vendor files it somewhere else, so the known screens
//                     are tried in turn and the app's own page is the fallback.
//
// Nothing here is guaranteed: a vendor that moves a screen leaves the fallback,
// which is why each one is tried and the answer is a plain true / false.

/**
 * The system's page for our notifications: 通知横幅, 声音 and 震动 live there,
 * per channel.
 *
 * The channel's own page comes first (Android 8+), because it is the one with
 * the switches; the app's notification page and then the app's own page are
 * the doors left when a device files it differently.
 */
fun openNotificationSettings(context: Context): Boolean {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return openAppInfo(context)
    val channel = Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
        .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
        .putExtra(Settings.EXTRA_CHANNEL_ID, NOTIFY_CHANNEL)
    if (start(context, channel)) return true
    val app = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
        .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
    return start(context, app) || openAppInfo(context)
}

/**
 * The vendor's autostart page, the ones the common phones use.
 *
 * None of these names is an API -- they are what other apps try, kept in the
 * order the phones turn up here.  Huawei first (the phone this was written on,
 * where both of its screens resolve), then the rest.
 */
private val AUTOSTART = listOf(
    "com.huawei.systemmanager/.startupmgr.ui.StartupNormalAppListActivity",
    "com.huawei.systemmanager/.appcontrol.activity.StartupAppControlActivity",
    "com.miui.securitycenter/com.miui.permcenter.autostart.AutoStartManagementActivity",
    "com.coloros.safecenter/com.coloros.safecenter.permission.startup.StartupAppListActivity",
    "com.coloros.safecenter/com.coloros.safecenter.startupapp.StartupAppListActivity",
    "com.oppo.safe/.permission.startup.StartupAppListActivity",
    "com.vivo.permissionmanager/.activity.BgStartUpManagerActivity",
    "com.iqoo.secure/.ui.phoneoptimize.AddWhiteListActivity",
    "com.samsung.android.lool/com.samsung.android.sm.ui.battery.BatteryActivity",
    "com.meizu.safe/.permission.SmartBGActivity",
    "com.letv.android.letvsafe/.AutobootManageActivity",
)

/** The vendor's autostart page, or the app's own page when none of them answers. */
fun openAutostartSettings(context: Context): Boolean {
    for (path in AUTOSTART) {
        val screen = ComponentName.unflattenFromString(path) ?: continue
        if (start(context, Intent().setComponent(screen))) return true
    }
    return openAppInfo(context)
}

/** 电池优化: the one switch that keeps Doze from stopping the reader. */
fun batteryExempt(context: Context): Boolean {
    val power = context.getSystemService(PowerManager::class.java) ?: return true
    return power.isIgnoringBatteryOptimizations(context.packageName)
}

/** The system's request dialog, then the full list as the fallback. */
fun openBatteryOptimization(context: Context): Boolean {
    // already exempt: do not ask again, show the list so it can be undone
    if (batteryExempt(context)) {
        return start(context, Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
    }
    try {
        val request = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                             Uri.parse("package:${context.packageName}"))
        if (start(context, request)) return true
    } catch (_: Throwable) {
        // fall through to the list
    }
    return start(context, Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
}

/** SCHEDULE_EXACT_ALARM: needed for the 30 s sampler on Android 12 and later. */
fun exactAlarms(context: Context): Boolean {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return true
    val manager = context.getSystemService(AlarmManager::class.java) ?: return true
    return manager.canScheduleExactAlarms()
}

fun openExactAlarm(context: Context): Boolean {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        try {
            val request = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,
                                 Uri.parse("package:${context.packageName}"))
            if (start(context, request)) return true
        } catch (_: Throwable) {
            // fall through to the app page
        }
    }
    return openAppInfo(context)
}

/** 设置 -> 应用 -> chargecap, the one page every phone has. */
/** The project's releases: where a new version is downloaded from. */
const val RELEASES_URL = "https://github.com/fanzu8/chargecap/releases"

/** 更新: the releases page in the phone's browser, since 关于 cannot check. */
fun openReleases(context: Context): Boolean =
    start(context, Intent(Intent.ACTION_VIEW, Uri.parse(RELEASES_URL)))

private fun openAppInfo(context: Context): Boolean =
    start(context, Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                          Uri.fromParts("package", context.packageName, null)))

/**
 * Hand an Intent to the system, and say whether anyone took it.
 *
 * A vendor screen that has moved throws, and on Android 11+ a package we did
 * not name in the manifest is invisible and throws the same way -- both mean
 * "try the next one", so a failure is an answer here rather than an error.
 */
private fun start(context: Context, intent: Intent): Boolean = try {
    context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    true
} catch (t: Throwable) {
    false
}

// ---- what the system has switched off ---------------------------------------

/**
 * The reminders 设置 can take away, as far as Android will say: the channel may
 * be silenced, and the system may stop the app once the screen goes off.
 */
enum class Limit {
    NOTIFICATIONS,

    /**
     * Not 自启动 itself -- that switch is the vendor's and has no API.  The
     * battery exemption is the closest question that can be asked, and the one
     * that decides whether the rules are still running when a reminder is due.
     */
    BACKGROUND,
}

/**
 * What is missing right now, in the order 设置 lists it.  Empty means the app
 * has what it needs as far as the system will tell.
 *
 * Read when 通知开关 is turned on: the banner and the sound are the channel's,
 * and a reminder due with the screen off needs the process still alive.
 */
fun limits(context: Context): List<Limit> {
    val missing = mutableListOf<Limit>()
    val notifications = context.getSystemService(NotificationManager::class.java)
    if (notifications != null) {
        val channel = notifications.getNotificationChannel(NOTIFY_CHANNEL)
        if (!notifications.areNotificationsEnabled() ||
            channel?.importance == NotificationManager.IMPORTANCE_NONE) {
            missing += Limit.NOTIFICATIONS
        }
    }
    val power = context.getSystemService(PowerManager::class.java)
    if (power?.isIgnoringBatteryOptimizations(context.packageName) == false) {
        missing += Limit.BACKGROUND
    }
    return missing
}
