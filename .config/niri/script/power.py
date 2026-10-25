#!/usr/bin/env python3
"""电源选项：锁屏、挂起、休眠、重启、关机与退出 Niri。

在浮动 Kitty 中以 curses 菜单运行；危险操作通过确认菜单二次确认。
锁屏、挂起和休眠统一走 lock.sh，确保操作前已经锁定会话。
"""
import argparse
import curses
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata

SCRIPT = Path(__file__).resolve()
LOCK = SCRIPT.parent.parent / 'lock.sh'
APP_ID = 'niri-power'

ACTIONS = [
    {'id': 'lock', 'name': '锁屏', 'detail': '立即锁定当前会话'},
    {'id': 'suspend', 'name': '挂起', 'detail': '锁屏后进入睡眠，按电源键唤醒'},
    {'id': 'hibernate', 'name': '休眠', 'detail': '锁屏后将会话保存到磁盘'},
    {'id': 'reboot', 'name': '重启', 'detail': '重新启动计算机'},
    {'id': 'poweroff', 'name': '关机', 'detail': '关闭计算机'},
    {'id': 'logout', 'name': '退出 Niri', 'detail': '结束当前 Wayland 会话'},
]
DESTRUCTIVE = {'reboot', 'poweroff', 'logout'}


def notify(message):
    if shutil.which('notify-send'):
        subprocess.run(['notify-send', '电源选项', message], check=False)
    else:
        print(message, file=sys.stderr)


def power_states():
    try:
        return set(Path('/sys/power/state').read_text().split())
    except OSError:
        return set()


def reason_unavailable(action, states):
    """返回不可用原因；可用时返回 None。只做只读检查，不执行任何动作。"""
    if action == 'lock':
        if not LOCK.is_file():
            return '未找到 lock.sh'
        if not shutil.which('swaylock'):
            return '未找到 swaylock'
        return None
    if action == 'logout':
        if not shutil.which('niri'):
            return '未找到 niri 命令'
        return None
    if not shutil.which('systemctl'):
        return '未找到 systemctl'
    if action == 'suspend' and states and 'mem' not in states:
        return '当前系统不支持挂起'
    if action == 'hibernate':
        if states and 'disk' not in states:
            return '当前系统未启用休眠'
        try:
            swap = Path('/proc/swaps').read_text().splitlines()[1:]
        except OSError:
            swap = []
        if not swap:
            return '未检测到交换空间，无法休眠'
    return None


def available_actions(states):
    return [action for action in ACTIONS
            if reason_unavailable(action['id'], states) is None]


def cell_width(text):
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
               for char in text)


def menu(screen, states):
    # 保留方向键解析，但不为单独的 Esc 等待默认的约一秒。
    curses.set_escdelay(25)
    curses.curs_set(1)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_MAGENTA, -1)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
    screen.keypad(True)
    query, selected, top = '', 0, 0
    items = available_actions(states)
    pending = None

    def put(y, x, text, style=0):
        height, width = screen.getmaxyx()
        chars, used = [], 0
        for char in text:
            size = cell_width(char)
            if used + size > max(0, width - x - 1):
                break
            chars.append(char)
            used += size
        if 0 <= y < height and 0 <= x < width - 1:
            try:
                screen.addstr(y, x, ''.join(chars), style)
            except curses.error:
                pass

    while True:
        height, width = screen.getmaxyx()
        rows = items if pending is None else [
            {'id': 'cancel', 'name': '取消'},
            {'id': pending['id'], 'name': '确认' + pending['name']},
        ]
        terms = query.casefold().split()
        visible = [item for item in rows
                   if all(term in item['name'].casefold() for term in terms)]
        selected = max(0, min(selected, len(visible) - 1))
        page = max(1, height - 2)
        top = max(0, min(top, max(0, len(visible) - page)))
        if selected < top:
            top = selected
        elif selected >= top + page:
            top = selected - page + 1
        screen.erase()
        put(0, 1, '❯', curses.color_pair(1))
        text = query
        while text and cell_width(text) > max(0, width - 5):
            text = text[1:]
        put(0, 3, text)
        put(1, 0, '─' * max(0, width - 1), curses.color_pair(1))
        for index, item in enumerate(visible[top:top + page], top):
            active = index == selected
            put(2 + index - top, 1,
                ('› ' if active else '  ') + item['name'],
                curses.color_pair(2) if active else 0)
        if not visible:
            put(2, 2, '没有匹配的操作')
        screen.move(0, min(width - 1, 3 + cell_width(text)))
        screen.refresh()
        key = screen.get_wch()
        if key in ('\x1b', '\x03'):
            if pending is not None:
                pending, query, selected, top = None, '', 0, 0
                continue
            return None
        if key in ('\n', '\r', curses.KEY_ENTER):
            if not visible:
                continue
            chosen = visible[selected]
            if chosen['id'] == 'cancel':
                pending, query, selected, top = None, '', 0, 0
            elif pending is not None:
                return chosen['id']
            elif chosen['id'] in DESTRUCTIVE:
                pending, query, selected, top = chosen, '', 0, 0
            else:
                return chosen['id']
        elif key == curses.KEY_UP:
            selected = max(0, selected - 1)
        elif key == curses.KEY_DOWN:
            selected = min(len(visible) - 1, selected + 1)
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - page)
        elif key == curses.KEY_NPAGE:
            selected = min(len(visible) - 1, selected + page)
        elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
            query, selected, top = query[:-1], 0, 0
        elif key == '\x15':
            query, selected, top = '', 0, 0
        elif key == '\x12':
            items = available_actions(power_states())
        elif isinstance(key, str) and key.isprintable():
            query += key
            selected, top = 0, 0


def perform(action):
    if action in ('lock', 'suspend', 'hibernate'):
        # lock.sh 返回时屏幕已经锁定；再执行挂起/休眠可避免内容泄露。
        subprocess.run(['sh', str(LOCK)], check=True)
    if action == 'suspend':
        subprocess.run(['systemctl', 'suspend'], check=True)
    elif action == 'hibernate':
        subprocess.run(['systemctl', 'hibernate'], check=True)
    elif action == 'reboot':
        subprocess.run(['systemctl', 'reboot'], check=True)
    elif action == 'poweroff':
        subprocess.run(['systemctl', 'poweroff'], check=True)
    elif action == 'logout':
        subprocess.run(['niri', 'msg', 'action', 'quit', '--skip-confirmation'],
                       check=True)


def launch():
    # 重复触发时聚焦已有窗口，而不是叠加多个电源菜单。
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
    os.execvp('kitty', ['kitty', '--class', APP_ID, '--title', '电源选项',
                       '-o', 'remember_window_size=no',
                       '-o', 'confirm_os_window_close=0',
                       '-o', 'background_opacity=1',
                       '-o', 'initial_window_width=80c',
                       '-o', 'initial_window_height=24c',
                       '-o', 'font_size=11',
                       sys.executable, str(SCRIPT), '--show'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--show', action='store_true', help='在当前 Kitty 中显示菜单')
    mode.add_argument('--list', action='store_true', help='只列出电源操作')
    args = parser.parse_args()
    states = power_states()
    if args.list:
        for action in ACTIONS:
            reason = reason_unavailable(action['id'], states)
            print(f'{action["name"]:<8} {reason or action["detail"]}')
    elif args.show:
        action = curses.wrapper(menu, states)
        if action is not None:
            try:
                perform(action)
            except (OSError, subprocess.CalledProcessError) as error:
                notify(f'操作失败：{error}')
                sys.exit(1)
    else:
        launch()


if __name__ == '__main__':
    main()
