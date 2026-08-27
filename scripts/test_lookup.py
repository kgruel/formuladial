#!/usr/bin/env python3
"""Offline checks for barcode normalization and territory filtering.

    python3 scripts/test_lookup.py

These checks use the committed snapshot only; no API requests are made.
"""
import json
import os
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

    print("\n%d failed" % failures if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
