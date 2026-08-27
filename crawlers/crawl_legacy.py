"""Crawl the discontinued original Formula Pro (model_type=pro) dataset.

Small enough to walk in one pass: ~18 territories, ~556 (territory, brand)
pairs.  Unlike the modern API there is no territory array on a record, so
nothing can be de-duplicated -- every pair is walked.

`getsetting` returns every stage for a triple in one table, so there is no
stage loop.  Brands whose `gettypepro` comes back empty are answered by
`getbrandtosetting` instead; the old UI branched the same way and skipping it
would silently drop those brands.

The raw HTML fragment is kept next to the parsed rows, because this backend is
frozen and re-crawling it is not something to rely on.
"""
import json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor
from legacy_api import post, options, rows

MODEL = sys.argv[1] if len(sys.argv) > 1 else "pro"
OUT = f"data/legacy/legacy_{MODEL}.jsonl"
lock = threading.Lock()
# An old index.php backend and the only copy of this data -- stay gentle.
CONCURRENCY = 4


def done_keys():
    if not os.path.exists(OUT):
        return set()
    keys = set()
    with open(OUT) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            keys.add((r["territory"], r["brand"]))
    return keys


def main():
    territories = options(post("", model_type=MODEL))
    print(f"model_type={MODEL}: {len(territories)} territories", flush=True)

    pairs = []
    for tval, tlabel in territories:
        for bval, blabel in options(post("getbrand", territory_id=tval, model_type=MODEL)):
            pairs.append((tval, tlabel, bval, blabel))
    print(f"{len(pairs)} (territory, brand) pairs", flush=True)

    have = done_keys()
    todo = [p for p in pairs if (p[1], p[3]) not in have]
    print(f"{len(have)} done, {len(todo)} to go", flush=True)

    n = [0]

    def work(pair):
        tval, tlabel, bval, blabel = pair
        entries, err = [], None
        try:
            types = options(post("gettypepro", brand_id=bval,
                                 territory_id=tval, model_type=MODEL))
            if types:
                for tyval, tylabel in types:
                    frag = post("getsetting", type_id=tyval, territory_id=tval,
                                brand_id=bval, model_type=MODEL)
                    entries.append({"type": tylabel, "rows": rows(frag), "html": frag})
            else:
                # Brand with no type list -- the old UI fell back to this call.
                frag = post("getbrandtosetting", brand_id=bval,
                            territory_id=tval, model_type=MODEL)
                entries.append({"type": "", "rows": rows(frag), "html": frag})
        except Exception as e:
            err = str(e)

        rec = {"model": MODEL, "territory": tlabel, "brand": blabel, "entries": entries}
        if err:
            rec["error"] = err
        with lock:
            with open(OUT, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n[0] += 1
            if n[0] % 25 == 0:
                print(f"  {n[0]}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(CONCURRENCY) as ex:
        list(ex.map(work, todo))
    print("legacy crawl complete", flush=True)


if __name__ == "__main__":
    main()
