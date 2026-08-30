#!/usr/bin/env python3
"""Offline regressions for the published Formula Pro Advanced-family snapshot."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import build_dataset


class DatasetTests(unittest.TestCase):
    def write_rows(self, rows):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.unlink(tmp.name))
        with tmp:
            for row in rows:
                tmp.write(json.dumps(row) + "\n")
        return tmp.name

    def test_known_unavailable_source_answers_are_retained(self):
        path = self.write_rows([
            {"query": ["US", "Known", "No stages", ""], "record": None,
             "no_match": True},
            {"query": ["Canada", "Known", "No setting", "1"], "record": {
                "brand": "Known", "type": "No setting", "stage": "1",
                "territory": ["Canada"], "setting": None,
                "upc": ["0123456789012"], "image": ["canada.png"]}},
            {"query": ["US", "Working", "Infant", "1"], "record": {
                "brand": "Working", "type": "Infant", "stage": "1",
                "territory": ["US"], "setting": 4, "upc": [], "image": []}},
        ])
        actionable, unavailable, stats = build_dataset.load_advanced(path)

        self.assertEqual(actionable, [{"brand": "Working", "type": "Infant", "stage": "1",
                                       "territory": "US", "setting": 4, "upc": [], "image": None}])
        self.assertEqual(stats["no_match"], 1)
        self.assertEqual(stats["no_stage"], 1)
        self.assertEqual(stats["no_setting"], 1)
        self.assertEqual(unavailable, [
            {"brand": "Known", "type": "No stages", "stage": "", "territory": "US",
             "reason": "no_stage", "upc": [], "image": None},
            {"brand": "Known", "type": "No setting", "stage": "1", "territory": "Canada",
             "reason": "no_setting", "upc": ["0123456789012"], "image": "canada.png"},
        ])

    def test_source_territory_and_metadata_variants_are_preserved(self):
        path = self.write_rows([
            {"query": ["US", "Same", "Product", "1"], "record": {
                "brand": "Same", "type": "Product", "stage": "1", "territory": ["US", "Canada"],
                "setting": "4", "upc": ["111"], "image": ["us.png"]}},
            {"query": ["Canada", "Same", "Product", "1"], "record": {
                "brand": "Same", "type": "Product", "stage": "1", "territory": ["Canada"],
                "setting": "4", "upc": ["222"], "image": ["canada.png"]}},
        ])
        actionable, unavailable, stats = build_dataset.load_advanced(path)
        self.assertFalse(unavailable)
        self.assertFalse(stats.get("malformed"))
        records = build_dataset.merge(actionable)
        self.assertEqual(records[0]["territories"], ["Canada", "US"])
        self.assertEqual(records[0]["upc"], ["111", "222"])
        self.assertEqual(records[0]["territory_variants"], [
            {"territories": ["US"], "upc": ["111"], "image": "us.png"},
            {"territories": ["Canada"], "upc": ["222"], "image": "canada.png"},
        ])

    def test_malformed_or_failed_latest_query_fails_closed(self):
        path = self.write_rows([
            {"query": ["US", "Broken", "Product"], "record": None},
            {"query": ["US", "Retry", "Product", "1"], "record": None,
             "error": "HTTP 500"},
        ])
        actionable, unavailable, stats = build_dataset.load_advanced(path)
        self.assertFalse(actionable)
        self.assertFalse(unavailable)
        self.assertEqual(stats["malformed"], 1)
        self.assertEqual(stats["errors"], 1)

    def test_unavailable_merging_keeps_query_count_and_territory_coverage(self):
        unavailable = build_dataset.merge_unavailable([
            {"brand": "Known", "type": "Unavailable", "stage": "1", "territory": "US",
             "reason": "no_setting", "upc": ["123"], "image": "same.png"},
            {"brand": "Known", "type": "Unavailable", "stage": "1", "territory": "Canada",
             "reason": "no_setting", "upc": ["123"], "image": "same.png"},
        ])
        self.assertEqual(unavailable, [{
            "brand": "Known", "type": "Unavailable", "stage": "1",
            "territories": ["Canada", "US"], "reason": "no_setting",
            "upc": ["123"], "image": "same.png",
        }])
        summary = build_dataset.counts([], unavailable, [], custom=1)
        self.assertEqual(summary["unavailable_records"], 1)
        self.assertEqual(summary["unavailable_queries"], 2)

    def test_checked_in_snapshot_has_a_complete_unavailable_schema(self):
        with open(os.path.join(ROOT, build_dataset.OUT)) as f:
            snapshot = json.load(f)
        self.assertIn("unavailable", snapshot)
        self.assertEqual(snapshot["counts"]["unavailable_queries"],
                         snapshot["crawl_stats"]["no_match"] + snapshot["crawl_stats"]["no_setting"])
        for row in snapshot["unavailable"]:
            self.assertEqual(set(row), {"brand", "type", "stage", "territories", "reason", "upc", "image"})
            self.assertTrue(row["territories"])
            self.assertIn(row["reason"], {"no_stage", "no_match", "no_setting"})

    def test_committed_observation_matches_the_local_crawl(self):
        """The committed manifest names the crawl that produced the snapshot.

        Only checkable where that crawl is on disk: ``data/raw`` is gitignored,
        so a fresh clone has nothing to bind against. Skipping says that out
        loud; failing would claim the code is wrong when only the input is
        missing, and passing silently would hide that nothing was checked.
        """
        raw_path = os.path.join(ROOT, build_dataset.RAW_SETTINGS)
        if not os.path.exists(raw_path):
            self.skipTest("data/raw/settings.jsonl is gitignored and absent here")
        with open(os.path.join(ROOT, build_dataset.OBSERVATION)) as source:
            expected = json.load(source)["observed"]
        self.assertEqual(build_dataset.observed_date(), expected)

    def test_observation_is_bound_to_the_exact_raw_crawl(self):
        raw = self.write_rows([{"query": ["US", "A", "B", "1"]}])
        manifest = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.addCleanup(lambda: os.path.exists(manifest.name) and os.unlink(manifest.name))
        with manifest:
            json.dump({"observed": "2026-01-01", "settings_sha256": "wrong"}, manifest)
        self.assertIsNone(build_dataset.observed_date(manifest.name, raw))

    def test_setting_history_records_changes_once(self):
        previous = {"records": [{"brand": "A", "type": "B", "stage": "1",
                                  "setting": 4, "territories": ["US"]}]}
        current = {"records": [{"brand": "A", "type": "B", "stage": "1",
                                 "setting": 5, "territories": ["US"]}]}
        history = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.addCleanup(lambda: os.path.exists(history.name) and os.unlink(history.name))
        with history:
            json.dump({"events": []}, history)
        self.assertEqual(build_dataset.update_history(previous, current, "2026-08-27",
                                                       history.name), 1)
        self.assertEqual(build_dataset.update_history(previous, current, "2026-08-27",
                                                       history.name), 1)
        with open(history.name) as source:
            event = json.load(source)["events"][0]
        self.assertEqual((event["from"], event["to"], event["territory"]), (4, 5, "US"))


if __name__ == "__main__":
    unittest.main()
