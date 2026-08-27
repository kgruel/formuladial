"""Layer 2 of the crawl: types for every (territory, brand) pair.

Resumable: every completed pair is appended to types.jsonl and skipped on
restart.  Type lists are territory-dependent (verified empirically), so this
layer cannot be collapsed.
"""
import json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor
from api import get

OUT = "types.jsonl"
lock = threading.Lock()

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
    bbt = json.load(open("brands_by_territory.json"))
    pairs = [(t, b) for t, bs in bbt.items() for b in bs]
    have = done_keys()
    todo = [p for p in pairs if p not in have]
    print(f"{len(pairs)} pairs, {len(have)} done, {len(todo)} to go", flush=True)

    n = [0]
    def work(pair):
        t, b = pair
        try:
            types = get("types", territory=t, brand=b)
            err = None
        except Exception as e:
            types, err = [], str(e)
        rec = {"territory": t, "brand": b, "types": types}
        if err:
            rec["error"] = err
        with lock:
            with open(OUT, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n[0] += 1
            if n[0] % 250 == 0:
                print(f"  {n[0]}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(7) as ex:
        list(ex.map(work, todo))
    print("types layer complete", flush=True)

if __name__ == "__main__":
    main()
