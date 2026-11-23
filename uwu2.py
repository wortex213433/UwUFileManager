import argparse
import curses
import fnmatch
import json
import locale
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pwd
except ImportError:
    pwd = None

APP = "UwU:3"
VERSION = "1.1.0"
MIN_PYTHON = (3, 11)
IS_TERMUX = "com.termux" in os.environ.get("PREFIX", "") or os.path.isdir("/data/data/com.termux")
HOME = Path.home()
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "uwu"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME") or HOME / ".local" / "share") / "uwu"
CONFIG_FILE = CONFIG_DIR / "config.json"
TRASH_DIR = DATA_DIR / "trash"

SORT_KEYS = ("name", "size", "mtime", "ext")
SORT_LABELS = {"name": "name", "size": "size", "mtime": "date", "ext": "extension"}
ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz", ".tar", ".zip")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tif", ".tiff", ".heic"}
MEDIA_EXT = {".mp3", ".mp4", ".mkv", ".wav", ".flac", ".ogg", ".avi", ".mov", ".webm", ".m4a", ".opus"}

CATEGORY_NAMES = {
    "broken": "Broken link",
    "link": "Symbolic link",
    "dir": "Folder",
    "archive": "Archive",
    "image": "Image",
    "media": "Audio / video",
    "exe": "Executable",
    "code": "File",
}

WHEEL_UP = getattr(curses, "BUTTON4_PRESSED", 0)
WHEEL_DOWN = getattr(curses, "BUTTON5_PRESSED", 0)
DBL_CLICK = getattr(curses, "BUTTON1_DOUBLE_CLICKED", 0)

MAIN_BAR = [
    ("Ctrl+Q", "Quit"),
    ("Ctrl+H", "Help"),
    ("Enter", "Open"),
    ("Space", "Select"),
    ("Ctrl+C", "Copy"),
    ("Ctrl+X", "Cut"),
    ("Ctrl+V", "Paste"),
    ("Ctrl+D", "Trash"),
    ("Ctrl+R", "Rename"),
    ("Ctrl+N", "New"),
    ("Ctrl+E", "Edit"),
    ("Ctrl+F", "Filter"),
    ("Ctrl+G", "Goto"),
    ("Ctrl+B", "Marks"),
]

HEADING = ">> "

HELP_LINES = [
    HEADING + "Quit and help",
    "Ctrl+Q or q          quit UwU:3",
    "Ctrl+H, F1 or ?      open this help page",
    "                     (Ctrl+H or F1 or ? closes it too)",
    "",
    HEADING + "Moving around",
    "Up/Down, j/k         move the cursor",
    "PgUp / PgDn          move one page",
    "Home or g / End or G first / last entry",
    "Enter, Right, l      open folder; open file with default app",
    "Left, h, Backspace   go to parent folder",
    "~                    go to your home folder",
    "-                    go back to the previous folder",
    "Ctrl+G or L          go to a typed path",
    "T                    jump to the trash folder",
    "b                    bookmark this folder (toggle)",
    "Ctrl+B or '          bookmarks list (Enter jumps, x removes)",
    "Mouse                click selects, double-click opens, wheel scrolls",
    "",
    HEADING + "Selecting",
    "Space                select or unselect, then move down",
    "a or Ctrl+A          select all entries in this folder",
    "u                    clear the selection",
    "Esc                  clear the selection, or clear the filter",
    "",
    HEADING + "File operations",
    "c or Ctrl+C          copy selection (or the current item)",
    "x or Ctrl+X          cut selection (moved on paste)",
    "p or Ctrl+V          paste into the current folder",
    "y                    duplicate in place",
    "d, Ctrl+D or Delete  move to trash (recoverable)",
    "D                    delete permanently (asks first)",
    "r, Ctrl+R or F2      rename",
    "n or Ctrl+N          create an empty file",
    "m or F7              create a folder",
    "M                    change permissions (octal, e.g. 755)",
    "Z                    compress selection into a .zip",
    "E                    extract archive (.zip, .tar, .tar.gz, .tgz ...)",
    "",
    HEADING + "Viewing and opening",
    "e, Ctrl+E or F4      edit in $EDITOR (nano, vi, ...)",
    "o                    open with default app (xdg-open / termux-open)",
    "i or F3              details panel for the current item",
    "v                    show or hide the preview pane (wide terminals)",
    "/ or Ctrl+F          live filter by name (* and ? wildcards work)",
    "s                    change sort: name, size, date, extension",
    "S                    reverse the sort order",
    "                     (the current sort is shown at the bottom right)",
    ".                    show or hide hidden files",
    "Ctrl+L or F5         refresh the folder",
    "",
    HEADING + "Running commands",
    "! or Ctrl+T          run a shell command in this folder",
    "",
    HEADING + "Notes",
    "Folders are always listed first.",
    "Selection is cleared when you change folders.",
    f"Config file: {CONFIG_FILE}",
    f"Trash folder: {TRASH_DIR}",
    "Run with --help to see command line options.",
]


