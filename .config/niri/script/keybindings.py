#!/usr/bin/env python3
"""Niri 快捷键提示：默认启动浮动 Kitty；--show 显示列表；--list 输出文本。

从同目录上一级的 binds.kdl 读取当前的一行式快捷键定义。
优先使用 hotkey-overlay-title，否则将 Niri 动作翻译为中文。
不执行配置中的任何命令。依赖仅为 Python 标准库、Kitty 和 Niri。
"""
import argparse
import curses
import json
import os
from pathlib import Path
import re
import subprocess
import unicodedata

SCRIPT = Path(__file__).resolve()
BINDS = SCRIPT.parent.parent / 'binds.kdl'
APP_ID = 'niri-keybindings'

DESCRIPTIONS = {
    'show-hotkey-overlay': '快捷键帮助',
    'toggle-overview': '切换工作区总览',
    'close-window': '关闭窗口',
    'focus-column-left': '聚焦左侧列', 'focus-column-right': '聚焦右侧列',
    'focus-window-down': '聚焦下方窗口', 'focus-window-up': '聚焦上方窗口',
    'move-column-left': '向左移动列', 'move-column-right': '向右移动列',
    'move-window-down': '向下移动窗口', 'move-window-up': '向上移动窗口',
    'focus-column-first': '聚焦第一列', 'focus-column-last': '聚焦最后一列',
    'move-column-to-first': '移动到第一列', 'move-column-to-last': '移动到最后一列',
    'focus-workspace-down': '切换到下方工作区',
    'focus-workspace-up': '切换到上方工作区',
    'move-column-to-workspace-down': '将列移到下方工作区',
    'move-column-to-workspace-up': '将列移到上方工作区',
    'move-workspace-down': '向下移动工作区', 'move-workspace-up': '向上移动工作区',
    'focus-workspace-previous': '返回上个工作区',
    'consume-or-expel-window-left': '向左合并 / 拆出窗口',
    'consume-or-expel-window-right': '向右合并 / 拆出窗口',
    'consume-window-into-column': '将右侧窗口合并到当前列',
    'expel-window-from-column': '从当前列拆出窗口',
    'switch-preset-column-width': '切换预设列宽',
    'switch-preset-column-width-back': '反向切换预设列宽',
    'switch-preset-window-height': '切换预设窗口高度',
    'reset-window-height': '重置窗口高度',
    'maximize-column': '切换列最大化', 'fullscreen-window': '切换全屏',
    'maximize-window-to-edges': '切换无边距最大化',
    'expand-column-to-available-width': '将列扩展到剩余可用宽度',
    'center-column': '居中当前列', 'center-visible-columns': '居中可见列',
    'toggle-window-floating': '切换悬浮 / 平铺',
    'switch-focus-between-floating-and-tiling': '在悬浮与平铺之间切换焦点',
    'toggle-column-tabbed-display': '切换列的标签页模式',
    'screenshot': '区域截图', 'screenshot-screen': '全屏截图',
    'screenshot-window': '窗口截图',
    'toggle-keyboard-shortcuts-inhibit': '切换快捷键抑制',
    'quit': '退出 Niri（需确认）', 'power-off-monitors': '关闭显示器',
}
KEY_NAMES = {
    'Mod': 'Super', 'Slash': '/', 'Return': 'Enter',
    'BracketLeft': '[', 'BracketRight': ']', 'Comma': ',', 'Period': '.',
    'Minus': '-', 'Equal': '=',
}


def description(body):
    action = body.strip().rstrip(';').strip()
    name = action.split()[0] if action else ''
    if name in DESCRIPTIONS:
        return DESCRIPTIONS[name]
    for prefix, label in [('focus-monitor-', '聚焦显示器'),
                          ('move-column-to-monitor-', '将列移到显示器')]:
        if name.startswith(prefix):
            direction = {'left': '左侧', 'right': '右侧', 'up': '上方', 'down': '下方'}
            return label + ' · ' + direction.get(name[len(prefix):], name[len(prefix):])
    for prefix, label in [('focus-workspace ', '切换到工作区 '),
                          ('move-column-to-workspace ', '将列移到工作区 '),
                          ('set-column-width ', '调整列宽 '),
                          ('set-window-height ', '调整窗口高度 ')]:
        if action.startswith(prefix):
            return label + action[len(prefix):].strip('"')
    if 'wpctl set-volume' in action:
        return '增加音量' if '0.1+' in action else '降低音量'
    if 'wpctl set-mute' in action:
        return '切换麦克风静音' if 'SOURCE' in action else '切换音量静音'
    for command, label in [('playerctl play-pause', '播放 / 暂停'),
                           ('playerctl stop', '停止播放'),
                           ('playerctl previous', '上一曲'),
                           ('playerctl next', '下一曲')]:
        if command in action:
            return label
    if 'brightnessctl' in action:
        return '增加亮度' if '+10%' in action else '降低亮度'
    return action


