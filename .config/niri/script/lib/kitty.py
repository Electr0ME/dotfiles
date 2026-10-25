"""启动/聚焦统一 app-id 的 Kitty 菜单窗口。"""
import json
import os
from pathlib import Path
import subprocess
import sys


def focus(app_id):
    """如果同 app-id 的窗口已存在，聚焦并返回 True。"""
    try:
        windows = json.loads(subprocess.check_output(
            ['niri', 'msg', '--json', 'windows'], text=True, timeout=3))
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    for window in windows:
        if window.get('app_id') == app_id:
            try:
                subprocess.run(
                    ['niri', 'msg', 'action', 'focus-window',
                     '--id', str(window['id'])], check=True)
            except (OSError, subprocess.SubprocessError):
                return False
            return True
    return False


def launch(app_id, title, script, args=(), *, width=80, height=24, font_size=11):
    """在 Kitty 中运行菜单脚本；已有同 app-id 窗口时只聚焦。"""
    if focus(app_id):
        return
    script = Path(script).resolve()
    os.execvp('kitty', [
        'kitty', '--class', app_id, '--title', title,
        '-o', 'remember_window_size=no',
        '-o', 'confirm_os_window_close=0',
        '-o', 'background_opacity=1',
        '-o', f'initial_window_width={width}c',
        '-o', f'initial_window_height={height}c',
        '-o', f'font_size={font_size}',
        sys.executable, str(script), *args,
    ])