@dataclass
class Config:
    show_hidden: bool = False
    sort_key: str = "name"
    sort_reverse: bool = False
    preview: bool = True
    bookmarks: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cfg
        if not isinstance(data, dict):
            return cfg
        cfg.show_hidden = bool(data.get("show_hidden", cfg.show_hidden))
        cfg.sort_reverse = bool(data.get("sort_reverse", cfg.sort_reverse))
        cfg.preview = bool(data.get("preview", cfg.preview))
        key = data.get("sort_key", cfg.sort_key)
        cfg.sort_key = key if key in SORT_KEYS else "name"
        marks = data.get("bookmarks", [])
        if isinstance(marks, list):
            cfg.bookmarks = [m for m in marks if isinstance(m, str)]
        return cfg

    def save(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")
        except OSError:
            pass


def ctrl(letter: str) -> int:
    return ord(letter) & 0x1F


K_ENTER = (10, 13, curses.KEY_ENTER)
K_ESC = 27
K_HELP = (ctrl("h"), curses.KEY_BACKSPACE, curses.KEY_F1, ord("?"))
K_PARENT = (curses.KEY_LEFT, ord("h"), 127)
K_TEXT_BACK = (127, 8, curses.KEY_BACKSPACE)


@dataclass
class Entry:
    path: Path
    name: str
    is_dir: bool = False
    is_link: bool = False
    is_exe: bool = False
    broken: bool = False
    size: int = 0
    mtime: float = 0.0
    mode: int = 0
    uid: int = 0
    link_target: str = ""

    @property
    def ext(self) -> str:
        return "" if self.is_dir else Path(self.name).suffix.lower()


def make_entry(path: Path) -> Entry:
    try:
        lst = os.lstat(path)
    except OSError:
        return Entry(path=path, name=path.name, broken=True)

    st = lst
    is_link = stat.S_ISLNK(lst.st_mode)
    target = ""
    broken = False
    if is_link:
        try:
            target = os.readlink(path)
        except OSError:
            target = "?"
        try:
            st = os.stat(path)
        except OSError:
            broken = True

    is_dir = (not broken) and stat.S_ISDIR(st.st_mode)
    is_exe = (not broken) and (not is_dir) and bool(st.st_mode & 0o111)
    return Entry(
        path=path,
        name=path.name,
        is_dir=is_dir,
        is_link=is_link,
        is_exe=is_exe,
        broken=broken,
        size=0 if is_dir else st.st_size,
        mtime=st.st_mtime,
        mode=st.st_mode,
        uid=st.st_uid,
        link_target=target,
    )


def read_dir(path: Path, show_hidden: bool) -> tuple[list[Entry], str]:
    items: list[Entry] = []
    try:
        with os.scandir(path) as it:
            for de in it:
                if not show_hidden and de.name.startswith("."):
                    continue
                items.append(make_entry(path / de.name))
    except PermissionError:
        return [], "Permission denied"
    except OSError as ex:
        return [], ex.strerror or str(ex)
    return items, ""


def sort_entries(items: list[Entry], key: str, reverse: bool) -> list[Entry]:
    def keyfn(e: Entry):
        if key == "size":
            return (e.size, e.name.lower())
        if key == "mtime":
            return (e.mtime, e.name.lower())
        if key == "ext":
            return (e.ext, e.name.lower())
        return e.name.lower()

    dirs = sorted((e for e in items if e.is_dir), key=keyfn, reverse=reverse)
    files = sorted((e for e in items if not e.is_dir), key=keyfn, reverse=reverse)
    return dirs + files


def is_archive_name(name: str) -> bool:
    return name.lower().endswith(ARCHIVE_SUFFIXES)


def archive_base(name: str) -> str:
    low = name.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if low.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return Path(name).stem or name


def category(e: Entry) -> str:
    if e.broken:
        return "broken"
    if e.is_link:
        return "link"
    if e.is_dir:
        return "dir"
    if is_archive_name(e.name):
        return "archive"
    if e.ext in IMAGE_EXT:
        return "image"
    if e.ext in MEDIA_EXT:
        return "media"
    if e.is_exe:
        return "exe"
    return "code"


def display_name(e: Entry) -> str:
    if e.broken:
        return f"{e.name} -> {e.link_target} [broken]"
    if e.is_link:
        return f"{e.name} -> {e.link_target}"
    if e.is_dir:
        return e.name + "/"
    if e.is_exe:
        return e.name + "*"
    return e.name


def is_regular(path: Path) -> bool:
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError:
        return False


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    value = float(n)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024
        if value < 1024:
            return f"{value:.1f} {unit}"
    return f"{value / 1024:.1f} PB"


def fmt_time(t: float) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))
    except (OverflowError, OSError, ValueError):
        return "?"


def owner_name(uid: int) -> str:
    if pwd is not None:
        try:
            return pwd.getpwuid(uid).pw_name
        except KeyError:
            pass
    return str(uid)


def trunc(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return text[:1]
    return text[: width - 1] + "~"


def unique_dest(dest: Path) -> Path:
    if not os.path.lexists(dest):
        return dest
    stem, suffix = dest.stem, dest.suffix
    for n in range(1, 10000):
        candidate = dest.with_name(f"{stem} ({n}){suffix}")
        if not os.path.lexists(candidate):
            return candidate
    raise OSError("too many items with this name")


def transfer(sources: list[Path], dst_dir: Path, move: bool) -> tuple[int, list[str]]:
    done = 0
    errors: list[str] = []
    dst_abs = os.path.abspath(dst_dir)
    dst_real = os.path.realpath(dst_dir)
    for src in sources:
        try:
            if move and os.path.dirname(os.path.abspath(src)) == dst_abs:
                errors.append(f"{src.name}: already in this folder")
                continue
            src_real = os.path.realpath(src)
            if src.is_dir() and not src.is_symlink() and (
                dst_real == src_real or dst_real.startswith(src_real + os.sep)
            ):
                errors.append(f"{src.name}: cannot put a folder inside itself")
                continue
            target = unique_dest(dst_dir / src.name)
            if move:
                shutil.move(str(src), str(target))
            elif src.is_dir() and not src.is_symlink():
                shutil.copytree(src, target, symlinks=True)
            else:
                shutil.copy2(src, target, follow_symlinks=False)
            done += 1
        except (OSError, shutil.Error) as ex:
            errors.append(f"{src.name}: {ex}")
    return done, errors


def delete_path(path: Path, permanent: bool) -> None:
    in_trash = os.path.abspath(path.parent) == str(TRASH_DIR)
    if permanent or in_trash:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        return
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(unique_dest(TRASH_DIR / path.name)))


def dir_size(path: Path, cap: int = 20000) -> tuple[int, bool]:
    total = 0
    seen = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
            seen += 1
            if seen >= cap:
                return total, True
    return total, False


