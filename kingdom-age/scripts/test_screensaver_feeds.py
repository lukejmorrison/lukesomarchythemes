#!/usr/bin/env python3
"""Tests for Kingdom Age screensaver grid fill (no black side bands)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

HELPER = Path(__file__).resolve().parent / "screensaver-feeds.py"
VERSES = Path(__file__).resolve().parent.parent / "screensaver.txt"


def load_mod():
    loader = importlib.machinery.SourceFileLoader("screensaver_feeds", str(HELPER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class FillGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_exact_rectangle(self):
        grid = self.mod.fill_grid("KINGDOM AGE\n\nSit under the fig tree.", 20, 8)
        lines = grid.splitlines()
        self.assertEqual(len(lines), 8)
        self.assertTrue(all(len(ln) == 20 for ln in lines), lines)
        self.assertTrue(grid.endswith("\n"))

    def test_no_empty_cells(self):
        grid = self.mod.fill_grid("hi", 12, 5)
        for ln in grid.splitlines():
            self.assertNotIn("  ", ln.replace(self.mod.GRID_FILL, "x"))
            self.assertEqual(len(ln), 12)
            self.assertTrue(any(ch != " " for ch in ln))

    def test_strips_ascii_wordmark(self):
        raw = VERSES.read_text(encoding="utf-8")
        grid = self.mod.fill_grid(raw, 48, 24)
        self.assertNotIn("▄", grid)
        self.assertNotIn("█", grid)
        self.assertIn("fig tree", grid.lower())
        lines = grid.splitlines()
        self.assertEqual(len(lines), 24)
        self.assertTrue(all(self.mod.display_width(ln) == 48 for ln in lines))

    def test_repeats_to_fill_height(self):
        grid = self.mod.fill_grid("Micah 4:4", 16, 20)
        self.assertGreaterEqual(grid.count("Micah"), 2)


class SlideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_one_verse_centered(self):
        slide = self.mod.format_slide(
            "Micah 4:4",
            "But they shall sit every man under his vine and under his fig tree.",
            80,
            24,
        )
        lines = slide.splitlines()
        self.assertEqual(len(lines), 24)
        self.assertEqual(slide.count("Micah 4:4"), 1)
        self.assertNotIn("Isaiah", slide)
        self.assertIn("KINGDOM AGE", slide)
        self.assertIn("fig tree", slide)
        nonempty = [ln for ln in lines if ln.strip()]
        self.assertTrue(all(ln.startswith(" ") for ln in nonempty))
        self.assertTrue(all(self.mod.display_width(ln) <= 80 for ln in lines))
        wrapped = [ln.strip() for ln in nonempty if ln.strip() not in ("KINGDOM AGE", "Micah 4:4")]
        self.assertTrue(all(len(ln) <= 56 for ln in wrapped), wrapped)

    def test_hold_scales_with_length(self):
        short = self.mod.hold_seconds("Micah 4:4", "Sit under the fig tree.")
        long = self.mod.hold_seconds(
            "John 1:48-49",
            "Nathanael saith unto him, Whence knowest thou me? " * 8,
        )
        self.assertGreaterEqual(short, 18)
        self.assertGreaterEqual(long, short)
        self.assertLessEqual(long, 40)

    def test_pick_slide_advances(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp())
        buf = io.StringIO()
        with redirect_stdout(buf):
            a = self.mod.cmd_pick_slide(
                ["--monitor", "test-mon-adv", "--cols", "80", "--rows", "24", "--output", str(tmp / "a.txt")]
            )
            b = self.mod.cmd_pick_slide(
                ["--monitor", "test-mon-adv", "--cols", "80", "--rows", "24", "--output", str(tmp / "b.txt")]
            )
        self.assertEqual(a, 0)
        self.assertEqual(b, 0)
        blobs = buf.getvalue().replace("}{", "}\n{").splitlines()
        titles = [json.loads(line)["title"] for line in blobs if line.strip()]
        self.assertEqual(len(titles), 2)
        self.assertNotEqual(titles[0], titles[1])


if __name__ == "__main__":
    unittest.main()
