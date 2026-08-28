#!/usr/bin/env python3
"""Offline contract checks for the generated current-settings app."""
import collections
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import build_page


def _relative_luminance(hex_color):
    """WCAG 2.x relative luminance of an #rrggbb string."""
    channels = []
    for offset in (1, 3, 5):
        c = int(hex_color[offset:offset + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b):
    """WCAG 2.x contrast ratio between two #rrggbb strings."""
    la, lb = _relative_luminance(a), _relative_luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def theme_blocks(css):
    """Every custom-property block that defines a full palette, by selector.

    The dark palette is written out twice -- once under prefers-color-scheme and
    once under [data-theme="dark"] -- so read both rather than the first match.
    """
    style = re.search(r"<style>(.*?)</style>", css, re.S)
    css = style.group(1) if style else css
    blocks = {}
    for match in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        tokens = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-f]{6})", match.group(2)))
        if {"--ground", "--surface", "--raised", "--ink", "--ink-2", "--ink-3"} <= set(tokens):
            blocks[match.group(1).strip().splitlines()[-1].strip()] = tokens
    return blocks


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
        self.assertTrue(all(len(row) == 11 for row in packed["R"]))
        self.assertEqual(sum(row[9] is not None for row in packed["R"]), 13)

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
        self.assertIn('if (machine !== "advanced") return LOT.STANDARD;', template)
        self.assertIn('const otherChip = machine !== "advanced"', template)

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
        # the dial is rendered only for the record `resolveHit` returned, and
        # that is null until a market, a single candidate, or an explicit
        # choice settles it
        self.assertIn("if (resolved == null){", template)
        self.assertIn("if (chosen != null) return chosen;", template)
        self.assertIn("const i = resolved;", template)
        self.assertIn("if (!market()", template)
        self.assertIn("Mini never takes this branch", template)
        self.assertIn('localStorage.removeItem("brezza.q")', template)
        self.assertIn("Last checked against Baby Brezza’s data on", template)
        self.assertIn('id="imagebox"', template)
        self.assertIn('fonts/source-sans-3-latin.woff2', template)

    def test_ink_ramp_clears_wcag_aa_on_every_surface_in_every_theme(self):
        """The three-step ink ramp carries 10-12px text on all three surfaces.

        Light is the default theme and its --ink-3 was inherited unaudited, so
        pin the whole grid rather than trusting review to re-check it. 4.5:1 is
        the AA threshold for normal text; there are no exemptions -- every ink
        clears it against every surface it can land on.
        """
        blocks = theme_blocks(self.html)
        self.assertEqual(set(blocks), {":root", ':root:not([data-theme="light"])',
                                       ':root[data-theme="dark"]'})
        for selector, tokens in blocks.items():
            for ink in ("--ink", "--ink-2", "--ink-3"):
                for surface in ("--surface", "--ground", "--raised"):
                    ratio = contrast_ratio(tokens[ink], tokens[surface])
                    self.assertGreaterEqual(
                        ratio, 4.5,
                        f"{selector} {ink} {tokens[ink]} on {surface} "
                        f"{tokens[surface]} is {ratio:.2f}:1, below WCAG AA")

    def test_ink_ramp_stays_a_ramp(self):
        """Darkening --ink-3 for AA must not collapse it into --ink-2."""
        for selector, tokens in theme_blocks(self.html).items():
            steps = [contrast_ratio(tokens[ink], tokens["--surface"])
                     for ink in ("--ink", "--ink-2", "--ink-3")]
            self.assertEqual(steps, sorted(steps, reverse=True), selector)
            for brighter, dimmer in zip(steps, steps[1:]):
                self.assertGreaterEqual(brighter - dimmer, 1.0,
                                        f"{selector} ink steps are indistinct: {steps}")

    def test_the_two_dark_palettes_are_one_palette(self):
        """prefers-color-scheme and [data-theme=dark] duplicate every token."""
        blocks = theme_blocks(self.html)
        self.assertEqual(blocks[':root:not([data-theme="light"])'],
                         blocks[':root[data-theme="dark"]'])

    def test_focus_survives_forced_colors(self):
        """forced-colors drops box-shadow, so the shell ring cannot be the only
        focus affordance -- an outline must come back on the control itself."""
        css = build_page.TEMPLATE
        self.assertIn(".field input:focus-visible,.terr input:focus-visible{outline:none}", css)
        forced = css[css.index("@media (forced-colors: active)"):]
        forced = forced[:forced.index("\n}\n") + 3]
        self.assertIn(".field input:focus-visible,.terr input:focus-visible", forced)
        self.assertIn("outline:2px solid Highlight", forced)

    def test_lot_placeholder_is_not_uppercased(self):
        """text-transform normalises the lot number the owner types; applying it
        to the authored placeholder is what overflowed the field."""
        self.assertIn(".lotfield input{cursor:text; text-transform:uppercase}", self.html)
        self.assertIn(".lotfield input::placeholder{text-transform:none}", self.html)

    def test_all_three_dial_marks_are_present(self):
        """Three dial marks ship on this page; pin them together.

        The header mark was removed once and later reinstated, so assert all
        three rather than any one -- a sweep for one must not take the others.
        """
        self.assertIn('<svg class="heromark" viewBox="0 0 100 100" aria-hidden="true">',
                      self.html)
        self.assertIn('<h1>What setting does this formula need?</h1>', self.html)
        # the dotted i of "formula dial": an inline svg inside <span class="ti">
        self.assertIn('<span class="ti">&#305;<svg viewBox="0 0 15 15"', self.html)
        self.assertIn('.brand .ti svg{', self.html)
        self.assertIn('<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg',
                      self.html)
        # No name-based assertion on the header's layout wrapper. The old
        # `hgrid` was removed with the mark and a two-column header is now back
        # deliberately, as `hrow` -- pinning the old class name would only have
        # been dodged by the rename. What actually went wrong with `hgrid` was
        # that it wrapped the h1 at 768px, so that is what is pinned, by
        # measurement, in the heading-fit block of scripts/test_browser.mjs.

    def test_hero_mark_is_drawn_from_this_snapshot(self):
        """The mark's petals are the live setting distribution, not a frozen
        picture of one. A hardcoded mark would keep describing a distribution
        the next crawl had moved on from, so pin every petal to the data."""
        doc = json.load(open(build_page.DATA))
        live = collections.Counter(r["setting"] for r in doc["records"])
        expected = {s: live.get(s, 0) for s in range(1, 11) if live.get(s, 0)}
        mark = re.search(r'<svg class="heromark".*?</svg>', self.html, re.S)
        self.assertIsNotNone(mark, "the header mark is missing from the built page")
        drawn = {int(s): int(n) for s, n in
                 re.findall(r'data-setting="(\d+)" data-records="(\d+)"', mark.group(0))}
        self.assertEqual(drawn, expected,
                         "the header mark's petals do not match the snapshot's "
                         "setting distribution -- it is not being regenerated")
        # the needle marks the modal setting and must stay inside the r=46 rim
        mode = max(expected, key=lambda s: expected[s])
        self.assertIn(f'data-setting="{mode}"', mark.group(0))
        for x, y in re.findall(r'x2="([\d.]+)" y2="([\d.]+)"', mark.group(0)):
            radius = ((float(x) - 50) ** 2 + (float(y) - 50) ** 2) ** 0.5
            self.assertLess(radius + 2.2, 46,
                            "a stroke punches through the mark's rim")

    def test_unavailable_warning_states_each_fact_once(self):
        """The lead carries what both reasons share; the detail carries only the
        difference. no_stage names a why, no_setting has none to name."""
        template = build_page.TEMPLATE
        self.assertIn(
            "<strong>Baby Brezza lists this formula but publishes no usable "
            "setting.</strong>${detail} Do not use it in the machine unless "
            "Baby Brezza confirms compatibility and the correct setting.",
            template)
        self.assertIn('? " Its finder needs a stage this product record does not carry."',
                      template)
        self.assertNotIn("Baby Brezza lists the product but returns no setting for it",
                         template)

    def test_count_counts_and_the_heading_instructs(self):
        """$count sits directly above a .choicehead h2. It carries the quantity;
        the imperative belongs to the heading, and is stated once."""
        template = build_page.TEMPLATE
        for restated in ("— choose where the formula was sold",
                         "— choose the exact formula",
                         "related formulas without a published setting are listed below"):
            self.assertNotIn(restated, template)
        for heading in ("<h2>Step 2: choose where it was sold</h2>",
                        "<h2>Step 4: which formula matches your container?</h2>"):
            self.assertIn(heading, template)

    def test_a_step_is_marked_done_only_when_it_has_resolved(self):
        """Steps 1 and 2 always used resolved-value predicates; step 3 used
        "is there text in the box", so a search with no match still showed a
        green tick. All three now say resolved, and `needs` marks the one step
        actually blocking an answer."""
        template = build_page.TEMPLATE
        self.assertNotIn('$searchStep.classList.toggle("done", !!raw)', template)
        self.assertIn('$searchStep.classList.toggle("done", resolved != null)', template)
        self.assertIn('$machineStep.classList.toggle("done", !!machine && !lotBlocked)',
                      template)
        self.assertIn('$machineStep.classList.toggle("needs", !machine || lotBlocked)',
                      template)
        self.assertIn('const lotBlocked = resolved != null && lotUndecided(D.R[resolved])',
                      template)

    def test_rows_without_a_published_setting_are_candidates_not_choices(self):
        """A same-named row Baby Brezza publishes no setting for is another
        thing the tin might be, so it counts toward ambiguity. It is never a
        choice card: choosing it could only promise a number that does not
        exist, so it is listed as context and the page stays in the choice
        state until a real candidate is picked."""
        template = build_page.TEMPLATE
        self.assertIn("return hits.length + unavailable.length === 1 ? hits[0] : null;",
                      template)
        self.assertIn("unavailable.slice(0, MAX).map(unavailableCard).join(\"\")", template)
        self.assertNotIn("unavailable.slice(0, MAX).map(i => choiceCard(i, terms))", template)
        self.assertNotIn("if (hits.length > 1 && chosen == null){", template)

    def test_the_lot_gate_never_borrows_the_stop_colour(self):
        """The two no-number faces that already existed are red and both mean
        do not use this. The lot-gated face means answerable, one fact short,
        so it takes the --dial amber that .step.needs already uses for
        "this is the blocker" -- and says so in visible copy, not a title
        tooltip, which does not exist on touch."""
        template = build_page.TEMPLATE
        ask = template[template.index("function askSVG()"):]
        ask = ask[:ask.index("\n}")]
        self.assertNotIn("--stop", ask)
        self.assertIn("var(--dial)", ask)
        self.assertIn('<p class="asklot">', template)
        self.assertIn("Check the sticker underneath the machine and enter the "
                      "lot number in step 1.", template)
        # Every number this record has is withheld, not only the dial: a `was`
        # chip is the standard setting struck out, and a history row names it
        # outright ("Standard setting: 4 → 5"). No record carries history in
        # the current snapshot -- watch.py's sentinels are drawn from the
        # alternates, so this is where one would first appear -- which is why
        # this is pinned in the source rather than in the browser walk.
        self.assertIn('const was = r[7] && !undecided ?', template)
        self.assertIn('const history = undecided ? "" : historyMarkup(r);', template)
        self.assertIn(".asklot{", self.html)
        self.assertIn(".rec.result.asking{border-style:dashed}", self.html)

    def test_no_surface_calls_the_lot_number_flatly_optional(self):
        """The lot became a gate wherever an alternate changes the answer, so
        it is optional only under a condition -- and any copy that says
        "optional" near "lot" without carrying that condition is the residue
        this pass swept. Enumerated across every authored surface rather than
        left to review: the qualifier list is meant to shrink, not grow.
        """
        qualifiers = ("everywhere else", "in general any more")
        surfaces = ("build_page.py", "lookup.py", "build_dataset.py",
                    "README.md", "docs/HOW-IT-WORKS.md")
        checked = 0
        for name in surfaces:
            with open(os.path.join(ROOT, name)) as f:
                text = f.read()
            for match in re.finditer(r"(?i)optional", text):
                window = text[max(0, match.start() - 140):match.end() + 140]
                if not re.search(r"(?i)lot", window):
                    continue  # an unrelated optional; this invariant is the lot
                checked += 1
                self.assertTrue(
                    any(q in window.lower() for q in qualifiers),
                    f"{name} calls the lot optional without the condition that "
                    f"makes it true: {window!r}")
        self.assertGreaterEqual(checked, 4, "the scan found nothing to check")

    def test_checks_are_collapsed_and_spacing_lives_in_the_stylesheet(self):
        """The four checks collapse to their headings and expand on click, and
        vertical rhythm is stylesheet rules, not per-element inline margins.
        The inline-style count is a shrink-only ratchet: it reached zero when
        the editorial's forced breaks were dissolved, and stays there."""
        self.assertEqual(self.html.count('<details class="check">'), 4)
        self.assertEqual(self.html.count("<summary><h3>"), 4)
        self.assertNotIn('style="', build_page.TEMPLATE)

    def test_persistence_is_opt_in_and_stores_identity_never_a_number(self):
        """Two things may outlive the tab, each behind an explicit action: the
        lot number behind its checkbox, and pins. A pin is identity and market
        only -- the setting is looked up fresh each visit by replaying the pin
        through run(), so revised data always wins over a saved answer. The
        browser walk enforces the same shape on the stored JSON itself."""
        template = build_page.TEMPLATE
        # the lot persists only while the box is ticked; unticking sweeps it
        self.assertIn('if ($lotkeep.checked) store.set("brezza.lot", raw);', template)
        self.assertIn('else store.remove("brezza.lot");', template)
        # the pin shape is named once, and carries no setting column
        self.assertIn("const pinOf = i => { const r = D.R[i]; "
                      "return {b:D.B[r[0]], t:r[1], s:r[2], m:market()} };",
                      template)
        # restore resolves through the ordinary flow, not from the stored pin
        self.assertIn("chosen = findPinned(p);", template)
        # the searched query itself still never lands in localStorage
        self.assertIn('tabStore.set("brezza.q", raw)', template)
        self.assertNotIn('store.set("brezza.q"', template)
        # the editorial states the boundary the feature must keep
        self.assertIn("never the\n  setting, which is looked up fresh", self.html)

    def test_link_unfurls_carry_the_card(self):
        self.assertEqual(build_page.SITE_URL, "https://formuladial.com")
        self.assertIn('<meta property="og:image" content="https://formuladial.com/og.png">',
                      self.html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', self.html)
        # one tagline, two renderings: plain in the metas, entity mdash in the lede
        self.assertIn('content="%s"' % build_page.TAGLINE, self.html)
        self.assertIn(build_page.TAGLINE.replace("\u2014", "&mdash;"), self.html)
        # unfurl scrapers read a bounded prefix of this 0.6 MB page: the card
        # metas must precede the stylesheet and everything after it
        self.assertLess(self.html.index("og:image"), self.html.index("<style>"))
        # the committed image really is the size the metas declare
        with open(os.path.join(ROOT, "site", "og.png"), "rb") as f:
            head = f.read(24)
        self.assertEqual(head[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual((int.from_bytes(head[16:20], "big"),
                          int.from_bytes(head[20:24], "big")), (1200, 630))

    def test_home_screen_icon_is_declared_and_sized(self):
        self.assertIn('<link rel="apple-touch-icon" href="apple-touch-icon.png">', self.html)
        with open(os.path.join(ROOT, "site", "apple-touch-icon.png"), "rb") as f:
            head = f.read(24)
        self.assertEqual(head[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual((int.from_bytes(head[16:20], "big"),
                          int.from_bytes(head[20:24], "big")), (180, 180))

    def test_the_page_links_its_published_repository(self):
        self.assertNotIn("USER/REPO", self.html)
        self.assertIn('href="https://github.com/kgruel/formuladial"', self.html)
        self.assertEqual(build_page.REPO_URL, "https://github.com/kgruel/formuladial")

    def test_typography_is_self_hosted(self):
        self.assertNotIn("fonts.googleapis.com", self.html)
        self.assertNotIn("fonts.gstatic.com", self.html)
        for name in ("source-sans-3-latin.woff2", "zilla-slab-600-latin.woff2",
                     "zilla-slab-700-latin.woff2", "ibm-plex-mono-400-latin.woff2",
                     "ibm-plex-mono-500-latin.woff2", "ibm-plex-mono-600-latin.woff2"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "site", "fonts", name)), name)


if __name__ == "__main__":
    unittest.main()