def make_zip(paths: list[Path], dest: Path) -> None:
    dest_abs = os.path.abspath(dest)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            base = p.parent
            if p.is_dir() and not p.is_symlink():
                for root, _dirs, files in os.walk(p):
                    rel_root = os.path.relpath(root, base)
                    z.write(root, rel_root)
                    for name in files:
                        full = os.path.join(root, name)
                        if os.path.abspath(full) == dest_abs:
                            continue
                        z.write(full, os.path.join(rel_root, name))
            else:
                z.write(p, p.name)


def extract_archive(path: Path, dest_dir: Path) -> tuple[bool, str]:
    target = unique_dest(dest_dir / archive_base(path.name))
    try:
        if zipfile.is_zipfile(path):
            target.mkdir()
            with zipfile.ZipFile(path) as z:
                z.extractall(target)
        elif tarfile.is_tarfile(path):
            target.mkdir()
            with tarfile.open(path) as t:
                if hasattr(tarfile, "data_filter"):
                    t.extractall(target, filter="data")
                else:
                    t.extractall(target)
        else:
            return False, f"{path.name}: not a supported archive"
    except (OSError, zipfile.BadZipFile, tarfile.TarError, EOFError, ValueError) as ex:
        shutil.rmtree(target, ignore_errors=True)
        return False, f"{path.name}: {ex}"
    return True, f"{path.name} -> {target.name}/"


def is_binary(path: Path, sample: int = 2048) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(sample)
    except OSError:
        return True


