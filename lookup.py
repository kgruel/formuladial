#!/usr/bin/env python3
"""Offline lookup for Baby Brezza powder settings.

    ./lookup.py similac 360              # Advanced / Advanced WiFi / Mini
    ./lookup.py --upc 070074680644       # barcode
    ./lookup.py similac --alt-only       # formulas with a lot-number variant
    ./lookup.py similac 360 --lot 11X    # numbers for a lot-11 Advanced

For the 99 formulas that carry an alternate the lot number decides the answer,
so a lookup without ``--lot`` is ``ambiguous`` rather than a standard setting
with a footnote.

Searches only the current Formula Pro Advanced-family snapshot. The
discontinued original Formula Pro is intentionally unavailable as a lookup;
its frozen crawl remains under data/legacy/ solely as a historical artifact.
Matching is case- and accent-insensitive; every space-separated term must
appear in "brand type stage".
"""
import argparse, json, os, re, sys, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = {"advanced": os.path.join(ROOT, "site/data/formula_settings.json")}

# These are the terminal confidence states. Text searches intentionally remain
# candidate lists, but no lookup is actionable without a market and no
# ambiguous result may expose settings as if one were authoritative.
RESULT_STATES = ("unique", "ambiguous", "known_unavailable", "not_found")


def fold(s):
    """Casefold and strip accents so 'nestle' matches 'Nestlé'."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def barcode_digits(value):
    """Return the digits in a barcode, ignoring spaces, dashes, and labels."""
    return re.sub(r"[^0-9]", "", str(value or ""))


def canonical_barcode(value):
    """Normalize equivalent UPC-A/EAN-13 representations to one key.

    A UPC-A is the 12-digit form of an EAN-13 whose first digit is zero.  The
    API and scans use both forms, so normalization must be symmetric: either
    a 12-digit query matches a stored 13-digit EAN, or a 13-digit query matches
    a stored UPC.  Other lengths are retained verbatim because the crawl has
    a few non-standard placeholder values; they should only match themselves.
    """
    digits = barcode_digits(value)
    if len(digits) == 13 and digits.startswith("0"):
        return digits[1:]
    return digits


def barcode_matches(query, candidate):
    """Whether two barcode values identify the same UPC-A/EAN-13 code."""
    wanted = canonical_barcode(query)
    return bool(wanted) and wanted == canonical_barcode(candidate)


def territory_matches(record, territory):
    """Whether a record belongs to a requested territory substring."""
    if not territory:
        return True
    wanted = fold(territory)
    # ``_row_territories`` also understands the query-shaped rows used by the
    # snapshot's optional unavailable list.  It is defined below; Python
    # resolves this name when the function is called, after module loading.
    return any(wanted in fold(t) for t in _row_territories(record))


def filter_records(records, territory=None):
    """Apply the same territory filter to text, brand, and barcode searches."""
    return [r for r in records if territory_matches(r, territory)]


def record_upcs(record, territory=None):
    """Barcodes valid for the selected market, preserving source provenance."""
    variants = record.get("territory_variants") or []
    if not territory or not variants:
        return record.get("upc", [])
    upcs = []
    for variant in variants:
        if territory_matches(variant, territory):
            upcs.extend(variant.get("upc", []))
    return sorted(set(upcs))


def barcode_hits(records, query, territory=None):
    """Find barcode records, applying an optional territory filter first."""
    return [r for r in filter_records(records, territory)
            if any(barcode_matches(query, u) for u in record_upcs(r, territory))]


def load_snapshot():
    """Load the current snapshot, including its optional unavailable list."""
    path = DATA["advanced"]
    if not os.path.exists(path):
        sys.exit(f"{path} not found — run the crawlers then build_dataset.py")
    with open(path) as f:
        snapshot = json.load(f)
    # Treat a missing list as an older snapshot, not as malformed data.  The
    # builder publishes unavailable rows separately from usable dial records.
    snapshot.setdefault("unavailable", [])
    return snapshot


def load():
    """Records from the current Advanced-family snapshot.

    Kept as a small compatibility wrapper for callers that only need usable
    settings.  Use :func:`load_snapshot` when a caller must distinguish a
    known product with no published setting from a genuine miss.
    """
    return load_snapshot()["records"]


def _row_territories(row):
    """Territories from either a merged row or a raw unavailable row."""
    territories = row.get("territories")
    if territories:
        return territories
    # A future/older unavailable export may retain its crawl query instead of
    # the normalized territories field.  Supporting it here keeps the CLI
    # useful while the snapshot format evolves.
    query = row.get("query")
    return [query[0]] if isinstance(query, list) and query else []


def unavailable_matches(rows, terms=None, query=None, territory=None):
    """Find known products for which the snapshot has no dial setting.

    ``rows`` is the snapshot's top-level ``unavailable`` list.  It is kept out
    of ``records`` on purpose: callers must opt into this state and can never
    accidentally print a missing setting as if it were a number.
    """
    rows = filter_records(rows, territory)
    if query is not None:
        return [r for r in rows
                if any(barcode_matches(query, u) for u in r.get("upc", []))]
    wanted = [fold(t) for t in (terms or []) if fold(t)]
    return [r for r in rows if all(t in fold(" ".join(
        str(r.get(k, "")) for k in ("brand", "type", "stage")))
        for t in wanted)]


def _effective_setting(record, lot=""):
    """Return the setting that would be used by an Advanced lot, if known."""
    if lot.strip().upper().startswith("11") and record.get("alt_setting") is not None:
        return record["alt_setting"]
    return record.get("setting")


def setting_variants(records, lot=""):
    """Distinct effective settings represented by records."""
    return {_effective_setting(r, lot) for r in records}


def lot_undecided(records, lot=""):
    """Whether an unentered lot number still decides one of these settings.

    A location claim, not a verdict: it says the answer depends on something
    the lookup has not been given, never that the standard number is wrong or
    unsafe.  Only records whose alternate would actually change the number
    count, so the ``--lot`` flag stays optional everywhere else.
    """
    if lot.strip():
        return False
    return any(_effective_setting(r, "11") != _effective_setting(r, "")
               for r in records)


def classify_results(hits, unavailable=None, mode="text", territory=None, lot=""):
    """Classify a lookup into a small, safety-oriented confidence contract.

    Text searches can intentionally return a list of formula choices; multiple
    hits are therefore ``ambiguous``. Barcode matches are exact-product
    lookups, but two different effective settings are also ``ambiguous``.
    A lone record whose setting depends on a lot number that no ``--lot``
    supplied is the same condition -- one record carrying two answers rather
    than two records -- so it takes that state rather than a fifth one.
    A row Baby Brezza publishes no setting for is a candidate too: while one
    sits beside the hit, the lookup has found two things the tin might be and
    ``unique`` would be a verdict the data cannot carry.
    As in the browser app, a missing territory keeps even one candidate
    non-actionable. ``known_unavailable`` always wins when there is no usable
    record, while an empty result is ``not_found``.
    """
    hits = list(hits or [])
    unavailable = list(unavailable or [])
    if not hits:
        return "known_unavailable" if unavailable else "not_found"
    if not territory:
        return "ambiguous"
    if mode == "barcode" and len(setting_variants(hits, lot)) > 1:
        return "ambiguous"
    if lot_undecided(hits, lot):
        return "ambiguous"
    return "unique" if len(hits) == 1 and not unavailable else "ambiguous"


def show(recs, territory_filter, lot="", reveal=True, blocked_label="CHOOSE TIN"):
    """Print results. A lot number starting 11 selects Baby Brezza's alternate
    settings for Formula Pro Advanced and Advanced WiFi machines."""
    if not recs:
        print("No match.")
        return
    alt_active = lot.strip().upper().startswith("11")
    w = max(len(f"{r['brand']} — {r['type']}") for r in recs)
    for r in recs:
        setting = r["alt_setting"] if (alt_active and "alt_setting" in r) else r["setting"]
        if not reveal:
            # Keep identifying candidate details visible, but never print a
            # number that could be copied into the machine before the market
            # and exact tin have been resolved.
            setting = blocked_label
        # The dial runs 1-10, so a published 0 is not a number to turn it to.
        if isinstance(setting, int) and setting > 0:
            cell = f"setting {setting:>2}"
        else:
            cell = f"{'NO DIAL POSITION' if setting == 0 else setting:>16}"
        stage = f"stage {r['stage']}" if r["stage"] else "no stage"
        if not reveal:
            alt = ""
        elif "alt_setting" not in r:
            alt = ""
        elif alt_active:
            alt = f"   [standard machine: {r['setting']}]"
        else:
            alt = f"   [lot 11… → {r['alt_setting']}]"
        print(f"  {'ADVANCED':<8} {cell}   "
              f"{r['brand'] + ' — ' + r['type']:<{w}}  {stage}{alt}")
        if not territory_filter:
            t = _row_territories(r)
            where = ", ".join(t) if len(t) <= 4 else f"{', '.join(t[:3])} +{len(t)-3} more"
            print(f"{'':>11}{where}")


def show_unavailable(rows, lead):
    """Name the known products the snapshot has no dial setting for.

    Withholding a number without naming the competing candidate would leave a
    lookup no way to narrow itself, so both states that hold one back -- the
    terminal ``known_unavailable`` and an ``ambiguous`` result with a sibling
    beside it -- print the same list.
    """
    if not rows:
        return
    print(lead)
    for r in rows:
        label = " — ".join(str(r.get(k, "")) for k in ("brand", "type") if r.get(k))
        stage = f"  stage {r['stage']}" if r.get("stage") else ""
        reason = f" ({r['reason']})" if r.get("reason") else ""
        print(f"  {label}{stage}{reason}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("terms", nargs="*", help="words to match against brand/type/stage")
    p.add_argument("--upc", help="barcode on the tin")
    p.add_argument("-t", "--territory", help="restrict to a territory (substring)")
    p.add_argument("--brands", action="store_true", help="list brands instead of settings")
    p.add_argument("--lot", default="",
                   help="machine lot number; required where a formula has an "
                        "alternate, since one starting 11 selects it")
    p.add_argument("--alt-only", action="store_true",
                   help="only formulas with a lot-number alternate setting")
    p.add_argument("--json", action="store_true", help="raw JSON output")
    a = p.parse_args()

    terr = fold(a.territory) if a.territory else None
    snapshot = load_snapshot()
    recs = snapshot["records"]
    unavailable = snapshot.get("unavailable", [])
    if a.alt_only:
        recs = [r for r in recs if "alt_setting" in r]
        unavailable = []
    recs = filter_records(recs, a.territory)
    unavailable = filter_records(unavailable, a.territory)

    if a.upc:
        hits = barcode_hits(recs, a.upc, a.territory)
        unavailable_hits = unavailable_matches(unavailable, query=a.upc)
        mode = "barcode"
    elif a.brands:
        names = sorted({r["brand"] for r in recs}, key=fold)
        print("\n".join(names) or "No brands for that filter.")
        return
    else:
        if not a.terms:
            p.error("give search terms, --upc, or --brands")
        terms = [fold(t) for t in a.terms]
        hits = [r for r in recs
                if all(t in fold(f"{r['brand']} {r['type']} {r['stage']}") for t in terms)]
        unavailable_hits = unavailable_matches(unavailable, terms=terms)
        mode = "text"

    state = classify_results(hits, unavailable_hits, mode=mode,
                             territory=a.territory, lot=a.lot)

    if a.json:
        # Preserve the historical list shape for successful, non-ambiguous
        # lookups.  The explicit envelope is used whenever the result needs a
        # confidence explanation, so scripts cannot mistake an omission for a
        # genuine no-match.
        if state == "unique":
            print(json.dumps(hits, indent=2, ensure_ascii=False))
        else:
            safe_hits = hits
            if state == "ambiguous":
                safe_hits = [{k: v for k, v in r.items()
                              if k not in ("setting", "alt_setting")} for r in hits]
            print(json.dumps({"state": state, "results": safe_hits,
                              "unavailable": unavailable_hits},
                             indent=2, ensure_ascii=False))
        return

    if state == "known_unavailable":
        show_unavailable(
            unavailable_hits,
            "Known formula, but Baby Brezza publishes no usable dial setting "
            "for it in this snapshot. Do not guess a number; contact Baby Brezza.")
        return
    if state == "not_found":
        print("No match.")
        return
    if state == "ambiguous":
        blocked_label = "CHOOSE TIN"
        if not a.territory:
            print("Choose the market with --territory before using a dial number.")
            blocked_label = "CHOOSE TERRITORY"
        elif len(hits) > 1 and mode == "barcode":
            print("Barcode matches multiple tins or settings in the selected territory. "
                  "Refine the lookup or verify the tin with Baby Brezza.")
        elif len(hits) > 1:
            print("Several formulas match. Refine the search to the exact tin before "
                  "using a dial number.")
        elif unavailable_hits:
            print("Another formula matching this lookup has no published setting, so "
                  "this is not an exact match. Identify the tin in hand before using "
                  "a dial number.")
        else:
            print("This formula's setting depends on the machine's lot number. "
                  "Check the sticker underneath the machine and pass --lot.")
            blocked_label = "NEED LOT"
        show(hits, terr, a.lot, reveal=False, blocked_label=blocked_label)
        show_unavailable(unavailable_hits,
                         "  also matching, with no published setting:")
    else:
        show(hits, terr, a.lot)
    if hits:
        print(f"\n  {len(hits)} result(s).  ADVANCED family only.")


if __name__ == "__main__":
    main()
