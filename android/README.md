# chargecap for Android

<img src="../icons/org.postmarketos.Chargecap.svg" width="88" alt="chargecap">

The GTK app's **monitoring half**, in Kotlin + Jetpack Compose: same panel, same
chart, same words.  Charging control needs a **root daemon** writing the
charger's nodes, which SELinux denies to apps, so an unrooted phone can only be
read.

## What it cannot do

| | |
|---|---|
| **Limit charging** (上限 / 下限 / 启动) | needs root: the rows are the GTK app's own, shown switched off |
| **USB input current limit** (限制) | no writable node without root, so the box is empty |
| **Rated maximum current** (最大) | Android does not publish it |
| **Health percentage** | Android reports a health *state*, never `charge_full` |

禁止休眠 works -- a partial wake lock, where the daemon holds a
`systemd-inhibit` -- as does everything else that can be read, the chart
included: samples in memory only (48 hours at 2 Hz), taken off the UI thread, so
it keeps filling while the screen is off.  And **休眠记录**, the row under it,
is where that promise can be caught: the sampler reads its two clocks every
pass, and uptime's shortage against the wall clock is how long the system slept
inside it.  It is a record, not a notification -- a sleeping system delivers
nothing -- so the row has no switch, no 通知方式, no 次数, no 间隔.  It has
nothing to do with 通知开关 either: the count is the last 禁止休眠 turn-on's, a
reboot clears it, and a tap opens the sleeps it kept.

The header carries two pages and a gear.  The app opens on **通知**, a page the
GTK app has too -- the same notifications, the same words, its own tab beside
高级.  The tab you are on sits on its own background, so which of the two is
showing needs no reading.

通知开关 has a row to itself: it is the page's one gate, not one
notification's answer.  With it off every row under it is drawn grey and takes
no input -- and not one answer changes, so switching it back on finds the page
exactly as it was left.  Under it the notifications come in seven groups --
**基础功能** (充电完成 / 电量过低), **电源** (连接 / 断开), **充电**
(充电中 / 未充电), **温度** (过高 / 过低), **电压** (过高 / 过低),
**电流** (充电过高 / 放电过高) and **功率** (过高): thirteen in all, and the
states (电源连接 / 电源断开 / 充电中 / 未充电) have no number to set.

The row wears the short word because its group already says the rest --
电源连接 is just 连接 under 电源 -- while the sentence a banner or a voice
says keeps the full name (电源连接, 温度过高 45 °C).  Each row is one
notification on one line: its name, the number it fires at in the middle, the
switch at the end; and then one row of answers -- 通知方式, 次数 and 间隔.
The numbers are 100 %, 10 %, 45 °C, -20 °C, 4300 mV, 3400 mV, 3000 mA,
1000 mA and 20 W, typed in or stepped, each inside its own range (0-100 %,
-60-100 °C, 3000-5000 mV, 2500-4500 mV, 0-10000 mA, 0-5000 mA, 0-100 W), and
never the panel's 上限 / 下限.  No 达 / 低于 / 高于 word stands beside the
number: the name already says which way it reads.  充电完成 always stays above
电量过低: two lines that cross are two notifications arguing with each other,
so each one's range stops at the other.

Every switch arrives off: the master decides whether anything fires at all,
and each notification is its owner's choice, so turning the master on does not
start a page of reminders nobody asked for.  The answers arrive at 语音, once,
间隔 2 s, and then repeat only if asked.

Turning a switch on -- the master's or one notification's -- **says nothing**,
and neither does opening the app under a switch that was already on: the rules
arm against the readings as they are, and only a crossing afterwards is news.
A switch turned on while the phone is already hot does not announce the heat
it did not see.  (A stepper is different: moving a line past the present value
is still a crossing, and says so.)

A notification arrives one way or the other -- **横幅** or **语音** -- and
次数 belongs to both: a banner is posted again, a voice says it again.  A
spoken notification is what makes the app usable without looking at it: an
elderly parent hears 充电完成 or 电量过低 from across the room.  The
counts are 1次 to 10次, plus -- where waiting means something -- one endless
chip.  电量过低 has 直到开始充电, 充电完成 has 直到电源断开, and either repeats
until the plug goes in or the power goes off.

