# TODO

## Supporting other Linux systems / Android (to discuss)

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
3. Monitor-only mode: with no way to control charging at all (a desktop, an
   unrooted Android), only show the data and the chart, hide or grey out the
   controls.
   - **done on Android**: `android/` is the monitoring half rewritten in Kotlin
     + Compose; the controls are shown greyed out with the reason next to them
4. Where it would land:
   - general Linux (laptops, mainline phones such as the PinePhone): the same
     code plus a backend table
   - Android: GTK cannot run there.  The equivalent is root + writing the
     charger's sysfs (ready-made: ACC / AccA, a Magisk module); without root
     only the vendor's fixed threshold is available (Samsung "Protect battery",
     Pixel "Charging optimisation", OnePlus/Xiaomi "smart charging" ...).
     - the port also has to work around the platform's own readings: there is no
       `charge_full`, `BATTERY_PROPERTY_CURRENT_NOW` is answered in mA by some
       vendors where the API promises µA, and the charge counter's own sign is
       worthless on those same phones (it only ever counts up, charging or
       discharging) -- its *magnitude* is what tells the two units apart (see
       `android/README.md`).

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
