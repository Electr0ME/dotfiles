"""Kitty 图片预览、缩略图缓存、后台预缓存和异步预览加载。"""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time
import uuid

CACHE_DIR = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'niri-preview'
MAX_SIZE = (1000, 700)
# Kitty 可以直接读取并通过 file transfer 显示的原生格式
NATIVE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif'}
CLEAR_IMAGES = b'\x1b_Ga=d,d=A,q=2;\x1b\\'
DEVNULL = subprocess.DEVNULL


def file_key(path):
    """返回可用于预览缓存的稳定键；文件被替换后会失效。"""
    path = Path(path)
    try:
        st = path.stat()
    except OSError:
        return (str(path), 0, 0)
    return (str(path.resolve()), st.st_mtime_ns, st.st_size)


def kitty_native(path):
    value = str(path).lower()
    return value in NATIVE_SUFFIXES or Path(value).suffix in NATIVE_SUFFIXES


def _identity(path, cache_key):
    if cache_key is not None:
        return str(cache_key)
    try:
        st = Path(path).stat()
    except OSError:
        return str(path)
    return f'{Path(path).resolve()}\0{st.st_mtime_ns}\0{st.st_size}'


def _cache_path(path, cache_key=None):
    key = hashlib.sha256(
        f'{_identity(path, cache_key)}\0{MAX_SIZE[0]}x{MAX_SIZE[1]}'.encode()).hexdigest()
    return CACHE_DIR / f'{key}.png'


def cached(path, cache_key=None):
    """返回已存在的缩略图，不存在时返回 None。"""
    output = _cache_path(path, cache_key)
    return output if output.is_file() and output.stat().st_size else None


def _prune(max_files=300):
    try:
        files = sorted((p for p in CACHE_DIR.iterdir()
                        if p.is_file() and not p.name.startswith('.')),
                       key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    for path in files[:max(0, len(files) - max_files)]:
        path.unlink(missing_ok=True)


def _run_thumbnail(tool, source, target):
    if tool == 'vips':
        return subprocess.run(
            ['vipsthumbnail', '-s', f'{MAX_SIZE[0]}x{MAX_SIZE[1]}',
             '-o', str(target), str(source)],
            stdout=DEVNULL, stderr=DEVNULL)
    return subprocess.run(
        [tool, str(source), '-auto-orient', '-thumbnail',
         f'{MAX_SIZE[0]}x{MAX_SIZE[1]}>', '-strip', f'PNG:{target}'],
        stdout=DEVNULL, stderr=DEVNULL)


def thumbnail(path, cache_key=None):
    """生成并缓存适合预览的缩略图，返回 PNG 路径。

    cache_key 可提供稳定的键（例如剪贴板内容哈希），此时不依赖临时文件路径。
    """
    path = Path(path).resolve()
    try:
        path.stat()
    except OSError as error:
        raise RuntimeError(f'无法读取图片：{path}') from error

    output = _cache_path(path, cache_key)
    if output.is_file() and output.stat().st_size:
        return output

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _prune()
    temp = CACHE_DIR / f'.{output.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp.png'
    try:
        tools = [tool for tool in ('vips', 'magick', 'convert')
                 if shutil.which('vipsthumbnail' if tool == 'vips' else tool)]
        if not tools:
            raise RuntimeError('需要 libvips 或 ImageMagick 生成预览')
        for tool in tools:
            result = _run_thumbnail('vips' if tool == 'vips' else tool, path, temp)
            if result.returncode == 0 and temp.is_file() and temp.stat().st_size:
                temp.replace(output)
                return output
        raise RuntimeError('缩略图生成失败')
    finally:
        temp.unlink(missing_ok=True)


def prewarm(jobs, delay=0.2):
    """在单个后台线程中依次预生成缓存，避免抢占首次预览。"""
    def run():
        if delay:
            time.sleep(delay)
        for job in jobs:
            try:
                job()
            except Exception:  # noqa: BLE001 - 预缓存失败不影响菜单
                pass

    threading.Thread(target=run, daemon=True).start()


class ImagePreview:
    """异步调用 kitten icat，避免大图解码阻塞菜单。"""

    def __init__(self):
        self.process = None
        self.output = None
        self.data = b''
        self.message = ''
        self.replayable = False

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
        self.data, self.message = b'', ''
        try:
            _, _, px, py = struct.unpack('HHHH', fcntl.ioctl(
                sys.stdout.fileno(), termios.TIOCGWINSZ, b'\0' * 8))
        except OSError:
            px = py = 0
        size = f'{cols},{rows},{px or cols * 9},{py or rows * 20}'
        remote = bool(os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_TTY'))
        try:
            small = Path(path).stat().st_size <= 3 * 1024 * 1024
        except OSError:
            small = True
        # 缓存的缩略图总是很小；对大图首次回退时用 file，避免把整图塞进 PTY。
        transfer = 'stream' if (remote or Path(path).parent == CACHE_DIR or small) else 'file'
        self.replayable = transfer == 'stream'
        try:
            self.output = tempfile.TemporaryFile()
            self.process = subprocess.Popen(
                ['kitten', 'icat', '--stdin=no', '--transfer-mode', transfer,
                 '--use-window-size', size,
                 '--place', f'{width}x{height}@{left}x{top}',
                 '--scale-up', '--loop=0', '--image-id=4242', '--', str(path)],
                stdin=DEVNULL, stdout=self.output, stderr=DEVNULL)
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


class Loader:
    """在后台线程生成预览；首次请求可返回一个立即可用的回退内容。"""

    def __init__(self, workers=2):
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.pending = {}
        self.results = {}
        self.fallbacks = {}

    def get(self, key, function, fallback=None):
        if key in self.results:
            return self.results[key]
        future = self.pending.get(key)
        if future is None:
            value = None
            if fallback is not None:
                try:
                    value = fallback() if callable(fallback) else fallback
                except Exception:  # noqa: BLE001 - 回退失败时退回加载状态
                    value = None
                self.fallbacks[key] = value
            future = self.executor.submit(function)
            self.pending[key] = future
            if value is not None:
                return value
            return ('loading', '')
        if not future.done():
            value = self.fallbacks.get(key)
            return value if value is not None else ('loading', '')
        try:
            result = future.result()
        except Exception as error:  # noqa: BLE001 - 预览失败不应关闭菜单
            result = ('error', str(error))
        self.results[key] = result
        del self.pending[key]
        self.fallbacks.pop(key, None)
        return result

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
