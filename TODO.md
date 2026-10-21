# TODO

## Supporting other Linux systems (to discuss)

Goal: **where the machine lets us set things, set them; where it does not, still
read the data and draw the chart** (monitor-only mode).

1. Move the "backend" out of the code (node paths + semantics) instead of
   hard-coding `pmi8998-charger` / `bq27411-0`:
   - capacity / voltage / current / temperature / full capacity:
     `power_supply/BAT*/`, whose field names differ per machine
   - stop / resume charging: many machines expose a single threshold
     (`charge_control_end_threshold`).  One threshold is enough for hysteresis:
     write the current percentage as the threshold to stop, write the upper
     limit back to resume.
   - USB input current limit: missing on most machines; make it optional
   - **first step done**: the gauge and charger nodes are found by the
     attributes they expose (`find_supply`), the known names are only a
     fallback -- which is what lets the OnePlus 6T work unchanged
2. Capability detection: enable whatever can be read, mark the rest as
   "unsupported / read-only" and trim the UI accordingly.
3. Monitor-only mode: with no way to control charging at all (a desktop), only
   show the data and the chart, hide or grey out the controls.
4. Where it would land: general Linux (laptops, mainline phones such as the
   PinePhone) gets the same code plus a backend table.

## Languages

- Chinese / English follow the system language (`GLib.get_language_names()`);
  English has its own, smaller type scale (`SCALE`).  Adding a language means
  one table plus one line in `SCALE`.
- The manual switch in the header (auto / 中文 / English) is stored in
  `ui.json`; changing it restarts the panel, because the strings are translated
  while the UI is being built.
- English needs two abbreviations: the metric buttons use the unit
  (V / mA / W / °C / %) and the chart axes use the standard quantity symbols
  (U / I / P / T / SOC, with the unit written underneath).

## Notifications

Shipped on both platforms; `README.md` has the full behaviour, this is the
shape of it:

- thirteen notifications in seven groups: 基础功能 (充电完成 / 电量过低),
  电源 (连接 / 断开), 充电 (充电中 / 未充电), 温度 (过高 / 过低),
  电压 (过高 / 过低), 电流 (充电过高 / 放电过高) and 功率 (过高);
- a threshold per notification, its own set -- never the panel's 上限 / 下限 --
  and the states (电源连接 / 电源断开 / 充电中 / 未充电) with no number at all;
- the three answers -- 通知方式 (横幅 / 语音), 次数 and 间隔 -- stored under the
  same keys on both sides, so the two read alike;
- every switch off on a fresh install; 语音, 1次 and 间隔 2s until asked;
- one firing per crossing, quiet while the reading rests on the line, and a
  repeat that wakes to a reading back inside its line ends the count;
- silent arming: turning a switch on, or opening the app under one already on,
  takes the readings as they are instead of saying them -- only a later
  crossing is news;
- postmarketOS runs the rules in `notifier.py`, a systemd **user** service, so
  a banner arrives with the panel closed; on Android they run with the process.
- the voice is Android's own TTS and `spd-say` (speech-dispatcher) on
  postmarketOS; without an engine the page offers 横幅 alone.

Still open:

- **Compound rules**: the same reading, where the condition has to hold or
  repeat:
  - discharge current above 1000 mA for 10 s
  - power above 10 W for 20 s
  - voltage reaching its threshold 3 times in a minute

  A rule would be a reading, a comparison and either a duration or a count, so
  one evaluator covers both kinds; the panel already samples every 500 ms,
  which is the resolution such windows get.
- **Rate-of-change rules**: a notification on how fast a reading moves
  (°C/min, mV/s) rather than on its value.
