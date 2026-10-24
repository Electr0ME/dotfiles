#!/usr/bin/env python3
"""Fuzzel front end for cliphist; content is restored, never auto-typed."""
import argparse
import shutil
import subprocess
import sys

CLIPHIST = ['cliphist', '-max-items', '200']


def notify(message):
    if shutil.which('notify-send'):
        subprocess.run(['notify-send', '剪贴板历史', message], check=False)
    else:
        print(message, file=sys.stderr)


def menu(data, prompt, history=False):
    command = ['fuzzel', '--dmenu', '--only-match', '--no-sort',
               '--no-icons', '--prompt', prompt, '--width', '60', '--lines', '12']
    if history:
        # Hide numeric IDs, but return the original line for decode/delete.
        command += ['--with-nth', '2..']
    result = subprocess.run(command, input=data, stdout=subprocess.PIPE)
    if result.returncode != 0:
        return None
    return result.stdout.rstrip(b'\n') or None


def history(action):
    result = subprocess.run(CLIPHIST + ['list'], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode:
        # A new database may not exist until the first copy operation.
        if b'no such file or directory' in result.stderr:
            notify('暂无历史，请先复制一些文字或图片。')
            return
        raise RuntimeError(result.stderr.decode(errors='replace').strip())
    if not result.stdout.strip():
        notify('暂无历史，请先复制一些文字或图片。')
        return
    selected = menu(result.stdout, '删除历史 ❯ ' if action == 'delete' else '剪贴板 ❯ ', True)
    if selected is None:
        return
    if action == 'delete':
        subprocess.run(CLIPHIST + ['delete'], input=selected, check=True)
        notify('已删除选中的历史记录。')
    else:
        # Keep binary data out of shell variables and preserve trailing newlines.
        decoded = subprocess.run(CLIPHIST + ['decode'], input=selected,
                                 stdout=subprocess.PIPE, check=True)
        subprocess.run(['wl-copy'], input=decoded.stdout, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['pick', 'manage', 'delete', 'clear'], default='pick')
    action = parser.parse_args().action
    if action == 'manage':
        choice = menu('删除单条历史\n清空全部历史\n'.encode(), '管理剪贴板 ❯ ')
        if choice is None:
            return
        action = {'删除单条历史': 'delete', '清空全部历史': 'clear'}[choice.decode()]
    if action == 'clear':
        choice = menu('取消\n确认清空全部历史\n'.encode(), '确认清空？❯ ')
        if choice == '确认清空全部历史'.encode():
            subprocess.run(CLIPHIST + ['wipe'], check=True)
            # Does not change the current clipboard, avoiding accidental data loss.
            notify('历史已清空；当前剪贴板内容保留。')
    else:
        history(action)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        notify(f'操作失败：{error}')
        sys.exit(1)
