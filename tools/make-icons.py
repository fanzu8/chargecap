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

"""Render the launcher icon into the Android resources.

    python3 tools/make-icons.py        # needs rsvg-convert

Android 8 and up draw the adaptive icon: a 108dp canvas of which the launcher
shows a mask over the middle 72dp, with a *guaranteed-safe* circle 66dp across.
Artwork that reaches past that circle has its corners cut off by a round mask,
which is what a full-bleed icon does -- so the artwork is scaled to TARGET of
the circle and centred, and the plain bitmaps below (Android 7 has no adaptive
icons) use the same artwork on the plate the adaptive background uses.

The icon's own <svg> carries a scale of its own; it is dropped here so that the
geometry below is the artwork's real one.
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(ROOT, "icons", "org.postmarketos.Chargecap.svg")
RES = os.path.join(ROOT, "android", "app", "src", "main", "res")

# the battery and its terminal nub, in the SVG's own units (x1, y1, x2, y2)
ART_BOX = (162, 330, 862, 694)
CLEAR = 1024.0            # the SVG's canvas
SAFE_DIAMETER = 66.0 / 108.0   # the adaptive icon's safe circle, as a fraction
# as much of that circle as the artwork's own shape allows: the limit is its
# corners, not its width, so this is where they meet the circle and no further
TARGET = 0.88
PLATE = "#FFFFFF"

DENSITIES = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0, "xxhdpi": 3.0,
             "xxxhdpi": 4.0}
ICONS = (("ic_launcher", 48, True),                   # plain bitmaps: 48dp
         ("ic_launcher_round", 48, True),
         ("ic_launcher_foreground", 108, False))      # adaptive foreground


def art_scale():
    """The scale that puts the artwork at TARGET of the safe circle."""
    return TARGET * SAFE_DIAMETER * CLEAR / (ART_BOX[2] - ART_BOX[0])


def wrap(inner, background):
    """The artwork, centred and scaled, on (or without) the plate."""
    plate = f'<rect width="{CLEAR:.0f}" height="{CLEAR:.0f}" fill="{background}"/>' if background else ""
    cx = (ART_BOX[0] + ART_BOX[2]) / 2
    cy = (ART_BOX[1] + ART_BOX[3]) / 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CLEAR:.0f} '
            f'{CLEAR:.0f}" width="{CLEAR:.0f}" height="{CLEAR:.0f}">' + plate +
            f'<g transform="translate({CLEAR / 2:.0f} {CLEAR / 2:.0f}) '
            f'scale({art_scale():.6f}) translate({-cx:.0f} {-cy:.0f})">'
            + inner + "</g></svg>")


def main():
    with open(SVG) as f:
        source = f.read()
    inner = source.split(">", 1)[1].rsplit("</svg>", 1)[0]
    # the icon brings its own scale; the geometry in ART_BOX is without it, so
    # its wrapper <g> goes (opening and closing both)
    inner = re.sub(r"^\s*<g[^>]*>", "", inner, count=1)
    if inner.rstrip().endswith("</g>"):
        inner = inner.rstrip()[:-len("</g>")]

    tmp = tempfile.mkdtemp(prefix="chargecap-icons-")
    fronts = {}
    for name, background in (("plate", PLATE), ("clear", None)):
        path = os.path.join(tmp, name + ".svg")
        with open(path, "w") as f:
            f.write(wrap(inner, background))
        fronts[name] = path

    for density, scale in DENSITIES.items():
        out = os.path.join(RES, f"mipmap-{density}")
        os.makedirs(out, exist_ok=True)
        for name, size, on_plate in ICONS:
            png = os.path.join(out, name + ".png")
            side = int(round(size * scale))
            done = subprocess.run(
                ["rsvg-convert", "-w", str(side), "-h", str(side), "-o", png,
                 fronts["plate" if on_plate else "clear"]])
            if done.returncode != 0:
                return done.returncode
            print(f"{os.path.relpath(png, ROOT)}: {side}x{side}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
