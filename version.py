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

"""Which chargecap this is: the number, and the build 关于 names.

VERSION is the one number a release is known by -- the Android build reads its
own copy in build.gradle.kts, and a test keeps the two honest.  The eight
characters and the day are not known until a build is made: install.sh writes
them to /usr/local/lib/chargecap/build-info, and a run from the checkout asks
git.  Where neither can answer, the number stands alone.
"""
import os
import subprocess

VERSION = "0.0.3"

# written by install.sh beside this file
BUILD_INFO = "/usr/local/lib/chargecap/build-info"


def _installed():
    try:
        with open(BUILD_INFO) as f:
            commit, day = f.read().split()[:2]
    except (OSError, ValueError):
        return None
    return (commit, day) if commit and day else None


def _git():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        commit = subprocess.check_output(
            ["git", "-C", here, "rev-parse", "--short=8", "HEAD"],
            text=True, stderr=subprocess.DEVNULL).strip()
        day = subprocess.check_output(
            ["git", "-C", here, "log", "-1", "--format=%cd",
             "--date=format:%Y%m%d"],
            text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return (commit, day) if commit and day else None


def build_label():
    """0.0.3 (a1b2c3d4-20261021), or just 0.0.3 when nothing knows better."""
    info = _git() or _installed()
    if not info:
        return VERSION
    return "%s (%s-%s)" % (VERSION, info[0], info[1])
