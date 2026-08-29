#!/usr/bin/env python3
"""Build per-monitor Kingdom Age screensaver text from RSS/Atom feeds."""

from __future__ import annotations

import hashlib
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

CACHE = Path.home() / ".cache/omarchy/kingdom-age-screensaver"
TTL = 900
DEFAULT_FEEDS = [
    "https://wizwam.com/quotes/rss",
    "https://wizwam.com/news/rss",
]
FALLBACK_VERSES = Path.home() / ".config/omarchy/branding/screensaver.txt"
THEME_VERSES = Path.home() / ".config/omarchy/themes/kingdom-age/screensaver.txt"
UA = "KingdomAgeScreensaver/1.0 (+https://github.com/lukejmorrison/lukesomarchythemes)"


def localname(tag: str) -> str:
    return tag.split("}")[-1] if tag else ""


def strip_html(s: str) -> str:
    s = unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return strip_html("".join(el.itertext()))


def load_feed_urls() -> list[str]:
    for path in (
        Path.home() / ".config/omarchy/branding/screensaver-feeds.txt",
        Path.home() / ".config/omarchy/themes/kingdom-age/screensaver-feeds.txt",
        Path.home() / ".config/omarchy/themes/1-kingdom-age-v2/screensaver-feeds.txt",
    ):
        if not path.is_file():
            continue
        urls = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
        if urls:
            return urls
    return list(DEFAULT_FEEDS)


