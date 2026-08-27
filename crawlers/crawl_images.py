"""Date the Advanced records via their product images.

Nothing in the settings API carries a timestamp, but every Advanced record
points at an image on babybrezzacloud.com, and those files answer HEAD with a
`Last-Modified` header.  The filenames also start with what looks like a
sequential upload id (`20467-<uuid>.png`), and the two broadly agree.

Scope: this dates the *image*, not the setting.  A record whose image was
uploaded in 2023 may have had its number revised since without the picture
changing.  It is an earliest-touched signal, not a last-verified one.
"""
import json, os, re, threading
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from api import IMAGE_BASE, head

OUT = "data/raw/image_dates.jsonl"
lock = threading.Lock()


def done():
    if not os.path.exists(OUT):
        return set()
    seen = set()
    with open(OUT) as f:
        for line in f:
            try:
                seen.add(json.loads(line)["image"])
            except ValueError:
                continue
    return seen


def main():
    data = json.load(open("site/data/formula_settings.json"))
    imgs = sorted({r["image"] for r in data["records"] if r.get("image")})
    have = done()
    todo = [i for i in imgs if i not in have]
    print(f"{len(imgs)} images, {len(have)} done, {len(todo)} to go", flush=True)

    n = [0]

    def work(img):
        row = {"image": img}
        try:
            h = head(IMAGE_BASE + img)
            lm = h.get("Last-Modified")
            row["last_modified"] = parsedate_to_datetime(lm).date().isoformat() if lm else None
            row["bytes"] = h.get("Content-Length")
        except Exception as e:
            row["error"] = str(e)[:120]
        # leading number in "20467-<uuid>.png" looks like an upload sequence id;
        # the separator varies -- "-", "_", or the extension on a bare "2181.jpg"
        m = re.match(r"(\d+)[-_.]", img)
        row["seq"] = int(m.group(1)) if m else None
        with lock:
            with open(OUT, "a") as f:
                f.write(json.dumps(row) + "\n")
            n[0] += 1
            if n[0] % 500 == 0:
                print(f"  {n[0]}/{len(todo)}", flush=True)

    with ThreadPoolExecutor(10) as ex:
        list(ex.map(work, todo))
    print("image dating complete", flush=True)


if __name__ == "__main__":
    main()
