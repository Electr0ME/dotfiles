#!/bin/sh
# Waybar 自定义 CPU 模块：保留一位小数，避免低负载时被取整成 0%。
# 同时提供负载、平均频率和封装温度的 tooltip。
set -eu

runtime="${XDG_RUNTIME_DIR:-/tmp}"
state="$runtime/waybar-cpu.state"
tmp="$state.$$"

read_cpu() {
    awk '/^cpu / {
        total = $2 + $3 + $4 + $5 + $6 + $7 + $8 + $9
        idle = $5 + $6
        print total, idle
        exit
    }' /proc/stat
}

set -- $(read_cpu)
total=$1
idle=$2

prev_total=0
prev_idle=0
have_prev=0
if [ -r "$state" ]; then
    read -r prev_total prev_idle <"$state" || true
    [ "${prev_total:-0}" -gt 0 ] && have_prev=1
fi

# 第一次运行时没有历史采样，短暂等待一次，避免首帧显示 0.0%。
if [ "$have_prev" -eq 0 ]; then
    prev_total=$total
    prev_idle=$idle
    sleep 0.2
    set -- $(read_cpu)
    total=$1
    idle=$2
fi

printf '%s %s\n' "$total" "$idle" >"$tmp"
mv -f "$tmp" "$state"

usage=$(awk -v t="$total" -v i="$idle" -v pt="$prev_total" -v pi="$prev_idle" 'BEGIN {
    dt = t - pt
    di = i - pi
    if (dt <= 0 || di < 0) {
        printf "0.0"
    } else {
        printf "%.1f", (dt - di) * 100 / dt
    }
}')

class=$(awk -v u="$usage" 'BEGIN {
    if (u >= 85) print "critical"
    else if (u >= 60) print "warning"
    else print "normal"
}')

load=$(cut -d' ' -f1-3 /proc/loadavg)

freq=$(awk '{ sum += $1; n++ } END {
    if (n > 0) printf "%.2f", sum / n / 1000000
}' /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq 2>/dev/null || true)
[ -n "${freq:-}" ] || freq="0.00"

temp=""
for d in /sys/class/hwmon/hwmon*; do
    [ -r "$d/name" ] || continue
    if [ "$(cat "$d/name")" = "coretemp" ] && [ -r "$d/temp1_input" ]; then
        temp=$(awk '{ printf "%.0f", $1 / 1000 }' "$d/temp1_input")
        break
    fi
done

tooltip="CPU 使用率: ${usage}%\\n负载: ${load}\\n平均频率: ${freq} GHz"
if [ -n "$temp" ]; then
    tooltip="${tooltip}\\n温度: ${temp}°C"
fi

printf '{"text":"%s%%","tooltip":"%s","class":"%s"}\n' \
    "$usage" "$tooltip" "$class"
