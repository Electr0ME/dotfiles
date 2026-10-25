#!/bin/sh
# Shared entry point for manual, idle, and before-sleep locking.
# -f returns only after the screen is locked (required by swayidle -w).
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
wallpaper="$config_home/niri/wallpapers/wallpaper.png"

# Do not open another locker when already locked.
if pgrep -u "$(id -u)" -x swaylock >/dev/null 2>&1; then
    exit 0
fi

if [ -f "$wallpaper" ] && [ -r "$wallpaper" ]; then
    exec swaylock -f -C "$config_home/swaylock/config" -i "$wallpaper" "$@"
fi
# The configured solid background remains usable if no wallpaper is available.
exec swaylock -f -C "$config_home/swaylock/config" "$@"
