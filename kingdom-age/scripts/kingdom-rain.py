#!/usr/bin/env python3
"""Kingdom Age Matrix rain: falling verse-words that stack into garden silhouettes.

One verse at a time. Honey/fig rain, a highlighted word drops like a Tetris piece,
locks into a fig tree / house / garden / eagle, holds 10–20s, then the letters
mount up and fly away like eagles.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import math
import os
import random
import re
import shutil
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOIL = (23, 20, 15)
LINEN = (234, 217, 196)
HONEY = (212, 160, 84)
HONEY_HI = (244, 232, 214)
WORD = (255, 246, 216)
GOLD = (224, 184, 90)
AMBER = (196, 146, 74)
FIG = (111, 154, 74)
FIG_DK = (61, 90, 40)
RIVER = (106, 171, 160)

STOP = {
    "the", "and", "of", "to", "a", "in", "that", "shall", "they", "them", "his",
    "her", "for", "from", "with", "not", "be", "is", "are", "was", "were", "unto",
    "ye", "thou", "thee", "thy", "it", "their", "this", "there", "have", "has",
    "had", "or", "as", "on", "at", "by", "an", "but", "which", "who", "whom",
    "into", "upon", "every", "man", "none", "make", "made", "said", "saith",
    "him", "she", "you", "your", "our", "we", "i", "my", "me", "will", "all",
    "no", "nor", "so", "if", "when", "then", "than", "also", "let", "may",
}

HERO = {
    "eagles", "eagle", "wings", "fig", "vine", "tree", "house", "houses",
    "river", "garden", "lamb", "peace",
}

PREFERRED = {
    "vine", "fig", "tree", "house", "houses", "peace", "river", "lamb", "garden",
    "sword", "swords", "plowshares", "nation", "nations", "dwell", "afraid",
    "healing", "life", "fruit", "mountain", "wine", "olive", "rest", "king",
    "kingdom", "vineyards", "fountain", "leaves", "plow", "neighbor", "neighbour",
    "zion", "jerusalem", "israel", "wolf", "lion", "crystal", "throne", "tears",
    "eagles", "eagle", "wings", "strength",
}

RAIN_GLYPHS = list("AEIOU.:|+¦*2569")
VARIATIONS = ("mold", "classic", "stack", "upwell", "soar")

VISTAS: dict[str, str] = {
    "fig-tree": r"""
            #####
         ###########
       ###############
      #################
       ###############
      #################
        #############
          #########
             ###
             ###
             ###
            #####
          #########
    """,
    "house": r"""
               ##
              ####
             ######
            ########
           ##########
          ############
         ##############
         ##          ##
         ##   ####   ##
         ##   ####   ##
         ##          ##
         ##############
        ################
    """,
    "garden": r"""
     ##                    ##
    ####       ~~~~       ####
   ######      ~~~~      ######
     ##        ~~~~        ##
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
###############################
    """,
    "vine": r"""
      #            #
     ###    #     ###
    #####  ###   #####
     ###  #####   ###
      #  ### #     #
        ###     #
       ##        ##
      #            #
     ###            ###
    """,
    "river": r"""
           ~~~~
         ~~~~~~~~
       ~~~~~~~~~~~~
         ~~~~~~~~  ~~~~
           ~~~~  ~~~~~~~~
         ~~~~~~~~  ~~~~
       ~~~~~~~~~~~~
     ~~~~~~~~    ~~~~
    """,
    "hills": r"""
              ****
            ********
              ****
     ###                    ###
    #####                  #####
   #######                #######
  #################################
    """,
    "eagle": r"""
