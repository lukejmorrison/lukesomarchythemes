#!/usr/bin/env python3
"""Tests for Kingdom Age Tetris/Matrix rain."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import random
import sys
import unittest
from pathlib import Path

RAIN = Path(__file__).resolve().parent / "kingdom-rain.py"


def load_mod():
    loader = importlib.machinery.SourceFileLoader("kingdom_rain", str(RAIN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = mod
    loader.exec_module(mod)
    return mod


class WordVistaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_prefers_fig_tree(self):
        word = self.mod.pick_word(
            "Micah 4:4",
            "But they shall sit every man under his vine and under his fig tree.",
        )
        self.assertIn(word.lower(), {"fig", "vine", "tree"})

    def test_vista_from_verse(self):
        self.assertEqual(
            self.mod.pick_vista("Micah 4:4", "under his fig tree", 0),
            "fig-tree",
        )
        self.assertEqual(
            self.mod.pick_vista("Isaiah 65:21", "they shall build houses", 0),
            "house",
        )
        self.assertEqual(
            self.mod.pick_vista("Revelation 22", "a pure river of water of life", 0),
            "river",
        )
        self.assertEqual(
            self.mod.pick_vista(
                "Isaiah 40:31",
                "they shall mount up with wings as eagles",
                0,
            ),
            "eagle",
        )

    def test_prefers_eagles(self):
        word = self.mod.pick_word(
            "Isaiah 40:31",
            "But they that wait upon the LORD shall renew their strength; they shall mount up with wings as eagles;",
        )
        self.assertEqual(word.lower(), "eagles")

    def test_mask_parse_and_place(self):
        mask = self.mod.parse_mask(self.mod.VISTAS["fig-tree"])
        self.assertGreater(sum(sum(row) for row in mask), 20)
        placed = self.mod.place_mask(mask, 80, 24, 6)
        self.assertEqual(len(placed), 24)
        self.assertEqual(len(placed[0]), 80)
        self.assertTrue(any(any(row) for row in placed[:18]))
        self.assertFalse(any(any(row) for row in placed[18:]))


class WorldCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def _world(self, variation="mold", hold=1.2):
        title = "Micah 4:4"
        body = "But they shall sit every man under his vine and under his fig tree."
        art = self.mod.VISTAS["fig-tree"]
        return self.mod.World(
            cols=80,
            rows=24,
            title=title,
            body=body,
            word="FIG",
            variation=variation,
            vista="fig-tree",
            rng=random.Random(1),
            mask=self.mod.place_mask(self.mod.parse_mask(art), 80, 24, 6),
            caption_rows=6,
            hold_seconds=hold,
        )

    def test_mold_fills_then_holds_then_reverses(self):
        w = self._world("mold", hold=0.8)
        seen = []
        filled = 0.0
        for _ in range(400):
            w.tick(1 / 24)
            if w.phase == "hold":
                filled = max(filled, w.mask_filled())
            if not seen or seen[-1] != w.phase:
                seen.append(w.phase)
            if w.phase == "done":
                break
        self.assertIn("hold", seen)
        self.assertIn("reverse", seen)
        self.assertEqual(w.phase, "done")
        self.assertGreater(filled, 0.9)

    def test_falling_word_is_the_highlight(self):
        w = self._world("classic", hold=8)
        w.spawn_word_piece()
        self.assertTrue(w.pieces)
        self.assertEqual(w.pieces[0].chars, "FIG")

    def test_next_world_advances_verses(self):
        feeds = self.mod.load_feeds()
        a = self.mod.next_world(feeds, "screen", 0, 80, 24, 15)
        b = self.mod.next_world(feeds, "screen", 1, 80, 24, 15)
        c = self.mod.next_world(feeds, "screen", 2, 80, 24, 15)
        titles = {a.title, b.title, c.title}
        self.assertGreaterEqual(len(titles), 2)
        self.assertEqual(a.hold_seconds, 15)
        self.assertIn(a.variation, self.mod.VARIATIONS)
        self.assertNotEqual(a.variation, b.variation)

    def test_render_covers_full_grid(self):
        w = self._world("mold")
        w.pack_mask(40)
        frame = self.mod.render(w)
        self.assertIn("\033[", frame)
        self.assertGreater(len(frame), 80)

    def test_reverse_flies_like_an_eagle(self):
        w = self._world("soar", hold=0.4)
        w.vista = "eagle"
        w.mask = self.mod.place_mask(self.mod.parse_mask(self.mod.VISTAS["eagle"]), 80, 24, 6)
        w.pack_mask(80)
        w.phase = "hold"
        w.phase_t = 0.4
        w.tick(0.05)
        self.assertEqual(w.phase, "reverse")
        self.assertTrue(w.drops)
        self.assertTrue(all(d.speed < 0 for d in w.drops))
        self.assertTrue(any(d.dc != 0 for d in w.drops))

    def test_isaiah_40_31_is_in_the_pool(self):
        feeds = self.mod.load_feeds()
        items = feeds.verse_items()
        titles = [t for t, _ in items]
        self.assertIn("Isaiah 40:31", titles)
        body = next(b for t, b in items if t == "Isaiah 40:31")
        self.assertIn("eagles", body.lower())


if __name__ == "__main__":
    unittest.main()
