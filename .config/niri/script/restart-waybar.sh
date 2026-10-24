#!/bin/sh
# 重启当前用户的 Waybar；菜单退出后 Waybar 继续运行。
set -eu

if ! command -v waybar >/dev/null 2>&1; then
    printf '未找到 waybar，请先安装。\n' >&2
    exit 1
fi

# 如果以后改用 systemd 管理，优先交给对应服务重启。
if systemctl --user is-active --quiet waybar.service 2>/dev/null; then
    systemctl --user restart waybar.service
    printf 'Waybar 服务已重启。\n'
    exit 0
fi

if [ -z "${WAYLAND_DISPLAY:-}" ]; then
    printf '请在 Wayland 桌面会话中运行此脚本。\n' >&2
    exit 1
fi

state="${XDG_STATE_HOME:-$HOME/.local/state}/niri"
mkdir -p "$state"
# 防止连续运行时启动多个实例。
exec 9>"${XDG_RUNTIME_DIR:-$state}/niri-restart-waybar.lock"
if ! flock -n 9; then
    printf 'Waybar 正在重启，请稍候。\n'
    exit 0
fi

uid=$(id -u)
pkill -u "$uid" -x waybar || true
attempt=0
while pgrep -u "$uid" -x waybar >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 50 ]; then
        printf '旧 Waybar 未能退出，已取消启动新实例。\n' >&2
        exit 1
    fi
    sleep 0.1
done

# 关闭子进程的锁文件描述符，避免 Waybar 一直持锁。
nohup waybar >>"$state/waybar.log" 2>&1 </dev/null 9>&- &
pid=$!
sleep 1
if kill -0 "$pid" 2>/dev/null; then
    printf 'Waybar 已重启（PID：%s）。\n' "$pid"
else
    printf 'Waybar 启动失败，请查看日志：%s/waybar.log\n' "$state" >&2
    exit 1
fi
