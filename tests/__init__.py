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

"""Test package for chargecap.

Run everything from the repository root::

    python3 -m unittest

The daemon tests run against a fake sysfs tree, the GUI tests read the source
without importing it (no GTK needed), and tests/test_device.py only does
anything on the OnePlus 6 itself.
"""