#                      ####                      #
 ##                  ########                  ##
  ###             ##############             ###
   #####       ####################       #####
    ##########################################
     ############      ####      ############
       #########      ######      #########
         #####         ####         #####
           ##          ####          ##
                       ####
                        ##
                        ##
    """,
}

KEYWORD_VISTA = (
    (("eagle", "eagles", "wings"), "eagle"),
    (("fig", "tree", "vine", "olive"), "fig-tree"),
    (("house", "houses", "build", "dwell", "inhabit"), "house"),
    (("river", "water", "fountain", "crystal"), "river"),
    (("garden", "plant", "fruit", "vineyard", "leaf", "leaves"), "garden"),
    (("mountain", "hill", "zion"), "hills"),
    (("nation", "peace", "sword", "plow"), "hills"),
)


def rgb(c: tuple[int, int, int]) -> str:
    return f"\033[38;2;{c[0]};{c[1]};{c[2]}m"


RESET = "\033[0m"
HIDE = "\033[?25l"
SHOW = "\033[?25h"
HOME = "\033[H"
CLEAR = "\033[2J"


def load_feeds():
    path = HERE / "screensaver-feeds.py"
    loader = importlib.machinery.SourceFileLoader("screensaver_feeds", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def pick_word(title: str, body: str) -> str:
    text = f"{title} {body}"
    tokens = re.findall(r"[A-Za-z']+", text)
    if not tokens:
        return "REST"
    lower = [t.lower() for t in tokens]
    hero = [tokens[i] for i, w in enumerate(lower) if w in HERO]
    if hero:
        return max(hero, key=lambda w: (w.lower() in {"eagles", "eagle"}, len(w)))
    preferred = [tokens[i] for i, w in enumerate(lower) if w in PREFERRED]
    if preferred:
        return max(preferred, key=lambda w: (len(w), w.lower() != "lord"))
    candidates = [t for t, w in zip(tokens, lower) if w not in STOP and len(w) >= 4]
    if candidates:
        return max(candidates, key=len)
    return max(tokens, key=len)


def pick_vista(title: str, body: str, index: int) -> str:
    blob = f"{title} {body}".lower()
    for keys, name in KEYWORD_VISTA:
        if any(k in blob for k in keys):
            return name
    return list(VISTAS)[index % len(VISTAS)]


def parse_mask(art: str) -> list[list[bool]]:
    lines = [ln.rstrip() for ln in art.strip("\n").splitlines()]
    width = max((len(ln) for ln in lines), default=0)
    grid = []
    for ln in lines:
        padded = ln.ljust(width)
        grid.append([ch not in (" ", ".") for ch in padded])
    return grid


def place_mask(mask: list[list[bool]], cols: int, rows: int, caption_rows: int) -> list[list[bool]]:
    mh = len(mask)
    mw = len(mask[0]) if mask else 0
    area_h = max(1, rows - caption_rows)
    top = max(0, (area_h - mh) // 3)
    left = max(0, (cols - mw) // 2)
    out = [[False] * cols for _ in range(rows)]
    for r, row in enumerate(mask):
        rr = top + r
        if rr >= area_h:
            break
        for c, on in enumerate(row):
            cc = left + c
            if 0 <= cc < cols:
                out[rr][cc] = on
    return out


def wrap_caption(title: str, body: str, word: str, cols: int, width: int) -> list[str]:
    wrap_w = max(24, min(width, cols - 4))
    words = (body or "").split()
    lines = [title] if title else []
    if words:
        cur = words[0]
        for w in words[1:]:
            if len(cur) + 1 + len(w) <= wrap_w:
                cur += " " + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    if word and word.lower() not in " ".join(lines).lower():
        lines.append(word)
    return lines[:6]


@dataclass
class Drop:
    r: float
    c: float
    ch: str
    color: tuple[int, int, int]
    speed: float
    highlight: bool = False
    locked: bool = False
    dc: float = 0.0


@dataclass
class Piece:
    r: float
    c: int
    chars: str
    speed: float


@dataclass
class World:
    cols: int
    rows: int
    title: str
    body: str
    word: str
    variation: str
    vista: str
    rng: random.Random
    mask: list[list[bool]] = field(default_factory=list)
    locked: list[list[Drop | None]] = field(default_factory=list)
    drops: list[Drop] = field(default_factory=list)
    pieces: list[Piece] = field(default_factory=list)
    letter_i: int = 0
    letters: str = ""
    phase: str = "rain"
    phase_t: float = 0.0
    caption_rows: int = 6
    spawn_acc: float = 0.0
    word_acc: float = 0.0
    hold_seconds: float = 15.0

    def __post_init__(self) -> None:
        self.letters = "".join(ch for ch in f"{self.body} {self.title}" if ch.isalnum()) or "REST"
        self.locked = [[None] * self.cols for _ in range(self.rows)]
        if not self.mask:
            art = VISTAS.get(self.vista) or VISTAS["fig-tree"]
            self.mask = place_mask(parse_mask(art), self.cols, self.rows, self.caption_rows)

    def glyph(self) -> str:
        if self.rng.random() < 0.55:
            ch = self.letters[self.letter_i % len(self.letters)]
            self.letter_i += 1
            return ch
        return self.rng.choice(RAIN_GLYPHS)

    def rain_color(self, head: bool = False) -> tuple[int, int, int]:
        if head:
            return HONEY_HI
        return self.rng.choice((AMBER, HONEY, GOLD, FIG, FIG_DK))

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.rows and 0 <= c < self.cols

    def blocked(self, r: int, c: int) -> bool:
        if not self.in_bounds(r, c):
            return True
        return self.locked[r][c] is not None

    def lock_at(self, r: int, c: int, ch: str, color: tuple[int, int, int], highlight: bool = False) -> None:
        if not self.in_bounds(r, c) or self.locked[r][c] is not None:
            return
        if self.variation in ("mold", "stack", "upwell", "soar") and not self.mask[r][c]:
            return
        if r >= self.rows - self.caption_rows:
            return
        self.locked[r][c] = Drop(float(r), c, ch, WORD if highlight else color, 0.0, highlight, True)

    def spawn_column_head(self) -> None:
        c = self.rng.randrange(self.cols)
        speed = self.rng.uniform(0.35, 1.15)
        if self.variation == "upwell":
            r = float(self.rows - self.caption_rows - 1)
            speed = -abs(speed)
        else:
            r = 0.0
        self.drops.append(Drop(r, float(c), self.glyph(), self.rain_color(True), speed, False))

    def spawn_word_piece(self) -> None:
        word = self.word.upper()
        if len(word) >= self.cols - 2:
            word = word[: max(4, self.cols - 4)]
        c = self.rng.randrange(0, max(1, self.cols - len(word)))
        if self.variation == "upwell":
            r = float(self.rows - self.caption_rows - 1)
            speed = -self.rng.uniform(0.25, 0.55)
        else:
            r = 0.0
            speed = self.rng.uniform(0.22, 0.45)
        self.pieces.append(Piece(r, c, word, speed))

    def lock_piece(self, piece: Piece) -> None:
        r = max(0, min(self.rows - self.caption_rows - 1, int(round(piece.r))))
        for i, ch in enumerate(piece.chars):
            self.lock_at(r, piece.c + i, ch, WORD, True)

    def tick_drops(self) -> None:
        stay: list[Drop] = []
        for d in self.drops:
            if self.phase == "reverse":
                # Mount up: accelerate skyward, wings beat outward.
                d.speed -= 0.04
                d.dc += math.sin(self.phase_t * 9.0 + d.r * 0.4) * 0.09
                d.r += d.speed
                d.c += d.dc
                if -3 < d.r < self.rows + 3 and -6 < d.c < self.cols + 6:
                    stay.append(d)
                continue
            nr = d.r + d.speed
            ri, ci = int(round(nr)), int(round(d.c))
            hit = False
            if d.speed >= 0:
                if ri >= self.rows - self.caption_rows or self.blocked(min(self.rows - 1, ri), ci):
                    hit = True
                    ri = min(self.rows - self.caption_rows - 1, max(0, int(d.r)))
            else:
                if ri < 0 or self.blocked(max(0, ri), ci):
                    hit = True
                    ri = max(0, int(d.r))
            if hit:
                if self.variation != "classic":
                    self.lock_at(ri, ci, d.ch, FIG if d.speed < 0 else d.color, d.highlight)
                continue
            d.r = nr
            if self.rng.random() < 0.04:
                d.ch = self.glyph()
            stay.append(d)
        self.drops = stay

        stay_p: list[Piece] = []
        for p in self.pieces:
            nxt = p.r + p.speed
            p.r = nxt
            ri = int(round(p.r))
            collided = False
            if p.speed >= 0 and ri >= self.rows - self.caption_rows:
                collided = True
            elif p.speed < 0 and ri < 0:
                collided = True
            else:
                for i in range(len(p.chars)):
                    c = p.c + i
                    if self.blocked(max(0, min(self.rows - 1, ri)), c):
                        collided = True
                        break
                    if self.variation in ("mold", "stack") and 0 <= ri < self.rows and self.mask[ri][c]:
                        below = ri + (1 if p.speed >= 0 else -1)
                        if not self.in_bounds(below, c) or self.blocked(below, c) or not self.mask[below][c]:
                            collided = True
                            break
            if collided:
                if self.phase != "reverse" and self.variation != "classic":
                    self.lock_piece(p)
                continue
            stay_p.append(p)
        self.pieces = stay_p

    def pack_mask(self, n: int) -> None:
        """Fill n empty mask cells so the picture actually appears."""
        holes = [
            (r, c)
            for r in range(self.rows - self.caption_rows)
            for c in range(self.cols)
            if self.mask[r][c] and self.locked[r][c] is None
        ]
        self.rng.shuffle(holes)
        for r, c in holes[:n]:
            hi = self.rng.random() < 0.12
            ch = self.word[self.letter_i % len(self.word)] if hi else self.glyph()
            self.letter_i += 1
            self.lock_at(r, c, ch, WORD if hi else LINEN, hi)

    def launch_eagle(self, r: float, c: float, ch: str, color: tuple[int, int, int], highlight: bool = False) -> None:
        """Send a glyph up and out, left and right like wings."""
        cx = (self.cols - 1) / 2.0
        side = -1.0 if c < cx else 1.0
        if abs(c - cx) < 1.5:
            side = -1.0 if self.rng.random() < 0.5 else 1.0
        span = abs(c - cx) / max(cx, 1.0)
        dc = side * self.rng.uniform(0.18, 0.85) * (0.45 + span)
        speed = -self.rng.uniform(0.35, 0.95)
        self.drops.append(Drop(float(r), float(c), ch, color, speed, highlight, False, dc))

    def reverse_unlock(self, n: int) -> None:
        cx = (self.cols - 1) / 2.0
        cells = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.locked[r][c] is not None
        ]
        # Body and trailing edge lift first, then the wingtips follow.
        cells.sort(key=lambda rc: (-rc[0], abs(rc[1] - cx)))
        for r, c in cells[:n]:
            cell = self.locked[r][c]
            self.locked[r][c] = None
            if cell:
                self.launch_eagle(r, c, cell.ch, WORD if cell.highlight else cell.color, cell.highlight)

    def release_caption(self) -> None:
        for (r, c), (ch, col) in self.caption_cells().items():
            if ch.strip():
                self.launch_eagle(r, c, ch, col, ch.lower() == self.word[:1].lower())

    def mask_filled(self) -> float:
        total = sum(1 for r in range(self.rows) for c in range(self.cols) if self.mask[r][c])
        if not total:
            return 1.0
        got = sum(1 for r in range(self.rows) for c in range(self.cols) if self.mask[r][c] and self.locked[r][c])
        return got / total

    def tick(self, dt: float) -> None:
        self.phase_t += dt
        heads = 3 if self.variation == "classic" else 2
        if self.phase == "rain":
            self.spawn_acc += dt
            while self.spawn_acc > 0.03:
                self.spawn_acc -= 0.03
                for _ in range(heads):
                    self.spawn_column_head()
            self.word_acc += dt
            if self.word_acc > 1.4:
                self.word_acc = 0.0
                self.spawn_word_piece()
            self.tick_drops()
            if self.variation != "classic" and self.phase_t > 2.2:
                self.pack_mask(max(4, self.cols // 8))
            if self.phase_t > 6.5 or (self.variation != "classic" and self.mask_filled() > 0.92):
                self.phase = "hold"
                self.phase_t = 0.0
                if self.variation != "classic":
                    self.pack_mask(self.cols * self.rows)
        elif self.phase == "hold":
            self.spawn_acc += dt
            while self.spawn_acc > 0.12:
                self.spawn_acc -= 0.12
                self.spawn_column_head()
            self.word_acc += dt
            if self.word_acc > 3.5:
                self.word_acc = 0.0
                self.spawn_word_piece()
            self.tick_drops()
            # Sparse rain should not keep stacking forever during hold.
            cap = self.cols * 2
            if len(self.drops) > cap:
                self.drops = self.drops[-cap:]
            if self.phase_t >= self.hold_seconds:
                self.phase = "reverse"
                self.phase_t = 0.0
                for p in self.pieces:
                    for i, ch in enumerate(p.chars):
                        self.launch_eagle(p.r, p.c + i, ch, WORD, True)
                self.pieces = []
                self.release_caption()
        elif self.phase == "reverse":
            self.reverse_unlock(max(8, self.cols // 2))
            self.tick_drops()
            empty = not any(self.locked[r][c] for r in range(self.rows) for c in range(self.cols))
            if (empty and not self.drops and not self.pieces) or self.phase_t > 5.0:
                self.phase = "done"
                self.phase_t = 0.0

    def caption_cells(self) -> dict[tuple[int, int], tuple[str, tuple[int, int, int]]]:
        lines = wrap_caption(self.title, self.body, self.word, self.cols, 56)
        kicker = "KINGDOM AGE"
        block = [kicker, ""] + lines
        out: dict[tuple[int, int], tuple[str, tuple[int, int, int]]] = {}
        start = self.rows - self.caption_rows
        word_l = self.word.lower()
        for i, ln in enumerate(block):
            r = start + i
            if r >= self.rows:
                break
            pad = max(0, (self.cols - len(ln)) // 2)
            lower = ln.lower()
            idx = lower.find(word_l) if word_l else -1
            for j, ch in enumerate(ln):
                c = pad + j
                if c >= self.cols:
                    break
                hi = idx >= 0 and idx <= j < idx + len(self.word)
                color = WORD if hi else (HONEY if i == 0 else LINEN)
                out[(r, c)] = (ch, color)
        return out


def render(world: World) -> str:
    grid = [[(" ", SOIL)] * world.cols for _ in range(world.rows)]
    for r in range(world.rows):
        for c in range(world.cols):
            cell = world.locked[r][c]
            if cell:
                col = WORD if cell.highlight else (LINEN if world.phase == "hold" else cell.color)
                grid[r][c] = (cell.ch, col)
    for d in world.drops:
        r, c = int(round(d.r)), int(round(d.c))
        if 0 <= r < world.rows and 0 <= c < world.cols:
            grid[r][c] = (d.ch, WORD if d.highlight else d.color)
    for p in world.pieces:
        r = int(round(p.r))
        if not (0 <= r < world.rows):
            continue
        for i, ch in enumerate(p.chars):
            c = p.c + i
            if 0 <= c < world.cols:
                grid[r][c] = (ch, WORD)
    if world.phase in ("hold", "rain"):
        for (r, c), (ch, col) in world.caption_cells().items():
            if world.phase == "rain" and world.phase_t < 3.5:
                continue
            grid[r][c] = (ch, col)
    parts: list[str] = [HOME]
    last = None
    for r in range(world.rows):
        for c in range(world.cols):
            ch, col = grid[r][c]
            if col != last:
                parts.append(rgb(col if col != SOIL else SOIL))
                last = col
            parts.append(ch if ch != " " else " ")
        if r != world.rows - 1:
            parts.append("\r\n")
    parts.append(RESET)
    return "".join(parts)


def term_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return max(24, size.columns), max(12, size.lines)


def next_world(feeds, monitor: str, idx: int, cols: int, rows: int, hold: float = 15.0) -> World:
    pool = feeds.collect_items(monitor)
    title, body = pool[idx % len(pool)]
    word = pick_word(title, body)
    vista = pick_vista(title, body, idx)
    variation = VARIATIONS[idx % len(VARIATIONS)]
    if vista == "eagle":
        variation = "soar"
    rng = random.Random(f"{monitor}:{idx}:{title}")
    caption_rows = min(7, max(5, rows // 7))
    art = VISTAS.get(vista) or VISTAS["fig-tree"]
    return World(
        cols=cols,
        rows=rows,
        title=title,
        body=body,
        word=word,
        variation=variation,
        vista=vista,
        rng=rng,
        mask=place_mask(parse_mask(art), cols, rows, caption_rows),
        caption_rows=caption_rows,
        hold_seconds=hold,
    )


def run(monitor: str, fps: float = 24.0, hold: float = 15.0) -> int:
    feeds = load_feeds()
    cols, rows = term_size()
    idx = 0
    world = next_world(feeds, monitor, idx, cols, rows, hold)
    dt = 1.0 / fps
    sys.stdout.write(f"{HIDE}{CLEAR}\033]11;rgb:17/14/0f\007")
    sys.stdout.flush()

    def restore(_signum=None, _frame=None):
        sys.stdout.write(f"{SHOW}{RESET}{CLEAR}")
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGINT, restore)
    signal.signal(signal.SIGTERM, restore)
    signal.signal(signal.SIGHUP, restore)

    while True:
        t0 = time.time()
        world.tick(dt)
        if world.phase == "done":
            idx += 1
            cols, rows = term_size()
            world = next_world(feeds, monitor, idx, cols, rows, hold)
        sys.stdout.write(render(world))
        sys.stdout.flush()
        elapsed = time.time() - t0
        if elapsed < dt:
            time.sleep(dt - elapsed)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Kingdom Age Matrix rain screensaver")
    p.add_argument("--monitor", default=os.environ.get("KINGDOM_AGE_MONITOR", "screen"))
    p.add_argument("--fps", type=float, default=24.0)
    p.add_argument("--hold", type=float, default=15.0, help="Seconds to hold a completed verse (10–20)")
    args = p.parse_args(argv)
    hold = min(20.0, max(10.0, args.hold))
    return run(args.monitor, fps=args.fps, hold=hold)


if __name__ == "__main__":
    raise SystemExit(main())
