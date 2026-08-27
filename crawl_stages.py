"""Layer 3 of the crawl: stage lists for every (territory, brand, type) triple.

Resumable via stages.jsonl.
"""
import json, os, threading
from concurrent.futures import ThreadPoolExecutor
from api import get

OUT = "stages.jsonl"
lock = threading.Lock()

def load_triples():
    triples = []
    with open("types.jsonl") as f:
        for line in f:
            r = json.loads(line)
            for t in r["types"]:
                triples.append((r["territory"], r["brand"], t))
    return triples

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
            keys.add((r["territory"], r["brand"], r["type"]))
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
        except Exception as e:
            stages, err = [], str(e)
        rec = {"territory": terr, "brand": brand, "type": typ, "stages": stages}
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
