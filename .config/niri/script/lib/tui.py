"""共享 curses 菜单：CJK 宽度、搜索、滚动、预览和确认。"""
import curses
import sys
import time
import unicodedata

from . import preview


def cell_width(text):
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
               for char in text)


def clip(text, width):
    """按终端显示宽度截断文本。"""
    if width <= 0:
        return ''
    chars, used = [], 0
    for char in text:
        size = cell_width(char)
        if used + size > width:
            break
        chars.append(char)
        used += size
    return ''.join(chars)


def tail_clip(text, width):
    """从左侧截断，保留行尾（适合长路径）。"""
    if width <= 0:
        return ''
    chars, used = [], 0
    for char in reversed(text):
        size = cell_width(char)
        if used + size > width:
            break
        chars.append(char)
        used += size
    return ''.join(reversed(chars))


def sanitize(text):
    return ''.join(char if char in '\n\t' or not unicodedata.category(char).startswith('C')
                   else ' ' for char in text).replace('\t', '    ')


def wrap_text(text, width, max_lines):
    """按显示宽度换行，限制总行数。"""
    if width <= 0 or max_lines <= 0:
        return []
    lines = []
    for raw in sanitize(text).splitlines() or ['']:
        if not raw:
            lines.append('')
            if len(lines) >= max_lines:
                break
            continue
        while raw:
            chunk = clip(raw, width)
            if not chunk:
                break
            lines.append(chunk)
            raw = raw[len(chunk):]
            if len(lines) >= max_lines:
                break
        if len(lines) >= max_lines:
            break
    return lines[:max_lines]


