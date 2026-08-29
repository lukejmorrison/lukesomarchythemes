#!/usr/bin/env python3
"""Tests for the Kingdom Age screensaver RSS helper."""

from __future__ import annotations

import http.server
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

HELPER = Path(__file__).resolve().parent / "omarchy-screensaver-rss"
THEME = Path(__file__).resolve().parent.parent

RSS_2 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Wizwam Quotes</title>
    <item>
      <title>Micah 4:4</title>
      <description>&lt;p&gt;But they shall sit every man under his &lt;em&gt;vine&lt;/em&gt; and under his fig tree.&lt;/p&gt;</description>
      <content:encoded>&lt;p&gt;But they shall sit every man under his vine and under his fig tree; and none shall make them afraid.&lt;/p&gt;</content:encoded>
      <link>https://wizwam.com/quotes/micah-4-4</link>
      <pubDate>Wed, 01 Jan 2025 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Isaiah 2:4</title>
      <description>They shall beat their swords into plowshares.</description>
      <link>https://wizwam.com/quotes/isaiah-2-4</link>
      <pubDate>2025-02-03T10:00:00Z</pubDate>
    </item>
  </channel>
</rss>
"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Wizwam News</title>
  <entry>
    <title>New operating model</title>
    <summary type="html">Build the public site around &lt;b&gt;documents&lt;/b&gt;.</summary>
    <link href="https://wizwam.com/news/operating-model" rel="alternate"/>
    <updated>2025-03-15T08:00:00Z</updated>
  </entry>
</feed>
"""

HTML_HOMEPAGE = b"<!doctype html><html><head><title>Nope</title></head><body>not a feed</body></html>"


def load_helper():
    loader = importlib.machinery.SourceFileLoader("omarchy_screensaver_rss", str(HELPER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class FeedParseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rss = load_helper()

    def test_strip_html(self):
        text = self.rss.strip_html("<p>Hello &amp; <em>world</em></p><br>Next")
        self.assertIn("Hello & world", text)
        self.assertIn("Next", text)
        self.assertNotIn("<", text)

    def test_parse_rss2(self):
        items = self.rss.parse_feed_xml(RSS_2.encode(), "https://wizwam.com/quotes/rss")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Micah 4:4")
        self.assertIn("none shall make them afraid", items[0]["description"])
        self.assertNotIn("<p>", items[0]["description"])
        self.assertEqual(items[0]["source"], "Wizwam Quotes")
        self.assertEqual(items[0]["link"], "https://wizwam.com/quotes/micah-4-4")
        self.assertTrue(items[0]["pubDate"])

    def test_parse_atom(self):
        items = self.rss.parse_feed_xml(ATOM.encode(), "https://wizwam.com/news/rss")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "New operating model")
        self.assertEqual(items[0]["description"], "Build the public site around documents.")
        self.assertEqual(items[0]["source"], "Wizwam News")
        self.assertEqual(items[0]["link"], "https://wizwam.com/news/operating-model")

    def test_parse_html_is_empty(self):
        items = self.rss.parse_feed_xml(HTML_HOMEPAGE, "https://example.com/rss")
        self.assertEqual(items, [])

    def test_parse_feed_urls_ignores_comments_and_junk(self):
        text = """