def parse_feed(xml_bytes: bytes) -> list[tuple[str, str]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    items: list[tuple[str, str]] = []
    for el in root.iter():
        ln = localname(el.tag)
        if ln not in ("item", "entry"):
            continue
        title = desc = ""
        for child in el:
            cl = localname(child.tag)
            if cl == "title":
                title = text_of(child)
            elif cl in ("description", "summary", "content"):
                if not desc:
                    desc = text_of(child)
        if title or desc:
            items.append((title[:180], desc[:360]))
    return items


def fetch(url: str, timeout: float = 5.0) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def read_blob(blob: Path) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if not blob.is_file():
        return items
    for block in blob.read_text(encoding="utf-8", errors="replace").split("\n---\n"):
        lines = block.strip().splitlines()
        if lines:
            items.append((lines[0], " ".join(lines[1:])))
    return items


def cached_items(urls: list[str]) -> list[tuple[str, str]]:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1("\n".join(urls).encode()).hexdigest()[:16]
    blob = CACHE / f"items-{key}.txt"
    now = time.time()
    if blob.is_file() and now - blob.stat().st_mtime < TTL:
        fresh = read_blob(blob)
        if fresh:
            return fresh

    items: list[tuple[str, str]] = []
    for url in urls:
        raw = fetch(url)
        if not raw:
            continue
        items.extend(parse_feed(raw))

    if items:
        parts = [title + ("\n" + desc if desc else "") for title, desc in items]
        blob.write_text("\n---\n".join(parts) + "\n", encoding="utf-8")
        return items
    return read_blob(blob)


def fallback_text() -> str:
    for path in (FALLBACK_VERSES, THEME_VERSES):
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return "KINGDOM AGE\n\nThey shall sit every man under his vine and under his fig tree."


# Visible pad so Matrix resolve does not hide leftover cells (it drops ASCII space).
GRID_FILL = "·"


def char_width(ch: str) -> int:
    o = ord(ch)
    if ch in "\n\r":
        return 0
    if o < 32:
        return 0
    # CJK / fullwidth ranges that would overflow a column.
    if (
        0x1100 <= o <= 0x115F
        or 0x2329 <= o <= 0x232A
        or 0x2E80 <= o <= 0xA4CF
        or 0xAC00 <= o <= 0xD7A3
        or 0xF900 <= o <= 0xFAFF
        or 0xFE10 <= o <= 0xFE6F
        or 0xFF00 <= o <= 0xFF60
        or 0xFFE0 <= o <= 0xFFE6
    ):
        return 2
    return 1


def display_width(text: str) -> int:
    return sum(char_width(ch) for ch in text)


def wrap(text: str, width: int = 72) -> str:
    return "\n".join(wrap_lines(text, width))


def wrap_lines(text: str, width: int) -> list[str]:
    width = max(8, int(width))
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        if display_width(cur) + 1 + display_width(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def clip_row(text: str, cols: int) -> str:
    out: list[str] = []
    w = 0
    for ch in text.replace("\t", " ").replace("\r", ""):
        if ch == "\n":
            break
        cw = char_width(ch)
        if cw <= 0:
            continue
        if w + cw > cols:
            break
        out.append(ch)
        w += cw
    if w < cols:
        out.append(GRID_FILL * (cols - w))
    return "".join(out)


def content_lines(text: str) -> list[str]:
    """Drop the ASCII wordmark; keep verses/RSS as wrap-ready paragraphs."""
    cleaned: list[str] = []
    for ln in text.splitlines():
        if any(ch in ln for ch in "▄█▀"):
            continue
        cleaned.append(ln.rstrip())
    paras = re.split(r"\n\s*\n", "\n".join(cleaned))
    lines: list[str] = []
    for para in paras:
        body = " ".join(para.split())
        if body:
            lines.append(body)
    return lines or ["KINGDOM AGE"]


def fill_grid(text: str, cols: int, rows: int) -> str:
    """Tile wrapped content into a cols×rows cell grid. Every cell is a glyph."""
    cols = max(8, int(cols))
    rows = max(4, int(rows))
    paras = content_lines(text)
    wrapped: list[str] = []
    for para in paras:
        wrapped.extend(wrap_lines(para, cols) or [""])
        wrapped.append("")
    while wrapped and wrapped[-1] == "":
        wrapped.pop()
    if not wrapped:
        wrapped = ["KINGDOM AGE"]

    out: list[str] = []
    i = 0
    while len(out) < rows:
        out.append(clip_row(wrapped[i % len(wrapped)], cols))
        i += 1
        if i % len(wrapped) == 0 and len(out) < rows:
            out.append(clip_row("", cols))
    return "\n".join(out[:rows]) + "\n"


def verse_items() -> list[tuple[str, str]]:
    raw = fallback_text()
    cleaned: list[str] = []
    for ln in raw.splitlines():
        if any(ch in ln for ch in "▄█▀"):
            continue
        cleaned.append(ln)
    items: list[tuple[str, str]] = []
    for block in re.split(r"\n\s*\n", "\n".join(cleaned)):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if lines[0] == "KINGDOM AGE" and len(lines) == 1:
            continue
        items.append((lines[0], " ".join(lines[1:])))
    return items


def collect_items(monitor: str) -> list[tuple[str, str]]:
    """RSS + verses, shuffled stably, split across monitors."""
    index, count = monitor_index(monitor)
    urls = load_feed_urls()
    items = cached_items(urls)
    seen = {title for title, _ in items}
    for title, desc in verse_items():
        if title not in seen:
            items.append((title, desc))
            seen.add(title)
    if not items:
        items = verse_items()
    rng = random.Random(hashlib.sha1(f"kingdom-age-{monitor}".encode()).hexdigest())
    pool = list(items)
    rng.shuffle(pool)
    if count > 1 and pool:
        pool = [it for i, it in enumerate(pool) if i % count == index] or pool
    return pool or [("KINGDOM AGE", "They shall sit every man under his vine and under his fig tree.")]


def compose(items: list[tuple[str, str]], monitor: str, index: int, count: int) -> str:
    if not items:
        items = collect_items(monitor)
    pool = items[:8]
    blocks = [f"KINGDOM AGE  ·  {monitor}", ""]
    for title, desc in pool:
        if title:
            blocks.append(wrap(title))
        if desc and desc != title:
            blocks.append(wrap(desc))
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def clip_plain(text: str, cols: int) -> str:
    out: list[str] = []
    w = 0
    for ch in text.replace("\t", " ").replace("\r", ""):
        if ch == "\n":
            break
        cw = char_width(ch)
        if cw <= 0:
            continue
        if w + cw > cols:
            break
        out.append(ch)
        w += cw
    return "".join(out)


def center_line(text: str, cols: int) -> str:
    text = clip_plain(text.strip(), cols)
    w = display_width(text)
    if w >= cols:
        return text
    pad = (cols - w) // 2
    return (" " * pad) + text


def format_slide(title: str, body: str, cols: int, rows: int, kicker: str = "KINGDOM AGE") -> str:
    """One verse, wrapped to a readable column and centered on the terminal."""
    cols = max(24, int(cols))
    rows = max(8, int(rows))
    wrap_w = max(28, min(56, cols - 12))
    block: list[str] = []
    if kicker:
        block.append(kicker)
        block.append("")
    title = (title or "").strip()
    body = (body or "").strip()
    if title:
        block.append(title)
        block.append("")
    if body and body != title:
        block.extend(wrap_lines(body, wrap_w))
    while block and block[-1] == "":
        block.pop()
    if not block:
        block = ["KINGDOM AGE"]
    if len(block) > rows:
        block = block[:rows]
    top = max(0, (rows - len(block)) // 2)
    lines = [""] * top + block
    while len(lines) < rows:
        lines.append("")
    return "\n".join(center_line(ln, cols) for ln in lines[:rows]) + "\n"


def hold_seconds(title: str, body: str) -> int:
    words = len(f"{title} {body}".split())
    # ~3 words/sec plus time to settle after the reveal.
    return min(40, max(18, 12 + words // 3))


def monitor_index(name: str) -> tuple[int, int]:
    try:
        import json
        import subprocess

        monitors = json.loads(subprocess.check_output(["hyprctl", "monitors", "-j"], text=True))
        names = [m.get("name", "") for m in monitors]
        if name in names:
            return names.index(name), max(1, len(names))
        return 0, max(1, len(names) or 1)
    except Exception:
        return 0, 1


def discover_monitor() -> str:
    env = os.environ.get("KINGDOM_AGE_MONITOR", "").strip()
    if env:
        return env
    try:
        import json
        import subprocess

        ppid = os.getppid()
        clients = json.loads(subprocess.check_output(["hyprctl", "clients", "-j"], text=True))
        for c in clients:
            if c.get("pid") == ppid or str(c.get("class")) == "org.omarchy.screensaver":
                mon = c.get("monitor")
                if isinstance(mon, int):
                    mons = json.loads(subprocess.check_output(["hyprctl", "monitors", "-j"], text=True))
                    for m in mons:
                        if m.get("id") == mon:
                            return str(m.get("name") or "screen")
                if mon:
                    return str(mon)
    except Exception:
        pass
    return "screen"


def cmd_fill_grid(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="screensaver-feeds.py fill-grid")
    p.add_argument("--cols", type=int, required=True)
    p.add_argument("--rows", type=int, required=True)
    p.add_argument("--input", default="-")
    p.add_argument("--output", default="-")
    args = p.parse_args(argv)
    if args.input in ("", "-"):
        src = sys.stdin.read()
    else:
        src = Path(args.input).read_text(encoding="utf-8", errors="replace")
    grid = fill_grid(src, args.cols, args.rows)
    if args.output in ("", "-"):
        sys.stdout.write(grid)
    else:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(grid, encoding="utf-8")
        sys.stdout.write(str(dest))
    return 0


def cmd_compose(monitor: str) -> int:
    index, count = monitor_index(monitor)
    items = collect_items(monitor)
    text = compose(items, monitor, index, count)
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"screen-{re.sub(r'[^A-Za-z0-9._-]', '_', monitor)}.txt"
    out.write_text(text, encoding="utf-8")
    sys.stdout.write(str(out))
    return 0


def cmd_pick_slide(argv: list[str]) -> int:
    import argparse
    import json

    p = argparse.ArgumentParser(prog="screensaver-feeds.py pick-slide")
    p.add_argument("--monitor", default="")
    p.add_argument("--cols", type=int, required=True)
    p.add_argument("--rows", type=int, required=True)
    p.add_argument("--output", default="")
    args = p.parse_args(argv)
    monitor = args.monitor.strip() or discover_monitor()
    pool = collect_items(monitor)
    CACHE.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", monitor)
    idx_path = CACHE / f"idx-{safe}.txt"
    try:
        idx = int(idx_path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        idx = 0
    title, body = pool[idx % len(pool)]
    try:
        idx_path.write_text(str(idx + 1), encoding="utf-8")
    except OSError:
        pass
    slide = format_slide(title, body, args.cols, args.rows)
    dest = Path(args.output) if args.output else CACHE / f"slide-{safe}.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(slide, encoding="utf-8")
    sys.stdout.write(
        json.dumps(
            {
                "path": str(dest),
                "hold": hold_seconds(title, body),
                "title": title,
                "index": idx,
            }
        )
    )
    return 0


def main() -> int:
    if sys.argv[1:2] == ["fill-grid"]:
        return cmd_fill_grid(sys.argv[2:])
    if sys.argv[1:2] == ["pick-slide"]:
        return cmd_pick_slide(sys.argv[2:])
    monitor = sys.argv[1] if len(sys.argv) > 1 else discover_monitor()
    return cmd_compose(monitor)


if __name__ == "__main__":
    raise SystemExit(main())