class Menu:
    """通用菜单。

    返回：
      ('select', item)  回车选中
      ('action', value) 自定义按键返回
      None              取消
    """

    def __init__(self, items, *, render=None, search=None, preview=None,
                 preview_ratio=0.55, prompt='❯ ', footer=None,
                 key_actions=None, empty='没有匹配项', preview_delay=0.04,
                 reload=None):
        self.items = list(items)
        self.render = render or (lambda item: (str(item), ''))
        self.search = search or (lambda item: ' '.join(self.render(item)))
        self.preview = preview
        self.preview_ratio = preview_ratio
        self.prompt = prompt
        self.footer = footer
        self.key_actions = key_actions or {}
        self.empty = empty
        self.preview_delay = preview_delay
        self.reload = reload

    def run(self):
        return curses.wrapper(self._loop)

    @staticmethod
    def _put(screen, y, x, text, style=0, limit=None):
        height, width = screen.getmaxyx()
        available = max(0, width - x - 1)
        if limit is not None:
            available = min(available, limit)
        text = clip(text, available)
        if 0 <= y < height and 0 <= x < width - 1:
            try:
                screen.addstr(y, x, text, style)
            except curses.error:
                pass

    def _loop(self, screen):
        curses.set_escdelay(25)
        curses.curs_set(1)
        curses.use_default_colors()
        try:
            curses.init_pair(1, curses.COLOR_MAGENTA, -1)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
            accent = curses.color_pair(1)
            selected = curses.color_pair(2)
        except curses.error:
            accent = selected = 0
        screen.keypad(True)
        screen.timeout(50)

        query, cursor, row = '', 0, 0
        page_top = 0
        image = preview.ImagePreview()
        image_path = None
        last_frame = None
        last_preview = None
        candidate_path = None
        candidate_time = 0.0

        def raw_write(data):
            # 直接写图形协议会移动终端光标/改变 SGR；恢复 curses 认为的光标位置。
            height, width = screen.getmaxyx()
            text = query
            while text and cell_width(text) > max(0, width - 5):
                text = text[1:]
            col = min(width - 1, 3 + cell_width(text))
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.write(b'\x1b[0m')
            sys.stdout.buffer.write(f'\x1b[1;{col + 1}H'.encode())
            sys.stdout.buffer.flush()

        try:
            while True:
                height, width = screen.getmaxyx()
                footer_lines = 1 if self.footer else 0
                bottom = height - footer_lines
                page = max(1, bottom - 2)
                terms = query.casefold().split()
                visible = [item for item in self.items if all(
                    term in self.search(item).casefold() for term in terms)]
                row = max(0, min(row, len(visible) - 1))
                page_top = max(0, min(page_top, max(0, len(visible) - page)))
                if row < page_top:
                    page_top = row
                elif row >= page_top + page:
                    page_top = row - page + 1
                item = visible[row] if visible else None

                split = 0
                pcols = prows = 0
                if self.preview is not None and width >= 48 and height >= 10:
                    split = max(18, min(width - 20,
                                       int((width - 1) * (1 - self.preview_ratio))))
                    pcols = width - split - 2
                    prows = max(1, bottom - 2)

                state = None
                if item is not None and self.preview is not None and pcols > 0:
                    state = self.preview(item, pcols, prows)

                frame = (query, row, page_top, height, width, item,
                         state[0] if state else None)
                redrawn = frame != last_frame
                if redrawn:
                    screen.erase()
                    screen.redrawwin()
                    self._put(screen, 0, 1, '❯', accent)
                    text = query
                    while text and cell_width(text) > max(0, width - 5):
                        text = text[1:]
                    self._put(screen, 0, 3, text)
                    self._put(screen, 1, 0, '─' * max(0, width - 1), accent)
                    if split:
                        for y in range(2, bottom):
                            self._put(screen, y, split, '│', accent)
                    for index, entry in enumerate(visible[page_top:page_top + page],
                                                  page_top):
                        active = index == row
                        columns = self.render(entry)
                        if isinstance(columns, str):
                            columns = (columns, '')
                        left = columns[0]
                        right = columns[1] if len(columns) > 1 else ''
                        if split:
                            available = split - 3
                        else:
                            available = width - 4
                        if right:
                            column = min(38, max(12, available // 2))
                            line = left + ' ' * max(0, column - cell_width(left)) + right
                        else:
                            line = left
                        self._put(screen, 2 + index - page_top, 1,
                                  ('› ' if active else '  ') + line,
                                  selected if active else 0,
                                  available - 1)
                    if not visible:
                        self._put(screen, 2, 2, self.empty)
                    if self.footer:
                        self._put(screen, height - 1, 1, self.footer)
                    screen.move(0, min(width - 1, 3 + cell_width(text)))
                    screen.refresh()
                    last_frame = frame

                # 预览：文本直接绘制，图片交给 kitten icat。
                if state is not None and pcols > 0:
                    kind = state[0]
                    if kind == 'image':
                        path = state[1]
                        loaded = False
                        if path != image_path:
                            now = time.monotonic()
                            if path != candidate_path:
                                candidate_path, candidate_time = path, now
                            if now - candidate_time >= self.preview_delay:
                                candidate_path = None
                                image.stop()
                                image_path = path
                                last_preview = None
                                screen.refresh()
                                raw_write(preview.CLEAR_IMAGES)
                                image.start(path, pcols - 1, prows,
                                            split + 2, 2, width, height)
                                loaded = image.poll()
                        else:
                            candidate_path = None
                            loaded = image.poll()
                        if image.message:
                            self._put(screen, 2, split + 2, image.message)
                            screen.refresh()
                        if image.data and (loaded or (redrawn and image.replayable)):
                            screen.refresh()
                            raw_write(preview.CLEAR_IMAGES + image.data)
                    elif kind in ('text', 'error'):
                        candidate_path = None
                        if image_path is not None:
                            image.stop()
                            image_path = None
                            last_preview = None
                            screen.refresh()
                            raw_write(preview.CLEAR_IMAGES)
                        if redrawn or state != last_preview:
                            lines = wrap_text(state[1], pcols - 1, prows) \
                                if kind == 'text' else [state[1]]
                            for index, line in enumerate(lines):
                                self._put(screen, 2 + index, split + 2, line)
                            screen.refresh()
                            last_preview = state
                    elif kind == 'loading':
                        candidate_path = None
                        if image_path is not None:
                            image.stop()
                            image_path = None
                            last_preview = None
                            screen.refresh()
                            raw_write(preview.CLEAR_IMAGES)
                elif image_path is not None:
                    candidate_path = None
                    image.stop()
                    image_path = None
                    screen.refresh()
                    raw_write(preview.CLEAR_IMAGES)

                try:
                    key = screen.get_wch()
                except curses.error:
                    continue
                if key in ('\x00', -1):
                    continue
                if key in ('\x1b', '\x03'):
                    return None
                if key in ('\n', '\r', curses.KEY_ENTER) and item is not None:
                    return ('select', item)
                if isinstance(key, str) and key in self.key_actions and item is not None:
                    result = self.key_actions[key](item)
                    if result is not None:
                        return ('action', result)
                if key == '\x12' and self.reload is not None:
                    self.items = list(self.reload())
                    row, page_top, last_frame = 0, 0, None
                    continue
                if key == curses.KEY_UP:
                    row = max(0, row - 1)
                elif key == curses.KEY_DOWN:
                    row = min(len(visible) - 1, row + 1)
                elif key == curses.KEY_PPAGE:
                    row = max(0, row - page)
                elif key == curses.KEY_NPAGE:
                    row = min(len(visible) - 1, row + page)
                elif key == curses.KEY_HOME:
                    row = 0
                elif key == curses.KEY_END:
                    row = max(0, len(visible) - 1)
                elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                    query, cursor, row, page_top = query[:-1], 0, 0, 0
                elif key == '\x15':
                    query, cursor, row, page_top = '', 0, 0, 0
                elif isinstance(key, str) and key.isprintable():
                    query += key
                    row, page_top = 0, 0
        finally:
            image.stop()
            try:
                raw_write(preview.CLEAR_IMAGES)
            except OSError:
                pass


def confirm(message):
    """显示 y/N 确认框。"""
    def run(screen):
        curses.curs_set(0)
        curses.use_default_colors()
        height, width = screen.getmaxyx()
        text = clip(message, max(1, width - 4))
        line = max(0, (width - cell_width(text)) // 2)
        screen.erase()
        try:
            if 0 <= height // 2 < height and 0 <= line < width - 1:
                screen.addstr(height // 2, line, text, curses.A_BOLD)
            hint = '[y/N]'
            screen.addstr(height // 2 + 1,
                          max(0, (width - 5) // 2), hint)
        except curses.error:
            pass
        screen.refresh()
        try:
            return screen.get_wch() in ('y', 'Y')
        except curses.error:
            return False
    return curses.wrapper(run)
