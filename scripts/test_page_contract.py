#!/usr/bin/env python3
"""Offline contract checks for the generated current-settings app."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import build_page


class PageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, build_page.DATA)) as f:
            cls.current = json.load(f)
        with open(os.path.join(ROOT, build_page.OUT)) as f:
            cls.html = f.read()

    def test_payload_contains_only_current_records(self):
        packed = build_page.pack(self.current)
        self.assertEqual(len(packed["R"]), self.current["counts"]["records"])
        self.assertEqual(set(packed), {"T", "B", "R", "U", "M"})
        self.assertEqual(set(packed["M"]), {"label", "counts", "generated", "observed"})
        self.assertTrue(all(len(row) == 12 for row in packed["R"]))
        self.assertEqual(sum(row[10] is not None for row in packed["R"]), 13)

    def test_legacy_lookup_is_absent_from_deployed_page(self):
        for text in ("legacy_formula_pro", "showpro", "D.M.pro", 'value="legacy"'):
            self.assertNotIn(text, self.html)
        self.assertIn("Historical note:", self.html)
        self.assertIn("none of its values are loaded, searched, or shown here", self.html)

    def test_machine_selection_gates_results_and_lot_alternates(self):
        template = build_page.TEMPLATE
        self.assertIn('data-machine="advanced"', template)
        self.assertIn('data-machine="mini"', template)
        self.assertIn('id="machine-step"', template)
        self.assertIn('id="market-step"', template)
        self.assertIn('id="search-step"', template)
        self.assertIn('if (!machine){', template)
        self.assertIn('$lotrow.hidden = machine !== "advanced"', template)
        self.assertIn('const useAlt = machine === "advanced"', template)
        self.assertIn('const altChip = machine !== "advanced" || altSetting == null', template)

    def test_barcode_search_honors_territory_and_warns_on_ambiguity(self):
        template = build_page.TEMPLATE
        barcode_loop = template.index("for (const u of rowUpcs(D.R[i]))")
        territory_filter = template.rindex("if (ti >= 0 && (MASK[i] & bit) === 0n) continue;",
                                           0, barcode_loop)
        self.assertLess(territory_filter, barcode_loop)
        self.assertIn("More than one product or setting uses this barcode", template)
        self.assertIn("for (const u of rowUpcs(D.R[i]))", template)

    def test_confidence_flow_has_no_implicit_ambiguous_dial(self):
        template = build_page.TEMPLATE
        self.assertIn("which formula matches your container?", template)
        self.assertIn("Do not use a dial setting until", template)
        self.assertIn("Baby Brezza lists this formula but publishes no usable setting", template)
        self.assertIn("chosen == null", template)
        self.assertIn("if (!market())", template)
        self.assertIn("Mini never takes this branch", template)
        self.assertNotIn('image dated ${fmtDate(r[7])}', template)
        self.assertIn('localStorage.removeItem("brezza.q")', template)
        self.assertIn("Last checked against Baby Brezza’s data on", template)
        self.assertIn('id="imagebox"', template)
        self.assertIn('fonts/source-sans-3-latin.woff2', template)

    def test_local_build_has_no_placeholder_repository_links(self):
        self.assertNotIn("USER/REPO", self.html)
        self.assertIn('href="data/formula_settings.json"', self.html)

    def test_typography_is_self_hosted(self):
        self.assertNotIn("fonts.googleapis.com", self.html)
        self.assertNotIn("fonts.gstatic.com", self.html)
        for name in ("source-sans-3-latin.woff2", "zilla-slab-600-latin.woff2",
                     "zilla-slab-700-latin.woff2", "ibm-plex-mono-400-latin.woff2",
                     "ibm-plex-mono-500-latin.woff2", "ibm-plex-mono-600-latin.woff2"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "site", "fonts", name)), name)


if __name__ == "__main__":
    unittest.main()
