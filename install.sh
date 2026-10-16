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

# Install the chargecap daemon + GUI. Run as root.

set -e

USER_NAME="user"
USER_HOME="/home/$USER_NAME"

# the chart needs Python cairo bindings (PangoCairo); warn early because the
# GUI cannot start without them
if ! python3 -c "import cairo" 2>/dev/null; then
	echo "!! 缺少 Python cairo 绑定，界面将无法启动：请先执行 apk add py3-cairo" >&2
fi

mkdir -p /usr/local/lib/chargecap /var/lib/chargecap

install -m 0755 daemon.py /usr/local/lib/chargecap/daemon.py
install -m 0755 chargecap /usr/local/bin/chargecap
install -m 0644 chargecap.service /etc/systemd/system/chargecap.service
install -m 0644 org.postmarketos.Chargecap.desktop \
	/usr/share/applications/org.postmarketos.Chargecap.desktop

# the app icon: named after the application id, as the desktop expects
mkdir -p /usr/share/icons/hicolor/scalable/apps
install -m 0644 icons/org.postmarketos.Chargecap.svg \
	/usr/share/icons/hicolor/scalable/apps/org.postmarketos.Chargecap.svg
gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true

# per-user request directory (owned by the desktop user)
install -d -o "$USER_NAME" -g "$USER_NAME" -m 0755 "$USER_HOME/.config" 2>/dev/null || true
install -d -o "$USER_NAME" -g "$USER_NAME" -m 0755 "$USER_HOME/.config/chargecap"

systemctl daemon-reload
systemctl enable --now chargecap.service

echo "installed. status:"
systemctl --no-pager --full status chargecap.service || true
