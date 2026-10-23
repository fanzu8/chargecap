#!/bin/sh

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

# Remove the chargecap daemon + GUI and all its state. Run as root.

set -e

systemctl disable --now chargecap.service 2>/dev/null || true

# the notifier lives in the user's session; stop it there before its files go
USER_UID=$(id -u user 2>/dev/null || true)
if [ -n "$USER_UID" ] && [ -d "/run/user/$USER_UID" ]; then
	sudo -u user env XDG_RUNTIME_DIR="/run/user/$USER_UID" \
		systemctl --user disable --now chargecap-notify.service \
		2>/dev/null || true
	# the panel is a user process, not a service the uninstall would stop;
	# the transient unit may already have detached from its process
	sudo -u user env XDG_RUNTIME_DIR="/run/user/$USER_UID" \
		systemctl --user stop chargecap-panel.service \
		2>/dev/null || true
fi
pkill -u user -f '/usr/local/bin/chargecap$' 2>/dev/null || true

rm -f /etc/systemd/system/chargecap.service
rm -f /usr/lib/systemd/user/chargecap-notify.service
rm -f /usr/local/bin/chargecap
rm -f /usr/local/bin/chargecap-notify
rm -f /usr/share/applications/org.postmarketos.Chargecap.desktop
rm -f /usr/share/icons/hicolor/scalable/apps/org.postmarketos.Chargecap.svg
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
rm -rf /usr/local/lib/chargecap
rm -rf /var/lib/chargecap
rm -rf /run/chargecap
rm -rf /home/user/.config/chargecap

systemctl daemon-reload

# release both overrides: allow charging again and push the USB input current
# limit back to the rated maximum -- a limit left behind would linger in the
# charger until the next re-plug
echo 1 > /sys/class/power_supply/pmi8998-charger/status 2>/dev/null || true
max=$(cat /sys/class/power_supply/bq27411-0/constant_charge_current_max 2>/dev/null)
if [ -n "$max" ]; then
	echo "$max" > /sys/class/power_supply/pmi8998-charger/current_max 2>/dev/null || true
fi

echo "uninstalled."
