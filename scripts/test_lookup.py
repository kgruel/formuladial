#!/usr/bin/env python3
"""Offline checks for barcode normalization and territory filtering.

    python3 scripts/test_lookup.py

These checks use the committed snapshot only; no API requests are made.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lookup  # noqa: E402


def check(name, condition, detail=""):
    print(("  ok   " if condition else "  FAIL ") + name
          + (("  " + detail) if detail else ""))
    return condition


def main():
    failures = 0

    # The leading zero is the only UPC-A/EAN-13 difference.  Both directions
    # must work, including common scanner formatting.
    pairs = [
        ("070074680644", "0070074680644"),
        ("300875126400", "0300875126400"),
    ]
    for upc, ean in pairs:
        failures += not check("UPC/EAN canonical key", lookup.canonical_barcode(upc)
                              == lookup.canonical_barcode(ean))
        failures += not check("UPC query matches EAN", lookup.barcode_matches(upc, ean))
        failures += not check("EAN query matches UPC", lookup.barcode_matches(ean, upc))
    failures += not check("formatting is ignored",
                          lookup.barcode_matches("0-300875-126400", "0300875126400"))
    failures += not check("different barcode does not match",
                          not lookup.barcode_matches("300875126400", "300875126401"))

    us = {"territories": ["United States of America"]}
    anz = {"territories": ["Australia/New Zealand"]}
    failures += not check("territory match is case/accent insensitive",
                          lookup.territory_matches(us, "united states"))
    failures += not check("territory excludes other regions",
                          not lookup.territory_matches(anz, "United States"))
    failures += not check("empty territory keeps all records",
                          lookup.territory_matches(anz, None))

    # This code is deliberately shared by every lookup mode.  The committed
    # snapshot has one barcode in both US and Australia/NZ with different
    # settings; a selected territory must narrow it before displaying results.
    records = json.load(open(lookup.DATA["advanced"]))["records"]
    hits = lookup.barcode_hits(records, "813267020335", "United States")
    failures += not check("territory-filtered barcode has US result",
                          len(hits) == 1 and hits[0]["setting"] == 4)
    hits = lookup.barcode_hits(records, "813267020335", "Australia")
    failures += not check("territory-filtered barcode has ANZ result",
                          len(hits) == 1 and hits[0]["setting"] == 5)
    hits = lookup.barcode_hits(records, "813267020335")
    ambiguous_hits = hits
    failures += not check("unfiltered barcode retains both regional results",
                          len(hits) == 2 and {r["setting"] for r in hits} == {4, 5})

    # A merged setting row can still have market-specific package provenance.
    # The extra Parent's Choice UPC is US-only and must not match in Canada.
    hits = lookup.barcode_hits(records, "681131350204", "United States")
    failures += not check("variant UPC matches its source market", len(hits) == 1)
    hits = lookup.barcode_hits(records, "681131350204", "Canada")
    failures += not check("variant UPC is excluded from another market", not hits)

    # Confidence states are explicit.  An unavailable row is not put in the
    # usable records list, and a broad text search may still return candidates
    # while reporting that the result needs a choice.
    unavailable = [{"brand": "Example", "type": "Sensitive", "stage": "1",
                    "territories": ["United States"], "reason": "no-setting"}]
    failures += not check("known unavailable is found by name",
                          len(lookup.unavailable_matches(unavailable,
                              terms=["example", "sensitive"], territory="United")) == 1)
    failures += not check("known unavailable state",
                          lookup.classify_results([], unavailable,
                                                   mode="text") == "known_unavailable")
    failures += not check("empty state is not found",
                          lookup.classify_results([], [], mode="text") == "not_found")
    failures += not check("conflicting barcode state is ambiguous",
                          lookup.classify_results(ambiguous_hits, mode="barcode") == "ambiguous")
    failures += not check("single barcode still requires a market",
                          lookup.classify_results(ambiguous_hits[:1], mode="barcode") == "ambiguous")
    failures += not check("single barcode with market is unique",
                          lookup.classify_results(ambiguous_hits[:1], mode="barcode",
                                                  territory="United States") == "unique")

    # The lot number is a fourth gate wherever it changes the answer, exactly
    # as on the page: an Advanced lookup with no --lot against a record that
    # carries an alternate has two answers, which is the condition `ambiguous`
    # already names.  It is a location claim about the lookup, never a verdict
    # about the standard number.
    alt = [r for r in records if r.get("alt_setting") is not None]
    alt_zero = [r for r in alt if r["alt_setting"] == 0]
    plain = [r for r in records if r.get("alt_setting") is None][:1]
    failures += not check("alternates all differ from their standard",
                          all(r["alt_setting"] != r["setting"] for r in alt),
                          f"{len(alt)} records")
    failures += not check("an unentered lot leaves an alternate undecided",
                          lookup.lot_undecided(alt[:1]))
    failures += not check("any lot decides it",
                          not lookup.lot_undecided(alt[:1], "2200XYZ")
                          and not lookup.lot_undecided(alt[:1], "1123ABC"))
    failures += not check("a record without an alternate is never gated",
                          not lookup.lot_undecided(plain))
    failures += not check("gated single hit is ambiguous, not unique",
                          lookup.classify_results(alt[:1], territory="United States")
                          == "ambiguous")
    failures += not check("a lot number resolves it to unique",
                          lookup.classify_results(alt[:1], territory="United States",
                                                  lot="1123ABC") == "unique"
                          and lookup.classify_results(alt[:1], territory="United States",
                                                      lot="2200XYZ") == "unique")
    failures += not check("an ungated single hit stays unique",
                          lookup.classify_results(plain, territory="United States")
                          == "unique")
    # Two of the 99 alternates are 0: a lot-11 machine resolves those to no
    # dial position at all, which must still be reachable through the gate.
    failures += not check("a lot-11 alternate of 0 resolves to no dial position",
                          len(alt_zero) == 2
                          and all(lookup._effective_setting(r, "11X") == 0
                                  for r in alt_zero))

    # A row with no published setting is a candidate on both surfaces.  While
    # one sits beside a single hit the lookup has found two things the tin
    # might be, so `unique` -- a verdict claim -- is withheld exactly as the
    # page withholds "Exact formula match".
    sibling = [{"brand": "Neocate", "type": "Syneo Infant", "stage": "",
                "territories": ["Australia/New Zealand"], "reason": "no_stage"}]
    failures += not check("a sibling with no setting keeps a single hit ambiguous",
                          lookup.classify_results(plain, sibling,
                                                  territory="Australia") == "ambiguous")
    failures += not check("without the sibling the same hit is unique",
                          lookup.classify_results(plain, territory="Australia")
                          == "unique")
    run = subprocess.run(
        [sys.executable, os.path.join(lookup.ROOT, "lookup.py"),
         "--territory", "Australia/New Zealand", "neocate", "syneo"],
        capture_output=True, text=True, check=True)
    failures += not check("a withheld number names the competing candidate",
                          "no published setting" in run.stdout
                          and "Neocate — Syneo Infant" in run.stdout
                          and "setting 4" not in run.stdout,
                          repr(run.stdout.splitlines()[0][:60]))

    # The documented --json envelope, end to end: a gated lookup must use the
    # explicit shape and withhold both numbers rather than print either.
    run = subprocess.run(
        [sys.executable, os.path.join(lookup.ROOT, "lookup.py"),
         "bobbie", "organic gentle", "-t", "United States", "--json"],
        capture_output=True, text=True, check=True)
    envelope = json.loads(run.stdout)
    failures += not check("gated --json keeps the state/results/unavailable envelope",
                          set(envelope) == {"state", "results", "unavailable"}
                          and envelope["state"] == "ambiguous")
    failures += not check("gated --json withholds both settings",
                          len(envelope["results"]) == 1
                          and not {"setting", "alt_setting"} & set(envelope["results"][0]))
    run = subprocess.run(
        [sys.executable, os.path.join(lookup.ROOT, "lookup.py"),
         "bobbie", "organic gentle", "-t", "United States", "--lot", "1123ABC",
         "--json"], capture_output=True, text=True, check=True)
    resolved = json.loads(run.stdout)
    failures += not check("a resolved lookup keeps the historical list shape",
                          isinstance(resolved, list) and len(resolved) == 1
                          and resolved[0]["alt_setting"] == 6)

    print("\n%d failed" % failures if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
