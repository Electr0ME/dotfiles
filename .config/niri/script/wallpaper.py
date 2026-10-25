#!/usr/bin/env python3
"""居中的 Kitty 壁纸选择器，使用缓存缩略图预览。"""
import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPT.parent))

from lib import kitty, preview, tui

WALLPAPERS = Path.home() / 'Pictures/Wallpapers'
STATE = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'niri'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
WALLPAPER = CONFIG / 'niri/wallpapers/wallpaper.png'
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.svg'}
APP_ID = 'niri-wallpaper'


def images(directory=WALLPAPERS):
    if not directory.is_dir():
        raise RuntimeError(f'壁纸目录不存在：{directory}')
    return sorted((p for p in directory.rglob('*')
                   if p.is_file() and p.suffix.lower() in EXTENSIONS
                   and '\n' not in str(p.relative_to(directory))),
                  key=lambda p: str(p.relative_to(directory)).casefold())


def choose(paths):
    loader = preview.Loader()
    preview.prewarm([lambda item=path: preview.thumbnail(item)
                     for path in paths[1:]], delay=0.25)

    def preview_item(path, cols, rows):
        hit = preview.cached(path)
        if hit is not None:
            return ('image', hit)
        fallback = ('image', path) if preview.kitty_native(path) else None
        return loader.get(preview.file_key(path),
                          lambda: ('image', preview.thumbnail(path)),
                          fallback=fallback)

    try:
        result = tui.Menu(
            paths,
            render=lambda path: str(path.relative_to(WALLPAPERS)),
            search=lambda path: str(path.relative_to(WALLPAPERS)),
            preview=preview_item,
            preview_ratio=0.6,
            prompt='壁纸 ❯ ',
            footer='Enter 应用 · Esc 取消',
        ).run()
    finally:
        loader.close()
    return result[1] if result and result[0] == 'select' else None


def install(path):
    """转换为 PNG 并替换 wallpapers/wallpaper.png。"""
    WALLPAPER.parent.mkdir(parents=True, exist_ok=True)
    temp = WALLPAPER.with_name(f'.{WALLPAPER.name}.tmp')
    try:
        if path.suffix.lower() == '.png':
            shutil.copyfile(path, temp)
        else:
            tool = shutil.which('magick') or shutil.which('convert')
            if not tool:
                raise RuntimeError('需要安装 ImageMagick（magick 或 convert）才能转换壁纸')
            result = subprocess.run(
                [tool, str(path), '-strip', '-define', 'png:compression-level=9',
                 f'PNG:{temp}'],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if result.returncode:
                lines = result.stderr.strip().splitlines()
                detail = f'：{lines[-1]}' if lines else ''
                raise RuntimeError(f'壁纸转换失败{detail}')
        temp.replace(WALLPAPER)
    finally:
        temp.unlink(missing_ok=True)


def apply(path):
    path = path.resolve()
    if not path.is_file():
        raise RuntimeError(f'壁纸不存在：{path}')
    install(path)
    STATE.mkdir(parents=True, exist_ok=True)
    existing = subprocess.run(['pgrep', '-u', str(os.getuid()), '-x', 'swaybg'],
                              capture_output=True, text=True)
    if existing.returncode not in (0, 1):
        raise RuntimeError('无法获取已有 swaybg 进程')
    old_pids = [int(pid) for pid in existing.stdout.split()]
    with (STATE / 'swaybg.log').open('a') as log:
        process = subprocess.Popen(['swaybg', '-i', str(WALLPAPER), '-m', 'fill'],
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
    print(f'已切换壁纸：{path} → {WALLPAPER}', flush=True)


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
        chosen = choose(paths)
        if chosen is not None:
            apply(chosen)
    else:
        kitty.launch(APP_ID, '选择壁纸', SCRIPT, ['--show'],
                     width=80, height=24, font_size=11)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as error:
        print(f'切换壁纸失败：{error}', flush=True)
        raise SystemExit(1)
