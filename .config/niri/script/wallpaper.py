#!/usr/bin/env python3
"""居中浮动 Kitty 壁纸选择器，使用 Kitty 图片协议预览。"""
import argparse
import curses
import fcntl
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unicodedata

WALLPAPERS = Path.home() / 'Pictures/Wallpapers'
STATE = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'niri'
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.svg'}
APP_ID = 'niri-wallpaper'
CLEAR_IMAGES = b'\x1b_Ga=d,d=A,q=2;\x1b\\'


def images(directory=WALLPAPERS):
    if not directory.is_dir():
        raise RuntimeError(f'壁纸目录不存在：{directory}')
    return sorted((p for p in directory.rglob('*')
                   if p.is_file() and p.suffix.lower() in EXTENSIONS
                   and '\n' not in str(p.relative_to(directory))),
                  key=lambda p: str(p.relative_to(directory)).casefold())


def cell_width(text):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in text)


class Preview:
    """异步解码，避免大图阻塞键盘；stdout 临时文件避免管道缓冲区死锁。"""
    def __init__(self):
        self.process = self.output = None
        self.data = b''
        self.message = ''

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process = None
        if self.output is not None:
            self.output.close()
            self.output = None

    def start(self, path, width, height, left, top, cols, rows):
        self.stop()
        self.data, self.message = b'', '加载中…'
        try:
            _, _, px, py = struct.unpack('HHHH', fcntl.ioctl(
                sys.stdout.fileno(), termios.TIOCGWINSZ, b'\0' * 8))
            # 显式提供尺寸，icat 不需要查询终端或占用 curses 的输入。
            size = f'{cols},{rows},{px or cols * 9},{py or rows * 20}'
            self.output = tempfile.TemporaryFile()
            self.process = subprocess.Popen(
                ['kitten', 'icat', '--stdin=no', '--transfer-mode=stream',
                 '--use-window-size', size, '--place', f'{width}x{height}@{left}x{top}',
                 '--scale-up', '--loop=0', '--image-id=4242', '--', str(path)],
                stdin=subprocess.DEVNULL, stdout=self.output, stderr=subprocess.DEVNULL)
        except OSError as error:
            self.stop()
            self.message = f'无法预览：{error}'

    def poll(self):
        if self.process is None or self.process.poll() is None:
            return False
        code = self.process.returncode
        self.output.seek(0)
        self.data = self.output.read() if code == 0 else b''
        self.message = '' if self.data else '此图片暂时无法预览'
        self.stop()
        return True


