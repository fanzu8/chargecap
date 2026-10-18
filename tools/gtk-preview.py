#!/usr/bin/env python3

# ---------------------------------------------------------------------------
# chargecap - keep an always-plugged-in phone inside a charge window
#
# Licence: General Pleasure League (GPL) 1.0
#          https://github.com/fanzu8/General-Pleasure-League
#
#          You are the general of your own life, the master of your own fate:
#          no restrictions, no compulsions - use it, change it, share it, and
#          let pleasure be your primary guide.  Just be happy.
# ---------------------------------------------------------------------------

"""Run the GTK front end on a development machine, against a fake sysfs tree.

    python3 tools/gtk-preview.py             # the panel, as a plugged-in phone
    python3 tools/gtk-preview.py --off       # nothing plugged in, discharging
    python3 tools/gtk-preview.py --scheme light

The GUI finds the gauge and the charger by the attributes they expose and reads
them straight, so a handful of files in a temp directory are enough to see the
whole panel -- no phone, no daemon, no root.  The daemon's two files are faked
as well, so the controls are live instead of greyed out and the status table
shows the numbers a device would.

It needs GTK4, libadwaita and PyGObject -- what the app needs on the phone too
(`brew install gtk4 libadwaita pygobject3` on a Mac).
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# the gauge and the charger: the OnePlus 6's names, the attributes the app
# looks for
GAUGE = {"capacity": 87, "voltage_now": 4243000, "current_now": -1510000,
         "temp": 273, "constant_charge_current_max": 1800000,
         "charge_full": 3456000, "charge_full_design": 4000000, "health": 87}
PLUGGED = {"BAT": {"status": "Charging"},
           "CHG": {"online": 1, "status": "1",
                   "usb_type": "Unknown SDP [DCP] CDP", "current_max": 900000},
           "state": {"limit_enabled": True, "upper": 50, "lower": 45,
                     "inhibit_sleep": False, "current_limit": 900}}
UNPLUGGED = {"BAT": {"status": "Discharging"},
             "CHG": {"online": 0, "status": "0",
                     "usb_type": "Unknown SDP DCP CDP", "current_max": 0},
             "state": {"limit_enabled": False, "upper": 50, "lower": 45,
                       "inhibit_sleep": False, "current_limit": 0}}


def write_tree(root, plugged):
    """A sysfs tree and a state file for the daemon the GUI reads."""
    what = PLUGGED if plugged else UNPLUGGED
    paths = {}
    for name, directory, values in (("BAT", "bq27411-0", GAUGE),
                                    ("CHG", "pmi8998-charger", {})):
        path = os.path.join(root, directory)
        os.makedirs(path, exist_ok=True)
        files = dict(values)
        files.update(what[name])
        for attr, value in files.items():
            with open(os.path.join(path, attr), "w") as f:
                f.write(str(value))
        paths[name] = path

    state = os.path.join(root, "state.json")
    with open(state, "w") as f:
        json.dump(what["state"], f)
    return paths["BAT"], paths["CHG"], state


def load_gui():
    """The chargecap script as a module (it has no .py suffix)."""
    loader = importlib.machinery.SourceFileLoader(
        "chargecap", os.path.join(ROOT, "chargecap"))
    spec = importlib.util.spec_from_loader("chargecap", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["chargecap"] = module
    loader.exec_module(module)
    return module


def render_to_png(window, path):
    """Write what the panel looks like, without needing a window manager."""
    from gi.repository import Gtk
    paintable = Gtk.WidgetPaintable.new(window)
    width, height = window.get_width(), window.get_height()
    snapshot = Gtk.Snapshot.new()
    paintable.snapshot(snapshot, width, height)
    texture = window.get_native().get_renderer().render_texture(snapshot.to_node())
    texture.save_to_png(path)
    print(f"{path}: {width}x{height}", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--off", action="store_true",
                    help="nothing plugged in: discharging, limit off")
    ap.add_argument("--scheme", choices=("dark", "light", "auto"),
                    help="the background to open in (default: dark)")
    ap.add_argument("--metric", action="append", choices=(
        "voltage_v", "current_mA", "power_w", "temp_c", "capacity"),
        help="a metric to plot (repeatable; default: the saved UI file)")
    ap.add_argument("--shot", metavar="PNG",
                    help="render the panel to a PNG and quit")
    ap.add_argument("--quit-after", type=float, metavar="SECONDS",
                    help="close the window again (for scripted screenshots)")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="chargecap-preview-")
    bat, chg, state = write_tree(tmp, not args.off)

    # the language, the background and the chart preferences are read from
    # ~/.config/chargecap/ui.json while the module is being imported, so the
    # sandbox has to be the home directory *before* that happens
    config = os.path.join(tmp, ".config", "chargecap")
    os.makedirs(config, exist_ok=True)
    ui = {}
    if args.scheme:
        ui["scheme"] = args.scheme
    if args.metric:
        ui["metrics"] = args.metric
    with open(os.path.join(config, "ui.json"), "w") as f:
        json.dump(ui, f)
    os.environ["HOME"] = tmp
    os.environ["XDG_CONFIG_HOME"] = os.path.join(tmp, ".config")

    gui = load_gui()
    # point it at the fake tree and the fake daemon before any widget is built
    gui.BAT, gui.CHG = bat, chg
    gui.STATE = state
    gui.REQUEST = os.path.join(tmp, "request.json")

    from gi.repository import GLib

    app = gui.App()

    def arm(*_):
        if args.shot:
            def shoot():
                render_to_png(app.get_active_window(), args.shot)
                app.quit()
            # late enough for the page to have been laid out and drawn once
            GLib.timeout_add(1200, shoot)
        elif args.quit_after:
            GLib.timeout_add(int(args.quit_after * 1000), lambda: app.quit())

    app.connect("activate", arm)
    return app.run(None)


if __name__ == "__main__":
    sys.exit(main())
