#!/usr/bin/env python3
"""Mod+X 脚本菜单：按 menu.json 手动维护显示名称、脚本路径和参数。"""
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
APP_ID = 'niri-script-launcher'
MENU_FILE = SCRIPT.with_name('menu.json')
INTERPRETERS = {'.py': 'python3', '.sh': 'sh', '.bash': 'bash',
                '.zsh': 'zsh', '.fish': 'fish'}


def load_menu(config=MENU_FILE):
    try:
        data = json.loads(config.read_text())
    except (OSError, ValueError) as error:
        raise RuntimeError(f'无法读取菜单 {config}：{error}') from error
    if not isinstance(data, list):
        raise RuntimeError('menu.json 顶层必须是数组')
    result = []
    for index, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise RuntimeError(f'菜单第 {index} 项必须是对象')
        name, script, args = item.get('name'), item.get('script'), item.get('args', [])
        if not isinstance(name, str) or not name.strip():
            raise RuntimeError(f'菜单第 {index} 项缺少有效的 name')
        if not isinstance(script, str) or not script.strip():
            raise RuntimeError(f'菜单第 {index} 项缺少有效的 script')
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise RuntimeError(f'菜单第 {index} 项的 args 必须是字符串数组')
        if any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise RuntimeError(f'菜单第 {index} 项的 name 不能含控制字符')
        path = Path(script).expanduser()
        if not path.is_absolute():
            path = config.parent / path
        result.append({'name': name, 'path': path, 'args': args})
    return result


def command(path):
    # Honor an executable script's shebang; otherwise use its extension.
    if not path.is_file():
        raise RuntimeError(f'脚本不存在或不是文件：{path}')
    if os.access(path, os.X_OK):
        return [str(path)]
    interpreter = INTERPRETERS.get(path.suffix)
    if interpreter is None:
        raise RuntimeError(f'未知脚本类型，请添加 shebang 和可执行权限：{path}')
    if not shutil.which(interpreter):
        raise RuntimeError(f'未安装解释器：{interpreter}')
    return [interpreter, str(path)]


def cell_width(text):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in text)


def menu(screen):
    # 保留方向键解析，但不为单独的 Esc 等待默认的约一秒。
    curses.set_escdelay(25)
    curses.curs_set(1)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_MAGENTA, -1)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
    screen.keypad(True)
    query, selected, top = '', 0, 0
    items = load_menu()

    def put(y, x, text, style=0):
        h, w = screen.getmaxyx()
        chars, used = [], 0
        for char in text:
            size = cell_width(char)
            if used + size > max(0, w - x - 1):
                break
            chars.append(char)
            used += size
        if 0 <= y < h and x < w - 1:
            try:
                screen.addstr(y, x, ''.join(chars), style)
            except curses.error:
                pass

    while True:
        height, width = screen.getmaxyx()
        terms = query.casefold().split()
        visible = [item for item in items
                   if all(t in item['name'].casefold() for t in terms)]
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
        for i, item in enumerate(visible[top:top + page], top):
            active = i == selected
            put(2 + i - top, 1, ('› ' if active else '  ') + item['name'],
                curses.color_pair(2) if active else 0)
        if not visible:
            put(2, 2, '没有匹配的脚本')
        screen.move(0, min(width - 1, 3 + cell_width(text)))
        screen.refresh()
        key = screen.get_wch()
        if key in ('\x1b', '\x03'):
            return None
        if key in ('\n', '\r', curses.KEY_ENTER):
            if visible:
                return visible[selected]
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
            items = load_menu()
        elif isinstance(key, str) and key.isprintable():
            query += key
            selected, top = 0, 0


def show():
    while True:
        try:
            item = curses.wrapper(menu)
        except RuntimeError as error:
            print(f'\n{error}', flush=True)
            try:
                input('\n修正 menu.json 后按 Enter 重试，Ctrl+C 关闭…')
            except (KeyboardInterrupt, EOFError):
                return
            continue
        if item is None:
            return
        try:
            run_item(item)
        except (OSError, RuntimeError) as error:
            print(f'\n无法运行：{error}', flush=True)
            try:
                input('\n按 Enter 返回菜单，Ctrl+C 关闭…')
            except (KeyboardInterrupt, EOFError):
                return
            continue
        # 子进程已脱离当前终端，退出菜单即可关闭 Kitty。
        return


def run_item(item):
    argv = command(item['path']) + item['args']
    state = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'niri'
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'script-launcher.log').open('a') as log:
        log.write(f'\n启动：{item["name"]}\n')
        log.flush()
        return subprocess.Popen(argv, cwd=SCRIPT.parent,
                                stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)


def launch():
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
    os.execvp('kitty', ['kitty', '--class', APP_ID, '--title', 'Niri 脚本',
                       '-o', 'remember_window_size=no',
                       '-o', 'confirm_os_window_close=0',
                       '-o', 'background_opacity=1',
                       '-o', 'initial_window_width=80c',
                       '-o', 'initial_window_height=24c',
                       '-o', 'font_size=11',
                       sys.executable, str(SCRIPT), '--show'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--show', action='store_true')
    modes.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if args.list:
        for item in load_menu():
            print(f'{item["name"]}\t{item["path"]}')
    elif args.show:
        show()
    else:
        launch()


if __name__ == '__main__':
    main()
