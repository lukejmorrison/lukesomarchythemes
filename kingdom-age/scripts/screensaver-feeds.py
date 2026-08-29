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


def wrap(text: str, width: int = 72) -> str:
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return "\n".join(lines)


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


def compose(items: list[tuple[str, str]], monitor: str, index: int, count: int) -> str:
    if not items:
        items = verse_items()

    rng = random.Random(hashlib.sha1(b"kingdom-age-feeds").hexdigest())
    pool = list(items)
    rng.shuffle(pool)
    if count > 1 and pool:
        pool = [it for i, it in enumerate(pool) if i % count == index] or pool[:1]
    pool = pool[:8]

    blocks = [f"KINGDOM AGE  ·  {monitor}", ""]
    for title, desc in pool:
        if title:
            blocks.append(wrap(title))
        if desc and desc != title:
            blocks.append(wrap(desc))
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


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


def main() -> int:
    monitor = sys.argv[1] if len(sys.argv) > 1 else discover_monitor()
    index, count = monitor_index(monitor)
    urls = load_feed_urls()
    items = cached_items(urls)
    seen = {title for title, _ in items}
    for title, desc in verse_items():
        if title not in seen:
            items.append((title, desc))
            seen.add(title)
    text = compose(items, monitor, index, count)
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"screen-{re.sub(r'[^A-Za-z0-9._-]', '_', monitor)}.txt"
    out.write_text(text, encoding="utf-8")
    sys.stdout.write(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