# comment
https://wizwam.com/quotes/rss
https://wizwam.com/quotes/rss
ftp://not-allowed.example/feed
not-a-url
https://example.com/extra.xml
"""
        urls = self.rss.parse_feed_urls(text)
        self.assertEqual(
            urls,
            [
                "https://wizwam.com/quotes/rss",
                "https://example.com/extra.xml",
            ],
        )


class ConfigAndDisplayTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tmpdir.name)
        self.cache = self.home / "cache"
        self.config = self.home / "config"
        self.cache.mkdir()
        self.config.mkdir()
        self.env = {
            "HOME": str(self.home),
            "XDG_CACHE_HOME": str(self.cache),
            "XDG_CONFIG_HOME": str(self.config),
            "KINGDOM_AGE_THEME_DIR": str(THEME),
        }
        self._old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.rss = load_helper()

    def tearDown(self):
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmpdir.cleanup()

    def test_shipped_defaults_when_no_user_file(self):
        urls = self.rss.configured_feed_urls()
        self.assertEqual(
            urls,
            [
                "https://wizwam.com/quotes/rss",
                "https://wizwam.com/news/rss",
            ],
        )

    def test_user_file_replaces_defaults(self):
        path = self.config / "omarchy" / "screensaver-feeds.conf"
        path.parent.mkdir(parents=True)
        path.write_text("# mine\nhttps://example.com/my.rss\n", encoding="utf-8")
        self.assertEqual(self.rss.configured_feed_urls(), ["https://example.com/my.rss"])

    def test_empty_user_file_falls_back_to_shipped(self):
        path = self.config / "omarchy" / "screensaver-feeds.conf"
        path.parent.mkdir(parents=True)
        path.write_text("# nothing yet\n", encoding="utf-8")
        self.assertEqual(
            self.rss.configured_feed_urls(),
            [
                "https://wizwam.com/quotes/rss",
                "https://wizwam.com/news/rss",
            ],
        )

    def test_compose_keeps_kingdom_age_and_wordmark(self):
        header = self.rss.wordmark_header(THEME / "screensaver.txt")
        text = self.rss.compose_display(
            {
                "title": "Micah 4:4",
                "description": "But they shall sit every man under his vine and under his fig tree.",
                "source": "Wizwam Quotes",
                "pubDate": "1 Jan 2025",
            },
            header,
        )
        self.assertIn("KINGDOM AGE", text)
        self.assertIn("Micah 4:4", text)
        self.assertIn("fig", text)
        self.assertIn("tree", text)
        self.assertIn("Wizwam Quotes", text)
        self.assertIn("▄", text)

    def test_pick_writes_display_and_skips_last(self):
        items = self.rss.parse_feed_xml(RSS_2.encode(), "https://wizwam.com/quotes/rss")
        self.rss.save_items(items)
        first = self.rss.pick_item(items)
        self.assertIsNotNone(first)
        path = self.rss.write_display(first)
        self.assertTrue(path.is_file())
        self.assertIn("KINGDOM AGE", path.read_text(encoding="utf-8"))
        second = self.rss.pick_item(items)
        self.assertIsNotNone(second)
        self.assertNotEqual(self.rss.item_key(first), self.rss.item_key(second))

    def test_refresh_keeps_last_cache_when_fetches_fail(self):
        cached = [{"title": "Cached", "description": "Still here", "source": "x", "pubDate": "", "link": "https://x", "feed": "https://x"}]
        self.rss.save_items(cached)
        out = self.rss.refresh_feeds(["http://127.0.0.1:1/does-not-exist"])
        self.assertEqual(out[0]["title"], "Cached")


class FetchServerTests(unittest.TestCase):
    def setUp(self):
        rss = load_helper()
        self.rss = rss

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/quotes/rss":
                    body = RSS_2.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/rss+xml")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/html":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(HTML_HOMEPAGE)))
                    self.end_headers()
                    self.wfile.write(HTML_HOMEPAGE)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, fmt, *args):
                return

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

        self.tmpdir = tempfile.TemporaryDirectory()
        home = Path(self.tmpdir.name)
        os.environ["HOME"] = str(home)
        os.environ["XDG_CACHE_HOME"] = str(home / "cache")
        os.environ["XDG_CONFIG_HOME"] = str(home / "config")
        os.environ["KINGDOM_AGE_THEME_DIR"] = str(THEME)
        self.rss = load_helper()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmpdir.cleanup()

    def test_fetch_rss_and_skip_html(self):
        items = self.rss.refresh_feeds([f"{self.base}/quotes/rss", f"{self.base}/html"])
        self.assertTrue(any(i["title"] == "Micah 4:4" for i in items))
        cached = json.loads((Path(os.environ["XDG_CACHE_HOME"]) / "omarchy" / "kingdom-age-rss" / "items.json").read_text())
        self.assertGreaterEqual(len(cached), 1)


class ShippedFilesTests(unittest.TestCase):
    def test_defaults_file(self):
        text = (THEME / "rss-feeds.conf").read_text(encoding="utf-8")
        self.assertIn("https://wizwam.com/quotes/rss", text)
        self.assertIn("https://wizwam.com/news/rss", text)
        rss = load_helper()
        self.assertNotIn(
            "yahvehyireh.com",
            " ".join(rss.parse_feed_urls(text)),
        )

    def test_readme_documents_config(self):
        text = (THEME / "README.md").read_text(encoding="utf-8")
        self.assertIn("screensaver-feeds.conf", text)
        self.assertIn("https://wizwam.com/quotes/rss", text)
        self.assertIn("https://wizwam.com/news/rss", text)
        self.assertIn("omarchy-launch-screensaver force", text)
        self.assertIn("preview", text)
        self.assertIn("themes/kingdom-age/scripts/omarchy-screensaver", text)

    def test_screensaver_still_uses_branding_fallback(self):
        script = (THEME / "scripts" / "omarchy-screensaver").read_text(encoding="utf-8")
        self.assertIn("kingdom-rain.py", script)
        self.assertIn("$branding", script)
        self.assertIn("kingdom_age_active", script)

    def test_launch_execs_theme_screensaver_path(self):
        script = (THEME / "scripts" / "omarchy-launch-screensaver").read_text(encoding="utf-8")
        self.assertIn("$script_dir/omarchy-screensaver", script)
        self.assertIn(
            "${HOME}/.config/omarchy/themes/kingdom-age/scripts/omarchy-screensaver",
            script,
        )
        self.assertIn('"$screensaver"', script)
        # Hyprland/Ghostty -e must not PATH-lookup stock /usr/bin or /usr/share/omarchy/bin
        self.assertNotRegex(
            script,
            r'-e env "KINGDOM_AGE_MONITOR=\$m" omarchy-screensaver\b',
        )

    def test_launch_resolver_follows_symlink_to_sibling(self):
        launch = THEME / "scripts" / "omarchy-launch-screensaver"
        sibling = THEME / "scripts" / "omarchy-screensaver"
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "omarchy-launch-screensaver"
            link.symlink_to(launch)
            resolved = subprocess.check_output(
                [
                    "bash",
                    "-c",
                    r"""
script_path="$1"
if command -v readlink >/dev/null; then
  script_path="$(readlink -f "$script_path" 2>/dev/null || echo "$script_path")"
fi
script_dir="$(cd "$(dirname "$script_path")" && pwd)"
screensaver="$script_dir/omarchy-screensaver"
printf '%s\n' "$screensaver"
""",
                    "resolve",
                    str(link),
                ],
                text=True,
            ).strip()
        self.assertTrue(Path(resolved).is_absolute())
        self.assertEqual(Path(resolved).resolve(), sibling.resolve())

    def test_hook_still_restores_stock_wordmark(self):
        hook = (THEME / "hooks" / "theme-set-screensaver.sh").read_text(encoding="utf-8")
        self.assertIn("theme == *kingdom-age*", hook)
        self.assertIn("KINGDOM AGE", hook)
        self.assertIn("cp \"$stock\" \"$branding\"", hook)
        self.assertIn("omarchy-screensaver-rss", hook)


if __name__ == "__main__":
    unittest.main()
