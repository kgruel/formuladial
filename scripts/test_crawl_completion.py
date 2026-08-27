#!/usr/bin/env python3
"""Offline regressions for resumable crawler completion semantics."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "crawlers"))

import crawl_alt
import crawl_images
import crawl_settings
import crawl_stages
import crawl_types


class CrawlCompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, self.old_cwd)
        os.makedirs("raw")
        crawl_types.OUT = "raw/types.jsonl"
        crawl_stages.OUT = "raw/stages.jsonl"
        crawl_settings.OUT = "raw/settings.jsonl"
        crawl_alt.OUT = "raw/alt.jsonl"
        crawl_images.OUT = "raw/images.jsonl"
        crawl_settings.covered.clear()

    def write(self, name, rows):
        with open("raw/" + name, "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")

    def test_types_and_stages_retry_error_rows(self):
        self.write("types.jsonl", [
            {"territory": "US", "brand": "Retry", "types": [], "error": "HTTP 400"},
            {"territory": "US", "brand": "No match", "types": [], "no_match": True},
            {"territory": "US", "brand": "Good", "types": ["Infant"]},
        ])
        self.assertEqual(crawl_types.done_keys(), {("US", "No match"), ("US", "Good")})

        self.write("stages.jsonl", [
            {"territory": "US", "brand": "Retry", "type": "A", "stages": [], "error": "timeout"},
            {"territory": "US", "brand": "Good", "type": "A", "stages": []},
        ])
        self.assertEqual(crawl_stages.done_keys(), {("US", "Good", "A")})

    def test_settings_retries_failures_and_keeps_explicit_no_match(self):
        retry = ["US", "Retry", "A", "1"]
        no_match = ["US", "Missing", "A", "1"]
        old_no_match = ["US", "Legacy missing", "A", "1"]
        good = ["US", "Good", "A", "1"]
        self.write("settings.jsonl", [
            {"query": retry, "record": None, "error": "HTTP Error 400"},
            {"query": no_match, "record": None, "no_match": True},
            {"query": old_no_match, "record": None, "error": "no-match"},
            {"query": good, "record": {"brand": "Good", "type": "A", "stage": "1",
                                        "territory": ["US"], "setting": 4}},
        ])
        self.assertEqual(crawl_settings.resume(), {tuple(no_match), tuple(old_no_match), tuple(good)})
        self.assertEqual(crawl_settings.covered[("Good", "A", "1")], {"US"})

    def test_alt_retries_partial_or_legacy_error_rows(self):
        self.write("alt.jsonl", [
            {"query": ["US", "Old error", "A", "1"], "default": "ERR timeout", "alt": 4},
            {"query": ["US", "Partial", "A", "1"], "default": 4, "alt": None,
             "errors": {"true": "HTTP 500"}},
            {"query": ["US", "No match", "A", "1"], "default": None, "alt": None},
        ])
        self.assertEqual(crawl_alt.done_keys(), {("US", "No match", "A", "1")})

    def test_images_retry_error_rows(self):
        self.write("images.jsonl", [
            {"image": "retry.jpg", "error": "timed out"},
            {"image": "good.jpg", "last_modified": None, "bytes": "123"},
        ])
        self.assertEqual(crawl_images.done(), {"good.jpg"})


if __name__ == "__main__":
    unittest.main()