def preview_lines(e: Entry, limit: int) -> list[str]:
    if limit < 1:
        return []
    if e.broken:
        return ["(broken symbolic link)", f"-> {e.link_target}"]
    if e.is_dir:
        items, err = read_dir(e.path, False)
        if err:
            return [err]
        out = [f"{len(items)} item(s) inside:"]
        out += [display_name(it) for it in sort_entries(items, "name", False)]
        return out[:limit]
    if not is_regular(e.path):
        return ["(special file - no preview)"]
    if e.size == 0:
        return ["(empty file)"]
    if is_binary(e.path):
        return [f"(binary file, {human_size(e.size)})"]
    out: list[str] = []
    try:
        with open(e.path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                out.append(line.rstrip("\r\n").replace("\t", "    "))
    except OSError as ex:
        return [str(ex)]
    return out


def opener_command() -> list[str] | None:
    if IS_TERMUX and shutil.which("termux-open"):
        return ["termux-open"]
    if shutil.which("xdg-open"):
        return ["xdg-open"]
    return None


def _wput(win, y: int, x: int, text: str, attr: int = 0, width: int | None = None) -> None:
    H, W = win.getmaxyx()
    if y < 0 or y >= H or x < 0 or x >= W - 1:
        return
    n = W - 1 - x if width is None else min(width, W - 1 - x)
    if n <= 0:
        return
    try:
        win.addnstr(y, x, text, n, attr)
    except curses.error:
        pass


def _plain(line: str) -> str:
    return line[len(HEADING):] if line.startswith(HEADING) else line


class App:
    MIN_H = 10
    MIN_W = 40

    def __init__(self, scr, cfg: Config, start: Path):
        self.scr = scr
        self.cfg = cfg
        self.cwd = start
        self.all_entries: list[Entry] = []
        self.entries: list[Entry] = []
        self.cursor = 0
        self.top = 0
        self.selected: set[Path] = set()
        self.clip: tuple[list[Path], bool] | None = None
        self.filter = ""
        self.history: list[Path] = []
        self.msg = ""
        self.msg_kind = "info"
        self.list_top = 1
        self.list_h = 10
        self.list_w = 40
        self.preview_x = 0
        self.attrs: dict[str, int] = {}

        self._init_terminal()
        self.reload()
        self.flash(f"Welcome to {APP}! Press Ctrl+H for help.", "ok")

    def _init_terminal(self) -> None:
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        try:
            curses.raw()
        except curses.error:
            pass
        self.scr.keypad(True)
        try:
            curses.mousemask(curses.ALL_MOUSE_EVENTS)
        except curses.error:
            pass
        self.init_colors()

    def init_colors(self) -> None:
        self.attrs = {
            "header": curses.A_REVERSE | curses.A_BOLD,
            "keys": curses.A_REVERSE,
            "cursor": curses.A_REVERSE,
            "dir": curses.A_BOLD,
            "exe": curses.A_BOLD,
            "selected": curses.A_UNDERLINE | curses.A_BOLD,
            "accent": curses.A_BOLD,
            "dim": curses.A_DIM,
            "ok": curses.A_BOLD,
            "warn": curses.A_BOLD,
            "error": curses.A_BOLD,
            "broken": curses.A_BOLD,
        }
        if not curses.has_colors():
            return
        try:
            curses.start_color()
        except curses.error:
            return
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK

        C = curses
        spec = {
            "header": (C.COLOR_BLACK, C.COLOR_MAGENTA, C.A_BOLD),
            "keys": (C.COLOR_BLACK, C.COLOR_CYAN, C.A_BOLD),
            "cursor": (C.COLOR_BLACK, C.COLOR_WHITE, 0),
            "dir": (C.COLOR_CYAN, bg, C.A_BOLD),
            "link": (C.COLOR_MAGENTA, bg, 0),
            "broken": (C.COLOR_RED, bg, C.A_BOLD),
            "exe": (C.COLOR_GREEN, bg, C.A_BOLD),
            "archive": (C.COLOR_YELLOW, bg, 0),
            "image": (C.COLOR_BLUE, bg, 0),
            "media": (C.COLOR_MAGENTA, bg, C.A_BOLD),
            "code": (-1, bg, 0),
            "selected": (C.COLOR_YELLOW, bg, C.A_BOLD),
            "ok": (C.COLOR_GREEN, bg, C.A_BOLD),
            "warn": (C.COLOR_YELLOW, bg, C.A_BOLD),
            "error": (C.COLOR_RED, bg, C.A_BOLD),
            "accent": (C.COLOR_MAGENTA, bg, C.A_BOLD),
            "dim": (C.COLOR_WHITE, bg, C.A_DIM),
        }
        for pair_no, (name, (fg, back, extra)) in enumerate(spec.items(), start=1):
            try:
                curses.init_pair(pair_no, fg, back)
            except curses.error:
                continue
            self.attrs[name] = curses.color_pair(pair_no) | extra

    def a(self, name: str) -> int:
        return self.attrs.get(name, 0)

    def flash(self, text: str, kind: str = "info") -> None:
        self.msg = text
        self.msg_kind = kind

    def get_key(self):
        try:
            k = self.scr.get_wch()
        except curses.error:
            return -1
        except KeyboardInterrupt:
            return ctrl("q")
        if isinstance(k, str):
            return ord(k) if ord(k) < 128 else k
        return k

    def prompt(self, label: str, initial: str = "", live=None) -> str | None:
        buf = list(initial)
        pos = len(buf)
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        try:
            while True:
                self.draw()
                H, W = self.scr.getmaxyx()
                y = H - 3
                self.put(y, 0, " " * (W - 1), self.a("keys"))
                self.put(y, 1, label, self.a("accent"))
                col = 1 + len(label)
                self.put(y, col, "".join(buf), 0)
                try:
                    self.scr.move(y, min(col + pos, W - 2))
                except curses.error:
                    pass
                self.scr.noutrefresh()
                curses.doupdate()

                k = self.get_key()
                if k == -1:
                    continue
                if k in K_ENTER:
                    return "".join(buf)
                if k == K_ESC:
                    return None
                if k in K_TEXT_BACK:
                    if pos > 0:
                        del buf[pos - 1]
                        pos -= 1
                elif k == curses.KEY_DC:
                    if pos < len(buf):
                        del buf[pos]
                elif k == curses.KEY_LEFT:
                    pos = max(0, pos - 1)
                elif k == curses.KEY_RIGHT:
                    pos = min(len(buf), pos + 1)
                elif k in (curses.KEY_HOME, ctrl("a")):
                    pos = 0
                elif k in (curses.KEY_END, ctrl("e")):
                    pos = len(buf)
                elif k == ctrl("u"):
                    buf.clear()
                    pos = 0
                elif isinstance(k, int) and 32 <= k < 127:
                    buf.insert(pos, chr(k))
                    pos += 1
                elif isinstance(k, str):
                    buf.insert(pos, k)
                    pos += 1
                else:
                    continue
                if live is not None:
                    live("".join(buf))
        finally:
            try:
                curses.curs_set(0)
            except curses.error:
                pass

    def confirm(self, question: str) -> bool:
        answer = self.prompt(f"{question} [y/N] ")
        return answer is not None and answer.strip().lower() in ("y", "yes")

    def modal(self, title: str, lines: list[str], selectable: bool = False,
              footer: str = "q / Esc closes") -> tuple[str, int]:
        idx = 0
        top = 0
        while True:
            self.draw()
            H, W = self.scr.getmaxyx()
            longest = max((len(_plain(line)) for line in lines), default=0)
            width = max(20, min(W - 4, max(longest, len(title), len(footer)) + 6))
            height = max(5, min(H - 2, len(lines) + 4))
            body_h = max(1, height - 3)
            max_top = max(0, len(lines) - body_h)

            if selectable:
                if idx < top:
                    top = idx
                if idx >= top + body_h:
                    top = idx - body_h + 1
            else:
                top = idx
            top = max(0, min(top, max_top))
            if not selectable:
                idx = top

            try:
                win = curses.newwin(height, width, max(0, (H - height) // 2), max(0, (W - width) // 2))
            except curses.error:
                return ("close", -1)
            win.keypad(True)
            win.erase()
            win.box()
            _wput(win, 0, 2, f" {title} ", self.a("accent"))
            for row in range(body_h):
                li = top + row
                if li >= len(lines):
                    break
                raw = lines[li]
                attr = self.a("accent") if raw.startswith(HEADING) else 0
                if selectable and li == idx:
                    attr = self.a("cursor")
                _wput(win, 1 + row, 2, _plain(raw).ljust(width - 4), attr, width - 4)
            _wput(win, height - 2, 2, footer, self.a("dim"), width - 4)
            win.noutrefresh()
            curses.doupdate()

            k = self.get_key()
            if k in (K_ESC, ord("q")) or k in K_HELP:
                return ("close", -1)
            if k in K_ENTER:
                if selectable and lines:
                    return ("enter", idx)
                return ("close", -1)
            if k in (curses.KEY_UP, ord("k")):
                idx -= 1
            elif k in (curses.KEY_DOWN, ord("j")):
                idx += 1
            elif k == curses.KEY_PPAGE:
                idx -= body_h
            elif k == curses.KEY_NPAGE:
                idx += body_h
            elif k == curses.KEY_HOME:
                idx = 0
            elif k == curses.KEY_END:
                idx = len(lines) - 1
            elif k in (ord("x"), curses.KEY_DC) and selectable and lines:
                return ("delete", idx)
            idx = max(0, min(idx, max(0, len(lines) - 1)))

    def show_help(self) -> None:
        self.modal("UwU:3 Help", HELP_LINES, footer="Up/Down scroll  |  q / Esc / Ctrl+H closes")

    def show_info(self) -> None:
        e = self.current()
        if e is None:
            return
        if e.is_dir:
            total, capped = dir_size(e.path)
            size_line = f"{human_size(total)} ({total:,} bytes)"
            if capped:
                size_line += "  (partial: very large folder)"
        else:
            size_line = f"{human_size(e.size)} ({e.size:,} bytes)"
        mode = stat.S_IMODE(e.mode)
        lines = [
            HEADING + "Details",
            f"Name       {e.name}",
            f"Path       {e.path}",
            f"Type       {CATEGORY_NAMES.get(category(e), 'File')}",
            f"Size       {size_line}",
            f"Modified   {fmt_time(e.mtime)}",
            f"Mode       {stat.filemode(e.mode)}  ({mode:04o})",
            f"Owner      {owner_name(e.uid)}  (uid {e.uid})",
        ]
        if e.is_link:
            lines += ["", HEADING + "Symbolic link", f"Points to  {e.link_target}"]
        if e.broken:
            lines.append("Status     BROKEN - the target does not exist")
        self.modal(f"Info: {trunc(e.name, 40)}", lines)

    def put(self, y: int, x: int, text: str, attr: int = 0, width: int | None = None) -> None:
        _wput(self.scr, y, x, text, attr, width)

    def draw(self) -> None:
        scr = self.scr
        scr.erase()
        H, W = scr.getmaxyx()
        if H < self.MIN_H or W < self.MIN_W:
            self.put(0, 0, "Terminal too small - please make the window bigger")
            scr.noutrefresh()
            return

        self.list_h = max(1, H - 6)
        self.list_top = 1
        preview = self.cfg.preview and W >= 90
        if preview:
            self.list_w = (W * 55) // 100
            self.preview_x = self.list_w + 2
        else:
            self.list_w = W
            self.preview_x = W
        self.ensure_visible()

        self.draw_header(W)
        self.draw_list(W)
        if preview:
            self.draw_preview(W, H)
        self.draw_info(W, H)
        self.draw_status(W, H)
        self.draw_bar(W, H)
        scr.noutrefresh()

    def ensure_visible(self) -> None:
        if self.cursor < self.top:
            self.top = self.cursor
        if self.cursor >= self.top + self.list_h:
            self.top = self.cursor - self.list_h + 1
        self.top = max(0, min(self.top, max(0, len(self.entries) - self.list_h)))

    def draw_header(self, W: int) -> None:
        head = self.a("header")
        self.put(0, 0, " " * (W - 1), head)
        left = f" {APP} "
        self.put(0, 0, left, head)
        right = f" {len(self.entries)} items "
        if self.filter:
            right = f" {len(self.entries)} matches for '{self.filter}' "
        room = W - len(left) - len(right) - 2
        path = str(self.cwd)
        if len(path) > room:
            path = ("..." + path[-(room - 3):]) if room > 4 else ""
        self.put(0, len(left), " " + path, head, max(0, room + 1))
        self.put(0, max(len(left), W - 1 - len(right)), right, head)

    def draw_list(self, W: int) -> None:
        width = self.list_w
        cols: list[int] = []
        if width >= 72:
            cols = [9, 16, 10]
        elif width >= 48:
            cols = [9]
        meta_w = sum(cols) + 2 * len(cols)
        name_w = max(4, width - 2 - meta_w)

        for row in range(self.list_h):
            y = self.list_top + row
            idx = self.top + row
            if idx >= len(self.entries):
                self.put(y, 0, " " * (width - 1))
                continue
            e = self.entries[idx]
            if idx == self.cursor:
                attr = self.a("cursor")
            elif e.path in self.selected:
                attr = self.a("selected")
            else:
                attr = self.a(category(e))
            mark = "+" if e.path in self.selected else " "
            line = f"{mark} {trunc(display_name(e), name_w).ljust(name_w)}"
            if cols:
                size_txt = "<DIR>" if e.is_dir else human_size(e.size)
                parts = [size_txt.rjust(9)]
                if len(cols) == 3:
                    parts.append(fmt_time(e.mtime).ljust(16))
                    parts.append(stat.filemode(e.mode).ljust(10))
                line += "  " + "  ".join(parts)
            self.put(y, 0, line.ljust(width), attr, width)

        if not self.entries:
            note = "(no matches for the filter)" if self.filter else "(empty folder)"
            self.put(self.list_top, 2, note, self.a("dim"))

    def draw_preview(self, W: int, H: int) -> None:
        try:
            self.scr.vline(1, self.list_w, curses.ACS_VLINE, H - 6, self.a("dim"))
        except curses.error:
            pass
        e = self.current()
        if e is None:
            return
        x = self.preview_x
        pw = W - x - 1
        self.put(1, x, f" {trunc(e.name, pw - 2)} ", self.a("accent"), pw)
        for i, line in enumerate(preview_lines(e, self.list_h - 1)):
            self.put(2 + i, x, line, self.a("dim") if e.is_dir else 0, pw)

    def draw_info(self, W: int, H: int) -> None:
        try:
            self.scr.hline(H - 5, 0, curses.ACS_HLINE, W - 1, self.a("dim"))
        except curses.error:
            pass
        parts = []
        e = self.current()
        if e is not None:
            size = "<DIR>" if e.is_dir else human_size(e.size)
            parts.append(f"{stat.filemode(e.mode)}  {owner_name(e.uid)}  {size}  {fmt_time(e.mtime)}")
        if self.selected:
            parts.append(f"{len(self.selected)} selected")
        if self.clip:
            paths, move = self.clip
            parts.append(f"clipboard: {len(paths)} to {'move' if move else 'copy'}")
        try:
            parts.append(f"free {human_size(shutil.disk_usage(self.cwd).free)}")
        except OSError:
            pass
        self.put(H - 4, 1, trunc("  |  ".join(parts), W - 3), self.a("dim"))

    def draw_status(self, W: int, H: int) -> None:
        y = H - 3
        self.put(y, 0, " " * (W - 1))
        state = (
            f" sort: {SORT_LABELS[self.cfg.sort_key]} "
            f"{'desc' if self.cfg.sort_reverse else 'asc'}"
            f" | hidden: {'on' if self.cfg.show_hidden else 'off'}"
            f" | preview: {'on' if self.cfg.preview else 'off'} "
        )
        room = max(0, W - len(state) - 3)
        if self.msg:
            text, kind = self.msg, self.msg_kind
        else:
            text, kind = "Ready. Press Ctrl+H for help.", "dim"
        self.put(y, 1, trunc(text, room), self.a(kind), room)
        self.put(y, max(1, W - 1 - len(state)), state, self.a("keys"))

    def draw_bar(self, W: int, H: int) -> None:
        rows = [H - 2, H - 1]
        row = 0
        x = 0
        for key, label in MAIN_BAR:
            seg = len(key) + len(label) + 3
            if x + seg > W - 2:
                row += 1
                x = 0
            if row >= len(rows):
                break
            y = rows[row]
            self.put(y, x, key, self.a("keys"))
            self.put(y, x + len(key), f" {label}", 0)
            x += seg + 1

    def current(self) -> Entry | None:
        return self.entries[self.cursor] if self.entries else None

    def move(self, delta: int) -> None:
        if not self.entries:
            return
        self.cursor = max(0, min(len(self.entries) - 1, self.cursor + delta))

    def reload(self, keep: str | None = None) -> None:
        items, err = read_dir(self.cwd, self.cfg.show_hidden)
        self.all_entries = items
        self.apply_view(keep)
        if err:
            self.flash(err, "error")

    def apply_view(self, keep: str | None = None) -> None:
        items = self.all_entries
        if self.filter:
            pattern = self.filter.lower()
            if not any(c in pattern for c in "*?["):
                pattern = f"*{pattern}*"
            items = [e for e in items if fnmatch.fnmatch(e.name.lower(), pattern)]
        self.entries = sort_entries(items, self.cfg.sort_key, self.cfg.sort_reverse)
        if keep is not None:
            for i, e in enumerate(self.entries):
                if e.name == keep:
                    self.cursor = i
                    break
        self.cursor = max(0, min(self.cursor, len(self.entries) - 1))

    def keep_current(self) -> str | None:
        e = self.current()
        return e.name if e else None

    def chdir(self, path: Path, remember: bool = True) -> None:
        target = Path(os.path.abspath(os.path.expanduser(str(path))))
        if not target.is_dir():
            self.flash(f"Not a folder: {target}", "error")
            return
        if target == self.cwd:
            return
        if remember:
            self.history.append(self.cwd)
        self.cwd = target
        self.cursor = 0
        self.top = 0
        self.selected.clear()
        self.filter = ""
        self.reload()
        if not self.msg_kind == "error":
            self.flash("")

    def go_back(self) -> None:
        if not self.history:
            self.flash("No previous folder", "warn")
            return
        self.chdir(self.history.pop(), remember=False)

    def open_current(self) -> None:
        e = self.current()
        if e is None:
            return
        if e.broken:
            self.flash("Broken symbolic link - nothing to open", "error")
        elif e.is_dir:
            self.chdir(e.path)
        else:
            self.open_external(e.path)

    def open_external(self, path: Path) -> None:
        cmd = opener_command()
        if cmd is None:
            self.edit_file(path)
            return
        try:
            subprocess.Popen(
                cmd + [str(path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self.flash(f"Opened {path.name}", "ok")
        except OSError as ex:
            self.flash(f"Could not open: {ex}", "error")

    def edit_file(self, path: Path) -> None:
        if not is_regular(path):
            self.flash("Only regular files can be edited", "warn")
            return
        editor = os.environ.get("EDITOR") or ("nano" if shutil.which("nano") else "vi")
        try:
            argv = shlex.split(editor) + [str(path)]
        except ValueError as ex:
            self.flash(f"Bad $EDITOR: {ex}", "error")
            return
        self.run_foreground(argv)
        self.reload(keep=path.name)

    def edit_current(self) -> None:
        e = self.current()
        if e is None:
            return
        if e.is_dir:
            self.flash("Folders cannot be edited - select a file", "warn")
            return
        self.edit_file(e.path)

    def run_foreground(self, argv: list[str], cwd: str | None = None, pause: bool = False) -> None:
        error = ""
        curses.def_prog_mode()
        curses.endwin()
        try:
            try:
                subprocess.call(argv, cwd=cwd)
            except OSError as ex:
                error = str(ex)
            if pause:
                input("\nPress Enter to return to UwU:3...")
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            curses.reset_prog_mode()
            self.scr.clear()
            self.scr.refresh()
        if error:
            self.flash(f"Could not run: {error}", "error")

    def targets(self) -> list[Path]:
        chosen = sorted(p for p in self.selected if os.path.lexists(p))
        if chosen:
            return chosen
        e = self.current()
        return [e.path] if e else []

    def toggle_select(self) -> None:
        e = self.current()
        if e is None:
            return
        if e.path in self.selected:
            self.selected.discard(e.path)
        else:
            self.selected.add(e.path)
        self.move(1)

    def select_all(self) -> None:
        self.selected = {e.path for e in self.entries}
        self.flash(f"Selected {len(self.selected)} item(s)", "ok")

    def clip_to(self, move: bool) -> None:
        paths = self.targets()
        if not paths:
            self.flash("Nothing to take", "warn")
            return
        self.clip = (paths, move)
        self.selected.clear()
        verb = "Cut" if move else "Copied"
        self.flash(f"{verb} {len(paths)} item(s). Go to a folder and press Ctrl+V / p.", "ok")

    def paste(self) -> None:
        if not self.clip:
            self.flash("Clipboard is empty", "warn")
            return
        paths, move = self.clip
        paths = [p for p in paths if os.path.lexists(p)]
        if not paths:
            self.clip = None
            self.flash("The items on the clipboard no longer exist", "error")
            return
        done, errors = transfer(paths, self.cwd, move)
        if move:
            self.clip = None
        self.selected.clear()
        self.reload()
        if errors:
            self.flash("; ".join(errors[:2]), "error")
        else:
            self.flash(f"{'Moved' if move else 'Pasted'} {done} item(s)", "ok")

    def delete(self, permanent: bool) -> None:
        paths = self.targets()
        if not paths:
            return
        what = f"{len(paths)} item(s)"
        question = f"PERMANENTLY delete {what}?" if permanent else f"Move {what} to trash?"
        if not self.confirm(question):
            self.flash("Cancelled", "warn")
            return
        done = 0
        errors: list[str] = []
        for p in paths:
            try:
                delete_path(p, permanent)
                done += 1
            except OSError as ex:
                errors.append(f"{p.name}: {ex}")
        self.selected.clear()
        self.reload()
        if errors:
            self.flash("; ".join(errors[:2]), "error")
        elif permanent:
            self.flash(f"Deleted {done} item(s) permanently", "warn")
        else:
            self.flash(f"Moved {done} item(s) to trash", "ok")

    def rename(self) -> None:
        e = self.current()
        if e is None:
            return
        new = self.prompt("Rename to: ", e.name)
        if not new or new == e.name:
            return
        if "/" in new:
            self.flash("A name cannot contain '/'", "error")
            return
        dst = self.cwd / new
        if os.path.lexists(dst):
            self.flash(f"'{new}' already exists", "error")
            return
        try:
            os.rename(e.path, dst)
        except OSError as ex:
            self.flash(str(ex), "error")
            return
        self.reload(keep=new)
        self.flash(f"Renamed to {new}", "ok")

    def new_item(self, is_dir: bool) -> None:
        name = self.prompt("New folder: " if is_dir else "New file: ")
        if not name:
            return
        dst = self.cwd / name
        if os.path.lexists(dst):
            self.flash(f"'{name}' already exists", "error")
            return
        try:
            if is_dir:
                os.makedirs(dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                with open(dst, "x", encoding="utf-8"):
                    pass
        except OSError as ex:
            self.flash(str(ex), "error")
            return
        self.reload(keep=Path(name).parts[0])
        self.flash(f"Created {name}", "ok")

    def duplicate(self) -> None:
        paths = self.targets()
        if not paths:
            return
        done, errors = transfer(paths, self.cwd, move=False)
        self.selected.clear()
        self.reload()
        if errors:
            self.flash("; ".join(errors[:2]), "error")
        else:
            self.flash(f"Duplicated {done} item(s)", "ok")

    def chmod(self) -> None:
        paths = self.targets()
        if not paths:
            return
        text = self.prompt("Permissions (octal, e.g. 755): ", "")
        if not text:
            return
        try:
            mode = int(text, 8)
        except ValueError:
            self.flash("Not an octal number", "error")
            return
        if not 0 <= mode <= 0o7777:
            self.flash("Permissions must be between 0 and 7777", "error")
            return
        failed = []
        for p in paths:
            try:
                os.chmod(p, mode)
            except OSError:
                failed.append(p.name)
        self.reload()
        if failed:
            self.flash(f"Could not change: {', '.join(failed[:3])}", "error")
        else:
            self.flash(f"Permissions set to {mode:o}", "ok")

    def extract(self) -> None:
        archives = [p for p in self.targets() if is_archive_name(p.name)]
        if not archives:
            self.flash("No archive selected (.zip, .tar, .tar.gz, .tgz ...)", "warn")
            return
        results = [extract_archive(p, self.cwd) for p in archives]
        self.selected.clear()
        self.reload()
        bad = [msg for ok, msg in results if not ok]
        if bad:
            self.flash("; ".join(bad[:2]), "error")
        else:
            self.flash("Extracted: " + "; ".join(msg for _, msg in results[:2]), "ok")

    def compress(self) -> None:
        paths = self.targets()
        if not paths:
            return
        default = (paths[0].name if len(paths) == 1 else "archive") + ".zip"
        name = self.prompt("Archive name: ", default)
        if not name:
            return
        dest = unique_dest(self.cwd / name)
        try:
            make_zip(paths, dest)
        except OSError as ex:
            self.flash(f"Compress failed: {ex}", "error")
            return
        self.selected.clear()
        self.reload(keep=dest.name)
        self.flash(f"Created {dest.name}", "ok")

    def goto(self) -> None:
        text = self.prompt("Go to: ", str(self.cwd))
        if not text:
            return
        target = Path(os.path.expanduser(text))
        if not target.is_absolute():
            target = self.cwd / target
        self.chdir(target)

    def go_trash(self) -> None:
        TRASH_DIR.mkdir(parents=True, exist_ok=True)
        self.chdir(TRASH_DIR)

    def start_filter(self) -> None:
        before = self.filter

        def live(text: str) -> None:
            self.filter = text
            self.apply_view()

        result = self.prompt("Filter: ", self.filter, live=live)
        if result is None:
            self.filter = before
        self.apply_view()
        self.flash(f"Filter: {self.filter}" if self.filter else "Filter cleared", "ok")

    def toggle_bookmark(self) -> None:
        here = str(self.cwd)
        if here in self.cfg.bookmarks:
            self.cfg.bookmarks.remove(here)
            self.flash("Bookmark removed", "warn")
        else:
            self.cfg.bookmarks.append(here)
            self.flash("Bookmarked this folder", "ok")
        self.cfg.save()

    def bookmark_menu(self) -> None:
        while True:
            if not self.cfg.bookmarks:
                self.flash("No bookmarks yet - press b to bookmark this folder", "warn")
                return
            action, idx = self.modal(
                "Bookmarks", self.cfg.bookmarks, selectable=True,
                footer="Enter jumps  |  x removes  |  Esc closes",
            )
            if action == "enter":
                self.chdir(Path(self.cfg.bookmarks[idx]))
                return
            if action == "delete":
                del self.cfg.bookmarks[idx]
                self.cfg.save()
                continue
            return

    def shell(self) -> None:
        cmd = self.prompt("Shell command: ")
        if not cmd:
            return
        shell = os.environ.get("SHELL") or "/bin/sh"
        self.run_foreground([shell, "-c", cmd], cwd=str(self.cwd), pause=True)
        self.reload()
        self.flash("Back from the shell", "ok")

    def cycle_sort(self) -> None:
        i = SORT_KEYS.index(self.cfg.sort_key)
        self.cfg.sort_key = SORT_KEYS[(i + 1) % len(SORT_KEYS)]
        self.apply_view(self.keep_current())
        self.flash(f"Sorted by {SORT_LABELS[self.cfg.sort_key]}", "ok")

    def reverse_sort(self) -> None:
        self.cfg.sort_reverse = not self.cfg.sort_reverse
        self.apply_view(self.keep_current())
        self.flash("Sort order: " + ("descending" if self.cfg.sort_reverse else "ascending"), "ok")

    def on_mouse(self) -> None:
        try:
            _, mx, my, _, state = curses.getmouse()
        except curses.error:
            return
        if state & WHEEL_UP:
            self.move(-3)
            return
        if state & WHEEL_DOWN:
            self.move(3)
            return
        if self.list_top <= my < self.list_top + self.list_h and mx < self.list_w:
            idx = self.top + (my - self.list_top)
            if 0 <= idx < len(self.entries):
                self.cursor = idx
                if state & DBL_CLICK:
                    self.open_current()

    def dispatch(self, k) -> bool:
        if k in (ctrl("q"), ord("q")):
            return False
        if k in K_HELP:
            self.show_help()
        elif k in (curses.KEY_UP, ord("k")):
            self.move(-1)
        elif k in (curses.KEY_DOWN, ord("j")):
            self.move(1)
        elif k == curses.KEY_PPAGE:
            self.move(-self.list_h)
        elif k == curses.KEY_NPAGE:
            self.move(self.list_h)
        elif k in (curses.KEY_HOME, ord("g")):
            self.cursor = 0
        elif k in (curses.KEY_END, ord("G")):
            self.cursor = max(0, len(self.entries) - 1)
        elif k in K_ENTER or k in (curses.KEY_RIGHT, ord("l")):
            self.open_current()
        elif k in K_PARENT:
            self.chdir(self.cwd.parent)
        elif k == ord("~"):
            self.chdir(HOME)
        elif k == ord("-"):
            self.go_back()
        elif k == ord(" "):
            self.toggle_select()
        elif k in (ord("a"), ctrl("a")):
            self.select_all()
        elif k == ord("u"):
            self.selected.clear()
            self.flash("Selection cleared", "ok")
        elif k == K_ESC:
            if self.selected:
                self.selected.clear()
                self.flash("Selection cleared", "ok")
            elif self.filter:
                self.filter = ""
                self.apply_view(self.keep_current())
                self.flash("Filter cleared", "ok")
        elif k in (ord("c"), ctrl("c")):
            self.clip_to(move=False)
        elif k in (ord("x"), ctrl("x")):
            self.clip_to(move=True)
        elif k in (ord("p"), ctrl("v")):
            self.paste()
        elif k in (ord("d"), ctrl("d"), curses.KEY_DC):
            self.delete(permanent=False)
        elif k == ord("D"):
            self.delete(permanent=True)
        elif k in (ord("r"), ctrl("r"), curses.KEY_F2):
            self.rename()
        elif k in (ord("n"), ctrl("n")):
            self.new_item(is_dir=False)
        elif k in (ord("m"), curses.KEY_F7):
            self.new_item(is_dir=True)
        elif k == ord("y"):
            self.duplicate()
        elif k in (ord("e"), ctrl("e"), curses.KEY_F4):
            self.edit_current()
        elif k == ord("o"):
            e = self.current()
            if e is not None and not e.is_dir:
                self.open_external(e.path)
        elif k in (ord("i"), curses.KEY_F3):
            self.show_info()
        elif k == ord("v"):
            self.cfg.preview = not self.cfg.preview
            self.flash(f"Preview {'shown' if self.cfg.preview else 'hidden'}", "ok")
        elif k in (ord("/"), ctrl("f")):
            self.start_filter()
        elif k == ord("s"):
            self.cycle_sort()
        elif k == ord("S"):
            self.reverse_sort()
        elif k == ord("."):
            self.cfg.show_hidden = not self.cfg.show_hidden
            self.reload(keep=self.keep_current())
            self.flash(f"Hidden files {'shown' if self.cfg.show_hidden else 'hidden'}", "ok")
        elif k in (ord("L"), ctrl("g")):
            self.goto()
        elif k == ord("b"):
            self.toggle_bookmark()
        elif k in (ord("'"), ctrl("b")):
            self.bookmark_menu()
        elif k == ord("T"):
            self.go_trash()
        elif k in (ord("!"), ctrl("t")):
            self.shell()
        elif k == ord("E"):
            self.extract()
        elif k == ord("Z"):
            self.compress()
        elif k == ord("M"):
            self.chmod()
        elif k in (ctrl("l"), curses.KEY_F5):
            self.reload(keep=self.keep_current())
            self.flash("Refreshed", "ok")
        elif k == curses.KEY_MOUSE:
            self.on_mouse()
        return True

    def run(self) -> None:
        while True:
            self.draw()
            curses.doupdate()
            k = self.get_key()
            if k == -1:
                continue
            if not self.dispatch(k):
                break


def parse_args(argv: list[str] | None):
    parser = argparse.ArgumentParser(
        prog="uwu2.py",
        description="UwU:3 - a stylish, detailed terminal file manager for Linux and Termux.",
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="folder to open (default: the current folder)")
    parser.add_argument("--hidden", action="store_true", help="show hidden files at start")
    parser.add_argument("--no-preview", action="store_true", help="start with the preview pane hidden")
    parser.add_argument("-V", "--version", action="version", version=f"{APP} {VERSION}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"UwU:3 needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.", file=sys.stderr)
        return 1

    args = parse_args(argv)
    start = Path(os.path.expanduser(args.path))
    if not start.is_dir():
        print(f"uwu: not a folder: {args.path}", file=sys.stderr)
        return 1

    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    os.environ.setdefault("ESCDELAY", "25")

    cfg = Config.load()
    if args.hidden:
        cfg.show_hidden = True
    if args.no_preview:
        cfg.preview = False
    start_dir = Path(os.path.abspath(start))

    def runner(scr):
        App(scr, cfg, start_dir).run()

    try:
        curses.wrapper(runner)
    except curses.error as ex:
        print(f"uwu: terminal error: {ex}", file=sys.stderr)
        return 1
    finally:
        cfg.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
