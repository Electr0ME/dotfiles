#!/bin/sh
# Only launched by niri. Do not enable these globally in the GNOME session.
state="${XDG_STATE_HOME:-$HOME/.local/state}/niri"
mkdir -p "$state" "$HOME/Pictures/Screenshots"
start() {
    name=$1; shift
    if ! pgrep -u "$(id -u)" -x "$name" >/dev/null 2>&1; then
        "$@" >>"$state/$name.log" 2>&1 &
    fi
}
start waybar waybar
# mako 取代 swaync 作为通知守护进程；先停掉旧服务，避免 D-Bus 名称冲突。
systemctl --user stop swaync.service >>"$state/notifications.log" 2>&1 || true
start mako mako
# Session-scoped service; stops with niri and is not enabled for GNOME.
systemctl --user start niri-clipboard.service >>"$state/clipboard.log" 2>&1
wallpaper="$HOME/.config/niri/wallpapers/mocha.png"
if [ -r "$state/wallpaper" ]; then
    IFS= read -r saved_wallpaper < "$state/wallpaper" || true
    if [ -f "$saved_wallpaper" ]; then
        wallpaper=$saved_wallpaper
    fi
fi
start swaybg swaybg -i "$wallpaper" -m fill
# fcitx5 is already provided by XDG autostart in a full niri session.
# niri >=25.08 starts xwayland-satellite on demand, so do not start it twice.
start polkit-gnome-au /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
start swayidle sh "$HOME/.config/niri/idle.sh"