def bindings():
    rows = []
    # 当前 binds.kdl 每条绑定占一行；跳过 // 与 /- 注释行。
    pattern = re.compile(r'^\s*([\w+]+)\s+([^{}]*?)\{(.*)\}\s*(?://.*)?$')
    title_pattern = re.compile(r'hotkey-overlay-title\s*=\s*("(?:\\.|[^"\\])*")')
    for line in BINDS.read_text().splitlines():
        match = pattern.match(line)
        if not match:
            continue
        key, properties, body = match.groups()
        title = title_pattern.search(properties)
        label = json.loads(title.group(1)) if title else description(body)
        key = '+'.join(KEY_NAMES.get(part, part) for part in key.split('+'))
        rows.append((key, label))
    return rows


def cell_width(text):
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
               for char in text)


def filtered_rows(rows, query):
    # Space-separated terms can match either the key combination or description.
    terms = query.casefold().split()
    return [row for row in rows
            if all(term in ' '.join(row).casefold() for term in terms)]


def viewer(screen, rows):
    # 降低 Esc 转义序列等待时间，避免关闭窗口时停顿。
    curses.set_escdelay(25)
    curses.curs_set(1)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_MAGENTA, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)
    screen.keypad(True)
    top, query, cursor = 0, '', 0

    def put(y, x, text, style=0, limit=None):
        height, width = screen.getmaxyx()
        available = max(0, width - x - 1)
        if limit is not None:
            available = min(available, limit)
        clipped, used = [], 0
        for char in text:
            size = cell_width(char)
            if used + size > available:
                break
            clipped.append(char)
            used += size
        if 0 <= y < height and x < width - 1:
            try:
                screen.addstr(y, x, ''.join(clipped), style)
            except curses.error:
                pass

    while True:
        height, width = screen.getmaxyx()
        visible = filtered_rows(rows, query)
        page = max(1, height - 2)
        top = min(max(0, top), max(0, len(visible) - page))
        screen.erase()
        put(0, 1, '❯', curses.color_pair(1) | curses.A_BOLD)
        # Keep the insertion point visible even for long Chinese searches.
        left = 0
        while left < cursor and cell_width(query[left:cursor]) > max(0, width - 5):
            left += 1
        put(0, 3, query[left:])
        put(1, 0, '─' * max(0, width - 1), curses.color_pair(1))
        column = min(38, max(12, width // 2))
        for index, (key, label) in enumerate(visible[top:top + page]):
            put(2 + index, 1, key, curses.color_pair(2), column - 2)
            put(2 + index, column, label)
        if height > 0 and width > 0:
            screen.move(0, min(width - 1, 3 + cell_width(query[left:cursor])))
        screen.refresh()
        key = screen.get_wch()
        old_query = query
        if key in ('\x1b', '\x03'):
            return
        if key == curses.KEY_DOWN:
            top += 1
        elif key == curses.KEY_UP:
            top -= 1
        elif key == curses.KEY_NPAGE:
            top += page
        elif key == curses.KEY_PPAGE:
            top -= page
        elif key == curses.KEY_LEFT:
            cursor = max(0, cursor - 1)
        elif key == curses.KEY_RIGHT:
            cursor = min(len(query), cursor + 1)
        elif key == curses.KEY_HOME:
            cursor = 0
        elif key == curses.KEY_END:
            cursor = len(query)
        elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
            if cursor:
                query = query[:cursor - 1] + query[cursor:]
                cursor -= 1
        elif key == curses.KEY_DC:
            query = query[:cursor] + query[cursor + 1:]
        elif key == '\x15':  # Ctrl+U
            query, cursor = '', 0
        elif key == '\x12':  # Ctrl+R
            rows = bindings()
        elif isinstance(key, str) and key.isprintable():
            query = query[:cursor] + key + query[cursor:]
            cursor += len(key)
        if query != old_query:
            top = 0


def launch():
    # Reuse an existing help window rather than piling up terminals.
    try:
        windows = json.loads(subprocess.check_output(
            ['niri', 'msg', '--json', 'windows'], text=True, timeout=3))
        for window in windows:
            if window.get('app_id') == APP_ID:
                subprocess.run(['niri', 'msg', 'action', 'focus-window',
                                '--id', str(window['id'])], check=True)
                return
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    os.execvp('kitty', ['kitty', '--class', APP_ID, '--title', 'Niri 快捷键',
                       '-o', 'remember_window_size=no',
                       '-o', 'confirm_os_window_close=0',
                       '-o', 'background_opacity=1',
                       '-o', 'initial_window_width=80c',
                       '-o', 'initial_window_height=24c',
                       '-o', 'font_size=11',
                       'python3', str(SCRIPT), '--show'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--show', action='store_true')
    mode.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if args.list:
        for key, label in bindings():
            print(f'{key:<36} {label}')
    elif args.show:
        curses.wrapper(viewer, bindings())
    else:
        launch()


if __name__ == '__main__':
    main()
