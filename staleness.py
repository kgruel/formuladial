"""Measure how stale the retired backend's data is.

The retired backend (legacy_api.py) serves *both* models: `model_type=pro` --
the original Formula Pro, the only copy of that data anywhere -- and
`model_type=advanced`, a frozen snapshot of the Advanced line from whenever
Baby Brezza stopped maintaining it.

That second copy is the useful instrument.  The Advanced line is still
maintained on the live API, so comparing frozen-Advanced against live-Advanced
measures how much settings actually move over that interval.  Assuming both
halves of the retired backend froze together -- same backend, same retired page
-- that percentage is the best available estimate of how far the original
Formula Pro's numbers would have drifted if anyone were still updating them.

It is an estimate, not a correction: there is nothing to check the original's
numbers against.

    python3 crawlers/crawl_legacy.py advanced   # -> data/legacy/legacy_advanced.jsonl
    python3 staleness.py
"""
import json, re, sys
from collections import defaultdict


def norm(s):
    """Loose key -- the two backends punctuate and capitalise differently."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def setting_of(text):
    t = text.strip()
    return int(t) if t.isdigit() else t.upper()


def main():
    live = defaultdict(set)
    for r in json.load(open("site/data/formula_settings.json"))["records"]:
        live[(norm(r["brand"]), norm(r["type"]), norm(r["stage"]))].add(r["setting"])

    frozen = defaultdict(set)
    try:
        rows = [json.loads(l) for l in open("data/legacy/legacy_advanced.jsonl")]
    except FileNotFoundError:
        sys.exit("run: python3 crawl_legacy.py advanced")
    for r in rows:
        for e in r["entries"]:
            for stage, setting in e["rows"]:
                stage = "" if stage.strip().upper() == "N/A" else stage
                frozen[(norm(r["brand"]), norm(e["type"]), norm(stage))].add(setting_of(setting))

    both = set(live) & set(frozen)
    # A name can describe different regional products.  Without a territory
    # mapping between the two backends, a multi-valued set is not evidence that
    # one particular product changed.  Keep those cases out of both the rate
    # and the per-result "was" annotations.
    comparable = {k for k in both if len(live[k]) == 1 and len(frozen[k]) == 1}
    ambiguous = both - comparable
    changed = sorted(k for k in comparable if live[k] != frozen[k])
    pct = 100 * len(changed) / len(comparable) if comparable else 0
    print(f"frozen Advanced entries : {len(frozen)}")
    print(f"live   Advanced entries : {len(live)}")
    print(f"unambiguous exact-name comparisons: {len(comparable)}")
    print(f"ambiguous regional sets excluded  : {len(ambiguous)}")
    print(f"settings changed        : {len(changed)}  ({pct:.0f}%)")
    print("\nexamples:")
    for k in changed[:15]:
        print(f"  {k[0]} / {k[1]} / {k[2] or '-'}: {sorted(frozen[k])} -> {sorted(live[k])}")
    json.dump({"comparable": len(comparable), "ambiguous_excluded": len(ambiguous),
               "changed": len(changed), "pct": round(pct),
               "examples": [{"brand": k[0], "type": k[1], "stage": k[2],
                             "was": sorted(map(str, frozen[k])),
                             "now": sorted(map(str, live[k]))} for k in changed]},
              open("data/staleness.json", "w"), indent=1)
    print("\nwrote data/staleness.json")


if __name__ == "__main__":
    main()
