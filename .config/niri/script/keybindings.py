#!/usr/bin/env python3
"""Niri 快捷键提示：读取 binds.kdl 中的 hotkey-overlay-title。"""
import argparse
import json
from pathlib import Path
import re
import sys

SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPT.parent))

from lib import kitty, tui

BINDS = SCRIPT.parent.parent / 'binds.kdl'
APP_ID = 'niri-keybindings'
KEY_NAMES = {
    'Mod': 'Super', 'Slash': '/', 'Return': 'Enter',
    'BracketLeft': '[', 'BracketRight': ']', 'Comma': ',', 'Period': '.',
    'Minus': '-', 'Equal': '=',
}
TITLE = re.compile(r'hotkey-overlay-title\s*=\s*("(?:\\.|[^"\\])*")')
LINE = re.compile(r'^\s*([\w+]+)\s+([^{}]*?)\{(.*)\}\s*$')


def bindings():
    rows = []
    for line in BINDS.read_text().splitlines():
        match = LINE.match(line)
        if not match:
            continue
        key, properties, _ = match.groups()
        title = TITLE.search(properties)
        if not title:
            continue
        label = json.loads(title.group(1))
        key = '+'.join(KEY_NAMES.get(part, part) for part in key.split('+'))
        rows.append({'key': key, 'label': label})
    return rows


def menu(rows):
    def render(item):
        return item['key'], item['label']

    return tui.Menu(
        rows,
        render=render,
        search=lambda item: item['key'] + ' ' + item['label'],
        prompt='❯ ',
        footer='Enter 关闭 · Esc 退出',
    ).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='只列出快捷键')
    parser.add_argument('--show', action='store_true', help='在当前 Kitty 中显示')
    args = parser.parse_args()
    rows = bindings()
    if args.list:
        width = max((len(row['key']) for row in rows), default=0)
        for row in rows:
            print(f'{row["key"]:<{width}}  {row["label"]}')
    elif args.show:
        menu(rows)
    else:
        kitty.launch(APP_ID, 'Niri 快捷键', SCRIPT, ['--show'],
                     width=90, height=20, font_size=11)


if __name__ == '__main__':
    main()
