"""Sweep for the alternate manufacturing setting on the Advanced line.

Baby Brezza's own finder does not let you choose this.  It asks Formula Pro
Advanced and Advanced WiFi owners for the machine's lot number and sets
`alt_mfg_setting=true` when the prefix is "11":

    altMfgSetting = this.isFormulaProAdvancedActive()
                      ? (lotPrefix.startsWith("11") ? "true" : "false")
                      : ""

`isFormulaProAdvancedActive()` matches "wifi" or "formula-pro-advanced" in the
product URL/name, so the **Mini** (/products/formula-pro-mini) never takes this
branch -- it always queries with the parameter omitted.

The main crawl requested the default, so this fills in the alternate answer
wherever one exists.  It is rare (about 0.3% of a 600-query sample) but real,
and it lands on mainstream formulas, so it is not something to leave out.

One request per merged record rather than per (territory, brand, type, stage),
using the record's first territory as the representative.
"""
import json, os, threading
from concurrent.futures import ThreadPoolExecutor
from api import get, EmptyResponse

OUT = "data/raw/alt_settings.jsonl"
lock = threading.Lock()


def done_keys():
    """Queries for which both default and lot-11 requests were answered."""
    if not os.path.exists(OUT):
        return set()
    keys = set()
    with open(OUT) as f:
        for line in f:
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    continue
                # New rows carry a structured error map.  Older rows encoded
                # failures as "ERR ..." in either value; treat both forms as
                # incomplete so they are retried.
                if row.get("error") or row.get("errors"):
                    continue
                if any(isinstance(row.get(k), str) and row[k].startswith("ERR ")
                       for k in ("default", "alt")):
                    continue
                if "default" not in row or "alt" not in row:
                    continue
                keys.add(tuple(row["query"]))
            except (KeyError, TypeError, ValueError):
                continue
    return keys


def main():
    data = json.load(open("site/data/formula_settings.json"))
    queries = sorted({(r["territories"][0], r["brand"], r["type"], r["stage"])
                      for r in data["records"]})

    have = done_keys()
    todo = [q for q in queries if q not in have]
    print(f"{len(queries)} records, {len(have)} probed, {len(todo)} to go", flush=True)

    n = [0]
    found = [0]

    def work(q):
        terr, brand, typ, stage = q
        got = {}
        errors = {}
        for alt in ("false", "true"):
            try:
                rec = get("settings", territory=terr, brand=brand, type=typ,
                          stage=stage, alt_mfg_setting=alt)
                got[alt] = rec.get("setting")
            except EmptyResponse:
                got[alt] = None
            except Exception as e:
                got[alt] = None
                errors[alt] = str(e)
        row = {"query": list(q), "default": got["false"], "alt": got["true"]}
        if errors:
            row["errors"] = errors
        with lock:
            with open(OUT, "a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n[0] += 1
            if got["false"] != got["true"]:
                found[0] += 1
            if n[0] % 500 == 0:
                print(f"  {n[0]}/{len(todo)} — {found[0]} differ", flush=True)

    with ThreadPoolExecutor(10) as ex:
        list(ex.map(work, todo))
    print(f"alt sweep complete: {found[0]} records have a different alternate setting",
          flush=True)


if __name__ == "__main__":
    main()
