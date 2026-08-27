"""Layer 2 of the crawl: types for every (territory, brand) pair.

Resumable: every completed pair is appended to data/raw/types.jsonl and skipped on
restart.  Type lists are territory-dependent (verified empirically), so this
layer cannot be collapsed.
"""
import json, os, sys, threading
from concurrent.futures import ThreadPoolExecutor
from api import EmptyResponse, get

OUT = "data/raw/types.jsonl"
lock = threading.Lock()

def done_keys():
    """Pairs with a verified response (including an explicit no-match)."""
    if not os.path.exists(OUT):
        return set()
    keys = set()
    with open(OUT) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict):
                continue
            # Error rows are retained as an audit trail, but must be retried.
            # This also makes rows written by older crawler versions retryable.
            if r.get("error"):
                continue
            if not isinstance(r.get("types"), list):
                continue
            try:
                keys.add((r["territory"], r["brand"]))
            except KeyError:
                continue
    return keys

def main():
    bbt = json.load(open("data/brands_by_territory.json"))
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
            no_match = False
        except EmptyResponse:
            types, err, no_match = [], None, True
        except Exception as e:
            types, err, no_match = [], str(e), False
        rec = {"territory": t, "brand": b, "types": types}
        if no_match:
            rec["no_match"] = True
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