def choose(screen, paths):
    curses.set_escdelay(25)
    curses.curs_set(1)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_MAGENTA, -1)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
    screen.keypad(True)
    screen.timeout(50)
    query, selected, top = '', 0, 0
    preview = Preview()
    last_target, last_frame = None, None
    try:
        while True:
            height, width = screen.getmaxyx()
            split = min(30, max(12, width // 3))
            terms = query.casefold().split()
            visible = [p for p in paths if all(
                term in str(p.relative_to(WALLPAPERS)).casefold() for term in terms)]
            selected = max(0, min(selected, len(visible) - 1))
            page = max(1, height - 2)
            top = max(0, min(top, max(0, len(visible) - page)))
            top = min(top, selected)
            if selected >= top + page:
                top = selected - page + 1
            path = visible[selected] if visible else None
            target = (path, height, width)
            if target != last_target:
                if path and width > 35 and height > 5:
                    preview.start(path, width - split - 3, height - 5,
                                  split + 2, 2, width, height)
                else:
                    preview.stop()
                    preview.data, preview.message = b'', ''
                last_target = target
            loaded = preview.poll()
            frame = (query, selected, top, height, width, path)
            if frame != last_frame or loaded:
                screen.erase()

                def put(y, x, text, style=0, limit=None):
                    available = max(0, width - x - 1)
                    if limit is not None:
                        available = min(available, limit)
                    chars, used = [], 0
                    for char in text:
                        size = cell_width(char)
                        if used + size > available:
                            break
                        chars.append(char)
                        used += size
                    if 0 <= y < height and 0 <= x < width - 1:
                        try:
                            screen.addstr(y, x, ''.join(chars), style)
                        except curses.error:
                            pass

                put(0, 1, '❯', curses.color_pair(1))
                text = query
                while text and cell_width(text) > max(0, width - 5):
                    text = text[1:]
                put(0, 3, text)
                put(1, 0, '─' * max(0, width - 1), curses.color_pair(1))
                for y in range(2, height):
                    put(y, split, '│', curses.color_pair(1))
                for i, image in enumerate(visible[top:top + page], top):
                    put(2 + i - top, 1,
                        ('› ' if i == selected else '  ') + str(image.relative_to(WALLPAPERS)),
                        curses.color_pair(2) if i == selected else 0, split - 2)
                if path:
                    put(height - 2, split + 2, path.name)
                    if preview.message:
                        put(3, split + 2, preview.message)
                else:
                    put(2, 1, '没有匹配的壁纸', limit=split - 2)
                screen.move(0, min(width - 1, 3 + cell_width(text)))
                screen.refresh()
                # 使用 Kitty graphics protocol。保存/恢复光标，避免干扰搜索框。
                sys.stdout.buffer.write(CLEAR_IMAGES + b'\x1b7' + preview.data + b'\x1b8')
                sys.stdout.buffer.flush()
                last_frame = frame
            try:
                key = screen.get_wch()
            except curses.error:
                continue
            if key in ('\x1b', '\x03'):
                return None
            if key in ('\n', '\r', curses.KEY_ENTER) and path:
                return path
            if key == curses.KEY_UP:
                selected -= 1
            elif key == curses.KEY_DOWN:
                selected += 1
            elif key == curses.KEY_PPAGE:
                selected -= page
            elif key == curses.KEY_NPAGE:
                selected += page
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                query, selected, top = query[:-1], 0, 0
            elif key == '\x15':
                query, selected, top = '', 0, 0
            elif isinstance(key, str) and key.isprintable():
                query += key
                selected, top = 0, 0
    finally:
        preview.stop()
        sys.stdout.buffer.write(CLEAR_IMAGES)
        sys.stdout.buffer.flush()


def apply(path):
    path = path.resolve()
    if not path.is_file():
        raise RuntimeError(f'壁纸不存在：{path}')
    STATE.mkdir(parents=True, exist_ok=True)
    existing = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', 'swaybg'],
                              capture_output=True, text=True)
    if existing.returncode not in (0, 1):
        raise RuntimeError('无法获取已有 swaybg 进程')
    old_pids = [int(pid) for pid in existing.stdout.split()]
    with (STATE / 'swaybg.log').open('a') as log:
        process = subprocess.Popen(['swaybg', '-i', str(path), '-m', 'fill'],
                                   stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    time.sleep(0.4)
    if process.poll() is not None:
        raise RuntimeError(f'壁纸加载失败，请查看 {STATE / "swaybg.log"}')
    for pid in old_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    temp = STATE / 'wallpaper.tmp'
    temp.write_text(str(path) + '\n')
    temp.replace(STATE / 'wallpaper')
    print(f'已切换壁纸：{path}', flush=True)


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
    os.execvp('kitty', ['kitty', '--class', APP_ID, '--title', '选择壁纸',
                       '-o', 'remember_window_size=no', '-o', 'confirm_os_window_close=0',
                       '-o', 'background_opacity=1', '-o', 'initial_window_width=80c',
                       '-o', 'initial_window_height=24c', '-o', 'font_size=11',
                       sys.executable, str(Path(__file__).resolve()), '--show'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--list', action='store_true', help='只列出可选壁纸')
    mode.add_argument('--show', action='store_true', help='在当前 Kitty 中显示选择器')
    args = parser.parse_args()
    if args.list:
        for path in images():
            print(path.relative_to(WALLPAPERS))
    elif args.show:
        paths = images()
        if not paths:
            raise RuntimeError(f'目录内没有支持的图片：{WALLPAPERS}')
        STATE.mkdir(parents=True, exist_ok=True)
        runtime = Path(os.environ.get('XDG_RUNTIME_DIR') or STATE)
        with (runtime / 'niri-wallpaper.lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            chosen = curses.wrapper(choose, paths)
            if chosen is not None:
                apply(chosen)
    else:
        launch()


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f'切换壁纸失败：{error}', flush=True)
        raise SystemExit(1)