间隔 is how long it waits between those repeats: 1s, 2s, 3s, 5s, 10s, 15s,
20s, 30s, 1min, 2min or 5min, two seconds unless asked otherwise.  At 1次 it
reads 0 -- a single notification has no gap, so the 0 is shown rather than the
row going quiet, and it cannot be changed.  A repeat is only news while the
reading is still past the line: if the gap was long enough for the battery to
come back (the phone cooled down, the charge came up, the line itself was
moved), the rest of the count is dropped rather than saying something that is
no longer true.  With 通知开关 off nothing is heard at all, the 试听 included --
and a sentence already handed to the engine is cut off rather than played to
its end.  通知方式 and 次数 are read again at every repeat, so a chip moved
mid-count takes effect from there.

The answers are stored, and the rules read them: each notification fires when
its reading crosses its line, once, and is quiet until the reading comes back
clear -- past the line by more than the notification's own step -- so a value
resting on the line says its piece once rather than twice a second.
电压 is read in millivolts off the gauge that reports volts, 充电电流过高 watches
the positive half of the signed current, and 放电电流过高 the negative half, so
each one only fires on its own side; 功率过高 compares the size of the power,
whichever direction it flows.  A voice is the phone's
own engine reading the same sentence, one announcement at a time: a new one
takes over rather than queueing behind the last, and a phone with no engine for
the app's language simply says nothing.
**高级** is the panel the GTK app draws -- limits, 禁止休眠, the status table, the
chart -- and the **gear** at the far right of the header is **设置**: the two
switches only the system owns, each a row that leaves the app, and **关于**.
自启动 comes first (no API for it, and every vendor files it elsewhere, so the
known screens are tried in turn and the app's own page is the fallback), then
通知横幅与声音 -- the channel's own page, where EMUI for one keeps 横幅 off
until asked.

关于 carries the version (`0.0.2 (a1b2c3d4-20261021)` -- the number, the commit
and the build day), the author, a 更新 row that opens the releases page in the
browser, and the privacy line: no network, no data collected.  All four are plain
selectable text -- long-press to copy.

Where the platforms differ, the ⓘ next to a value says how: the charger type is
the port (AC / USB / wireless / dock), 健康度 is the state the system reports,
and the mAh row's first number is the gauge's coulomb counter -- charge that has
flowed through it, *not* what is left, so `54/4000` is not 1.35% (it resets when
the battery reaches full).

## Build and install

```sh
cd android
./gradlew assembleDebug                      # needs a JDK 17+ and the Android SDK
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

`org.chargecap.android`, Android 7.0 (API 24) and up, tested on Android 9 (EMUI
9.1).  Permissions: `WAKE_LOCK` for 禁止休眠; `POST_NOTIFICATIONS` -- granted at
install up to Android 12, asked for when 通知开关 goes on from 13; and
`FOREGROUND_SERVICE` / `FOREGROUND_SERVICE_SPECIAL_USE` /
`RECEIVE_BOOT_COMPLETED` for the background monitor.  The `<queries>` also names
the vendor packages an autostart Intent has to reach.

## Releases

CI builds on every change to `android/`, and on a `v*` tag attaches the result to
a release; the tag has to match the version the build declares (`v0.0.2` needs
`appVersion = "0.0.2"`).  One file per release,
`chargecap-<version>-<abi>-<variant>.apk`:

| | |
|---|---|
| `chargecap-0.0.2-universal.apk` | the release: signed with `keystore/`, minified, not debuggable |
| `chargecap-0.0.2-universal-debug.apk` | a branch or PR build: attached to the run, never released |
| `SHA256SUMS` | the APK's hash, for `sha256sum -c` |
| `chargecap-0.0.2-build-info.txt` | commit, build time, ABIs, toolchain, signer |

`<version>` is the tag without its `v`, `<abi>` is `universal` (all four ABIs in
one file: splitting them would save 36 KB of a 3.4 MB download).  The `keystore/`
key is what lets a local and a CI build install over each other, so it must never
be rotated; CI refuses a release it did not sign.

## Licence

[General Pleasure League (GPL) 1.0](https://github.com/fanzu8/General-Pleasure-League)
