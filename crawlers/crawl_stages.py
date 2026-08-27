"""Layer 3 of the crawl: stage lists for every (territory, brand, type) triple.

Resumable via data/raw/stages.jsonl.
"""
import json, os, threading
from concurrent.futures import ThreadPoolExecutor
from api import EmptyResponse, get

OUT = "data/raw/stages.jsonl"
lock = threading.Lock()

def load_triples():
    triples = []
    with open("data/raw/types.jsonl") as f:
        for line in f:
            r = json.loads(line)
            for t in r["types"]:
                triples.append((r["territory"], r["brand"], t))
    return triples

def done_keys():
    """Triples with a verified response (including an explicit no-match)."""
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
            # A prior failed attempt must never suppress its retry.
            if r.get("error"):
                continue
            if not isinstance(r.get("stages"), list):
                continue
            try:
                keys.add((r["territory"], r["brand"], r["type"]))
            except KeyError:
                continue
    return keys

def main():
    triples = load_triples()
    have = done_keys()
    todo = [t for t in triples if t not in have]
    print(f"{len(triples)} triples, {len(have)} done, {len(todo)} to go", flush=True)

    n = [0]
    def work(tri):
        terr, brand, typ = tri
        try:
            stages = get("stages", territory=terr, brand=brand, type=typ)
            err = None
            no_match = False
        except EmptyResponse:
            stages, err, no_match = [], None, True
        except Exception as e:
            stages, err, no_match = [], str(e), False
        rec = {"territory": terr, "brand": brand, "type": typ, "stages": stages}
        if no_match:
            rec["no_match"] = True
        if err:
            rec["error"] = err
        with lock:
            with open(OUT, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n[0] += 1
            if n[0] % 2000 == 0:
                print(f"  {n[0]}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(14) as ex:
        list(ex.map(work, todo))
    print("stages layer complete", flush=True)

if __name__ == "__main__":
    main()
