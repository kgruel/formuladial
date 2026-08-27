"""Layer 4 of the crawl: the actual powder settings.

Note on the `territory` array: it is *filtered to the queried territory*, so a
record always names exactly one.  An earlier reading of the frontend suggested
it listed every territory a record belongs to, which would have allowed a
lossless skip -- it does not, so the coverage index below never fires and the
walk is exhaustive.  The index is kept because it is correct either way: it
skips only when a fetched record explicitly names the territory being asked
about, never on (brand, type, stage) equality alone.  The same brand/type name
in a different region can be a different product with a different setting.
"""
import json, os, threading
from concurrent.futures import ThreadPoolExecutor
from api import get, EmptyResponse

OUT = "data/raw/settings.jsonl"
lock = threading.Lock()

# (brand, type, stage) -> set of territories already known to be covered
covered = {}


def load_queries():
    """Every (territory, brand, type, stage) the finder can be asked about."""
    queries = []
    with open("data/raw/stages.jsonl") as f:
        for line in f:
            r = json.loads(line)
            # The UI falls back to a single empty stage when the list is empty.
            for stage in (r["stages"] or [""]):
                queries.append((r["territory"], r["brand"], r["type"], stage))
    return queries


def resume():
    """Rebuild the coverage index and the set of queries already answered."""
    asked = set()
    if not os.path.exists(OUT):
        return asked
    with open(OUT) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            q = tuple(r["query"])
            asked.add(q)
            rec = r.get("record")
            if rec:
                key = (rec["brand"], rec["type"], rec["stage"])
                covered.setdefault(key, set()).update(rec.get("territory") or [])
    return asked


def main():
    queries = load_queries()
    asked = resume()
    todo = [q for q in queries if q not in asked]
    print(f"{len(queries)} queries, {len(asked)} answered, {len(todo)} to go", flush=True)

    n = [0]
    skipped = [0]

    def work(q):
        terr, brand, typ, stage = q
        key = (brand, typ, stage)
        with lock:
            if terr in covered.get(key, ()):        # already answered losslessly
                skipped[0] += 1
                return
        try:
            rec = get("settings", territory=terr, brand=brand, type=typ,
                      stage=stage, alt_mfg_setting="false")
            err = None
        except EmptyResponse:
            rec, err = None, "no-match"
        except Exception as e:
            rec, err = None, str(e)
        out = {"query": list(q), "record": rec}
        if err:
            out["error"] = err
        with lock:
            if rec:
                covered.setdefault((rec["brand"], rec["type"], rec["stage"]),
                                   set()).update(rec.get("territory") or [])
            with open(OUT, "a") as f:
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
            n[0] += 1
            if n[0] % 1000 == 0:
                print(f"  fetched {n[0]}, skipped {skipped[0]} / {len(todo)}", flush=True)

    with ThreadPoolExecutor(14) as ex:
        list(ex.map(work, todo))
    print(f"settings layer complete: {n[0]} fetched, {skipped[0]} covered by "
          f"another territory's record", flush=True)


if __name__ == "__main__":
    main()
