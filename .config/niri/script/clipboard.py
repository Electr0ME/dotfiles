#!/usr/bin/env python3
"""Kitty TUI 剪贴板历史：cliphist 后端，支持文本和图片预览。"""
import argparse
import hashlib
import html
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPT.parent))

from lib import kitty, preview, tui

CLIPHIST = ['cliphist', '-max-items', '200']
APP_ID = 'niri-clipboard'
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir()) / 'niri-clipboard'
TEXT_LIMIT = 128 * 1024
IMAGE_MAGIC = (
    (b'\x89PNG\r\n\x1a\n', '.png', 'image/png'),
    (b'\xff\xd8\xff', '.jpg', 'image/jpeg'),
    (b'GIF87a', '.gif', 'image/gif'),
    (b'GIF89a', '.gif', 'image/gif'),
    (b'BM', '.bmp', 'image/bmp'),
    (b'II*\x00', '.tiff', 'image/tiff'),
    (b'MM\x00*', '.tiff', 'image/tiff'),
)


def notify(message):
    if shutil.which('notify-send'):
        subprocess.run(['notify-send', '剪贴板历史', message], check=False)
    else:
        print(message, file=sys.stderr)


def entries():
    result = subprocess.run(CLIPHIST + ['list'], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode:
        error = result.stderr.decode(errors='replace').strip()
        lowered = error.lower()
        if ('no such file or directory' in lowered
                or 'please store something first' in lowered
                or lowered.startswith('opening db:')):
            return []
        raise RuntimeError(error)

    rows = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        raw_id, _, text = line.partition(b'\t')
        rows.append({
            'id': raw_id.decode(errors='replace'),
            'line': line,
            'text': text.decode(errors='replace'),
        })
    return rows


def decode(entry):
    result = subprocess.run(CLIPHIST + ['decode'], input=entry['line'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip()
                           or '无法读取剪贴板内容')
    return result.stdout


def detect_mime(data):
    head = data[:65536]
    for magic, suffix, mime in IMAGE_MAGIC:
        if head.startswith(magic):
            return suffix, mime
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return '.webp', 'image/webp'
    stripped = head.lstrip()
    if stripped.startswith(b'<svg') or b'<svg' in stripped[:512].lower():
        return '.svg', 'image/svg+xml'

    if shutil.which('file'):
        result = subprocess.run(['file', '-b', '--mime-type', '-'], input=head,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        mime = result.stdout.decode(errors='replace').strip()
        if mime:
            suffix = {
                'image/png': '.png', 'image/jpeg': '.jpg', 'image/gif': '.gif',
                'image/webp': '.webp', 'image/bmp': '.bmp', 'image/svg+xml': '.svg',
                'image/tiff': '.tiff', 'image/avif': '.avif',
            }.get(mime, '.img')
            return suffix, mime
    return '', ''


def looks_text(data):
    if b'\0' in data[:65536]:
        return False
    text = data[:TEXT_LIMIT].decode('utf-8', errors='replace')
    return text.count('\ufffd') * 20 <= len(text)


def text_preview(data, mime):
    text = data[:TEXT_LIMIT].decode('utf-8', errors='replace').replace('\r\n', '\n')
    if mime == 'text/html' or 'html' in mime:
        text = re.sub(r'(?is)<(script|style).*?</\1>', '', text)
        text = re.sub(r'(?i)<br\s*/?>|</(p|div|li|tr|h[1-6]|blockquote|pre)>', '\n', text)
        text = html.unescape(re.sub(r'<[^>]+>', '', text))
    return text


def write_image(data, suffix):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=RUNTIME, prefix='clip-', suffix=suffix or '.img')
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    return Path(name)


def build_preview_from_data(entry, data):
    suffix, mime = detect_mime(data)
    if mime.startswith('image/'):
        source = write_image(data, suffix)
        try:
            return ('image', preview.thumbnail(
                source, cache_key=('clip', hashlib.sha256(data).hexdigest())))
        finally:
            source.unlink(missing_ok=True)
    if mime.startswith('text/') or mime in ('application/json', 'application/xml') \
            or (not mime and looks_text(data)):
        return ('text', text_preview(data, mime))
    return ('text', f'[{mime or "二进制数据"}] {len(data)} 字节')


def build_preview(entry):
    return build_preview_from_data(entry, decode(entry))


def image_fallback(entry, state):
    """首次选择图片时立即返回原图；缩略图仍在后台生成。"""
    if 'binary data' not in entry['text'].lower():
        return None
    try:
        data = decode(entry)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return None
    state['data'] = data
    state['hash'] = hashlib.sha256(data).hexdigest()
    suffix, mime = detect_mime(data)
    if mime.startswith('image/') and preview.kitty_native(suffix):
        state['source'] = write_image(data, suffix)
        return ('image', state['source'])
    return None


def prewarm_rows(rows, limit=8):
    jobs = []
    for entry in rows:
        if 'binary data' in entry['text'].lower() and \
                re.search(r'\b(png|jpe?g|gif|webp|bmp|avif)\b', entry['text'], re.I):
            jobs.append(lambda item=entry: build_preview(item))
            if len(jobs) >= limit:
                break
    if jobs:
        preview.prewarm(jobs, delay=0.3)


def copy_entry(entry):
    subprocess.run(['wl-copy'], input=decode(entry), check=True)


def delete_entry(entry):
    subprocess.run(CLIPHIST + ['delete'], input=entry['line'], check=True)


def wipe_history():
    subprocess.run(CLIPHIST + ['wipe'], check=True)


def run_menu(rows):
    loader = preview.Loader()

    def preview_item(entry, cols, rows):
        state = {}

        def job():
            data = state.get('data')
            if data is not None:
                source = state.get('source')
                if source is not None:
                    return ('image', preview.thumbnail(
                        source, cache_key=('clip', state['hash'])))
                return build_preview_from_data(entry, data)
            return build_preview(entry)

        return loader.get(('clip', entry['id']), job,
                          fallback=lambda: image_fallback(entry, state))

    actions = {
        '\x04': lambda entry: ('delete', entry),
        '\x18': lambda entry: ('clear', None),
    }
    footer = 'Enter 复制 · Ctrl+D 删除 · Ctrl+X 清空 · Esc 退出'

    try:
        return tui.Menu(
            rows,
            render=lambda entry: tui.sanitize(entry['text']) or '[空]',
            search=lambda entry: tui.sanitize(entry['text']),
            preview=preview_item,
            preview_ratio=0.55,
            prompt='剪贴板 ❯ ',
            footer=footer,
            key_actions=actions,
            empty='暂无历史，请先复制一些文字或图片。',
        ).run()
    finally:
        loader.close()


def interactive(action):
    prewarmed = False
    if RUNTIME.is_dir():
        for old in RUNTIME.glob('clip-*'):
            old.unlink(missing_ok=True)
    if action == 'clear':
        wipe_history()
        notify('历史已清空；当前剪贴板内容保留。')
        return

    while True:
        rows = entries()
        if not prewarmed:
            prewarm_rows(rows)
            prewarmed = True
        result = run_menu(rows)
        if result is None:
            return
        kind, payload = result
        if kind == 'select':
            copy_entry(payload)
            return
        command, entry = payload
        if command == 'delete' and entry is not None:
            delete_entry(entry)
            notify('已删除选中的历史记录。')
        elif command == 'clear':
            wipe_history()
            notify('历史已清空；当前剪贴板内容保留。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?',
                        choices=['pick', 'manage', 'delete', 'clear'],
                        default='pick')
    parser.add_argument('--show', action='store_true', help='在当前 Kitty 中运行')
    args = parser.parse_args()
    if args.show:
        interactive(args.action)
    elif args.action == 'clear':
        wipe_history()
        notify('历史已清空；当前剪贴板内容保留。')
    else:
        kitty.launch(APP_ID, '剪贴板历史', SCRIPT, ['--show'],
                     width=100, height=26, font_size=11)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        notify(f'操作失败：{error}')
        raise SystemExit(1)
