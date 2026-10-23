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

# 语音: the app speaks through whichever engine the phone has.  Without one the
# notification page quietly offers 横幅 alone, so say why.
if ! command -v spd-say >/dev/null 2>&1 && \
   ! command -v espeak-ng >/dev/null 2>&1 && \
   ! command -v espeak >/dev/null 2>&1; then
	echo "!! 没有语音引擎，语音通知不可用：请先执行 apk add speech-dispatcher espeak-ng" >&2
fi

# an upgrade must not leave a module from an older release behind: the library
# directory is ours, so replace it rather than layering the new files on top
rm -rf /usr/local/lib/chargecap
rm -f /usr/local/bin/chargecap /usr/local/bin/chargecap-notify
mkdir -p /usr/local/lib/chargecap /var/lib/chargecap

install -m 0755 daemon.py /usr/local/lib/chargecap/daemon.py
# the notification table is shared: the panel draws the page, the notifier
# (a user service) keeps watching with the panel closed
install -m 0644 notifications.py /usr/local/lib/chargecap/notifications.py
install -m 0644 version.py /usr/local/lib/chargecap/version.py
# 关于 says which build this is: the eight characters and the day it was
# installed.  No repository (a tarball install) leaves the number alone.
commit=$(git rev-parse --short=8 HEAD 2>/dev/null || true)
if [ -n "$commit" ]; then
	printf '%s %s\n' "$commit" "$(date +%Y%m%d)" \
		> /usr/local/lib/chargecap/build-info
else
	rm -f /usr/local/lib/chargecap/build-info
fi
install -m 0755 chargecap /usr/local/bin/chargecap
install -m 0755 notifier.py /usr/local/bin/chargecap-notify
install -m 0644 chargecap.service /etc/systemd/system/chargecap.service
install -m 0644 chargecap-notify.service \
	/usr/lib/systemd/user/chargecap-notify.service
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

# the notifier is the user's own, so it can speak and show banners in their
# session; start it there when they have one, and otherwise at their next login
USER_UID=$(id -u "$USER_NAME" 2>/dev/null || true)
if [ -n "$USER_UID" ] && [ -d "/run/user/$USER_UID" ]; then
	sudo -u "$USER_NAME" env XDG_RUNTIME_DIR="/run/user/$USER_UID" \
		systemctl --user enable --now chargecap-notify.service 2>/dev/null || true
else
	sudo -u "$USER_NAME" systemctl --user enable chargecap-notify.service \
		2>/dev/null || true
fi

echo "installed. status:"
systemctl --no-pager --full status chargecap.service || true
