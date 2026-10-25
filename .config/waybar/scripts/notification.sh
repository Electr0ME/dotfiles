#!/bin/sh
# Waybar 通知图标：显示 mako 的勿扰模式状态。
# 左键切换勿扰模式。
set -eu

if makoctl mode 2>/dev/null | grep -qx 'do-not-disturb'; then
    icon='󰂛'
    class='dnd'
    tooltip='勿扰模式：开\n左键关闭勿扰'
else
    icon='󰂚'
    class='none'
    tooltip='勿扰模式：关\n左键开启勿扰'
fi

printf '{"text":"%s","tooltip":"%s","class":"%s"}\n' \
    "$icon" "$tooltip" "$class"
