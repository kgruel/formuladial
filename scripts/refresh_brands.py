#!/usr/bin/env python3
"""Rewrite data/brands_by_territory.json from the live API.

`crawl_types.py` walks this file, so it is the crawl's root input -- and it was
a hand-captured snapshot that nothing regenerated.  That made the automation
unable to converge: the tripwire would spot a new brand, the full crawl would
walk the *old* brand list, the snapshot would come back unchanged, and the
tripwire would report the same brand again the following week.  Refreshing it
at the start of a crawl cycle closes that loop, for ~80 requests.

It is written back only when it actually differs, so a no-op crawl leaves the
file (and the commit) alone.

    python3 scripts/refresh_brands.py            # rewrite, print a JSON delta
    python3 scripts/refresh_brands.py --dry-run  # report only

Exit 0 whether or not anything moved; exit 2 if the API could not be walked
completely -- a half-fetched brand list must never overwrite a good one.
"""
import argparse, json, os, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "crawlers"))
from api import get  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "data", "brands_by_territory.json")


def fetch():
    territories = sorted(get("territories"))
    errors = []

    def brands_of(t):
        try:
            return t, sorted(get("brands", territory=t))
        except Exception as e:
            errors.append("%s: %s" % (t, e))
            return t, None

    with ThreadPoolExecutor(7) as ex:
        pairs = list(ex.map(brands_of, territories))
    return {t: bs for t, bs in pairs if bs is not None}, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    old = json.load(open(OUT))
    new, errors = fetch()
    if errors:
        print(json.dumps({"error": "incomplete walk, refusing to overwrite",
                          "failures": errors[:10]}))
        return 2

    delta = {
        "territories_added": sorted(set(new) - set(old)),
        "territories_removed": sorted(set(old) - set(new)),
        "brands_added": {t: sorted(set(new[t]) - set(old.get(t, [])))
                         for t in new if set(new[t]) - set(old.get(t, []))},
        "brands_removed": {t: sorted(set(old[t]) - set(new.get(t, [])))
                           for t in old if set(old[t]) - set(new.get(t, []))},
    }
    changed = any(delta.values())
    if changed and not a.dry_run:
        with open(OUT, "w") as f:
            json.dump({t: new[t] for t in sorted(new)}, f,
                      ensure_ascii=False, indent=1)
            f.write("\n")
    print(json.dumps({"changed": changed,
                      "pairs": sum(len(v) for v in new.values()),
                      "written": bool(changed and not a.dry_run),
                      "delta": delta}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
