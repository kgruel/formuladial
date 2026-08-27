"""Layer 6: the product photos, and the thumbnails the page ships.

`crawl_images.py` HEADs every image the snapshot references and writes
`data/raw/image_dates.jsonl`.  That file is the authority for *what images
exist* and for what upstream last said about each one; this walks the same
list one step further -- GET the bytes, archive the original under
`data/raw/images/`, and cut a 128px WebP into `site/thumbs/`.  There is no
second discovery path: an image that is not in `image_dates.jsonl` is not
fetched, so the two layers can never disagree about the set.

Resume is driven by `site/thumbs/manifest.json`, which is *committed*, and
that is the whole point.  `data/raw/` is untracked, so a monthly CI run starts
with no originals on disk at all; if the skip rule asked "is the original
here?" every cycle would re-download 1.3 GB to produce byte-identical thumbs.
So the manifest records, per filename, the `{last_modified, bytes}` of the
`image_dates.jsonl` row its thumb was cut from, and the work list is the diff
of the authority against the manifest.  Manifest values are copied from that
row rather than from the GET's own headers -- the manifest is a cursor into
the sweep, and an original already on disk is accepted without a request, so a
GET's headers are not always there to record.

The origin answers unknown paths with `200` and an HTML page rather than a
404, so a response is only believed if Pillow can decode it as an image.  A
rejected image writes no file and no manifest row, which is what makes the
next run retry it and keeps `data/raw/images/` decode-clean -- the on-disk
skip rule below trusts that.

Originals are kept because they are the expensive half: any future size or
format regenerates from them without touching the network again.

Usage:
    python3 crawlers/fetch_images.py                  # fetch + thumb the diff
    python3 crawlers/fetch_images.py --deadline-min 60
    python3 crawlers/fetch_images.py --dry-run        # say what would be done

Run from the repo root.  Requires Pillow -- the one non-stdlib dependency in
the repo, and only for the encode; the crawl half is stdlib.
"""
import argparse, io, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api import IMAGE_BASE, fetch  # noqa: E402

SRC = "data/raw/image_dates.jsonl"
ORIG_DIR = "data/raw/images"
THUMB_DIR = "site/thumbs"
MANIFEST = "site/thumbs/manifest.json"

MAX_EDGE = 128          # the page draws 52px and 44px boxes; 128 covers 2x
QUALITY = 80
POOL = 10               # same pacing as the other crawlers
MAX_BODY = 32 << 20     # a product photo is ~215KB; anything near this is wrong

lock = threading.Lock()


def authority():
    """filename -> {"last_modified", "bytes"}, from the HEAD sweep."""
    rows = {}
    with open(SRC) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("error"):
                continue
            rows[r["image"]] = {"last_modified": r.get("last_modified"),
                                "bytes": r.get("bytes")}
    return rows


def manifest():
    if not os.path.exists(MANIFEST):
        return {}
    try:
        with open(MANIFEST) as f:
            return json.load(f)
    except ValueError:
        return {}


def save_manifest(m):
    """Atomic, deterministic -- this file is committed and diffed monthly."""
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as f:
        json.dump(m, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, MANIFEST)


def thumb_path(image):
    return os.path.join(THUMB_DIR, image.rsplit(".", 1)[0] + ".webp")


def pending(auth=None, have=None):
    """The work list: what the authority says exists, minus what is recorded.

    Also redoes anything whose thumb has gone missing since it was recorded --
    the manifest claims a thumb was produced, so an absent file means the
    claim is stale, not that the image is done.
    """
    auth = authority() if auth is None else auth
    have = manifest() if have is None else have
    return sorted(img for img, meta in auth.items()
                  if have.get(img) != meta or not os.path.exists(thumb_path(img)))


def thumbnail(blob):
    """Decode `blob` and return (webp bytes, (w, h) in, (w, h) out).

    Raises if the bytes are not a decodable image -- which is also how the
    origin's 200-with-HTML soft-404 is caught.
    """
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(blob))
    im.load()                                   # force the decode now, not lazily
    src = im.size
    im = ImageOps.exif_transpose(im) or im
    if im.mode in ("P", "LA", "PA"):
        im = im.convert("RGBA")
    elif im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)   # aspect kept, never upscaled
    out = io.BytesIO()
    im.save(out, "WEBP", quality=QUALITY, method=6)
    return out.getvalue(), src, im.size


def atomic_write(path, data):
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--deadline-min", type=float, default=0,
                    help="stop starting new work after N minutes (0 = no limit)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    auth = authority()
    have = manifest()
    todo = pending(auth, have)
    print(f"{len(auth)} images, {len(have)} in the manifest, {len(todo)} to go",
          flush=True)
    if args.dry_run or not todo:
        return 0

    os.makedirs(ORIG_DIR, exist_ok=True)
    os.makedirs(THUMB_DIR, exist_ok=True)
    deadline = time.time() + args.deadline_min * 60 if args.deadline_min else None

    stat = {"fetched": 0, "on_disk": 0, "skipped_deadline": 0,
            "orig_bytes": 0, "thumb_bytes": 0}
    failed, drift, mislabeled = [], [], []
    dirty = [0]

    def flush(force=False):
        if dirty[0] >= 200 or (force and dirty[0]):
            save_manifest(have)
            dirty[0] = 0

    def work(img):
        if deadline and time.time() > deadline:
            with lock:
                stat["skipped_deadline"] += 1
            return
        meta = auth[img]
        path = os.path.join(ORIG_DIR, img)
        want = int(meta["bytes"]) if (meta.get("bytes") or "").isdigit() else None
        blob, note = None, None
        try:
            # An original already archived at the size the sweep saw is the same
            # file; re-fetching it would buy nothing but bandwidth.
            if os.path.exists(path) and want is not None and \
                    os.path.getsize(path) == want:
                with open(path, "rb") as f:
                    blob = f.read()
                note = "disk"
            else:
                blob, hdrs = fetch(IMAGE_BASE + img)
                if len(blob) > MAX_BODY:
                    raise ValueError(f"absurd body: {len(blob)}B")
                note = "net"
                # Content-Type is a hint, not a verdict: the origin serves a
                # handful of genuine photos as application/octet-stream, and
                # serves its soft-404 page as text/html with a 200.  Only the
                # decode below tells the two apart, so that is what decides;
                # a wrong label is worth reporting, not refusing.
                ctype = (hdrs.get("Content-Type") or "").split(";")[0].strip()
                if not ctype.startswith("image/"):
                    mislabeled.append((img, ctype or "?", str(len(blob))))
                lm = hdrs.get("Last-Modified")
                lm = parsedate_to_datetime(lm).date().isoformat() if lm else None
                if lm != meta["last_modified"] or (
                        want is not None and len(blob) != want):
                    drift.append((img, meta["last_modified"], meta["bytes"],
                                  lm, str(len(blob))))
            thumb, src_size, out_size = thumbnail(blob)
        except Exception as e:
            with lock:
                failed.append((img, f"{type(e).__name__}: {str(e)[:100]}"))
            return                                  # no file, no row -> retried

        if note == "net":
            atomic_write(path, blob)
        atomic_write(thumb_path(img), thumb)
        with lock:
            have[img] = meta
            dirty[0] += 1
            stat["fetched" if note == "net" else "on_disk"] += 1
            stat["orig_bytes"] += len(blob)
            stat["thumb_bytes"] += len(thumb)
            n = stat["fetched"] + stat["on_disk"]
            if n % 250 == 0:
                print(f"  {n}/{len(todo)}  net={stat['fetched']} "
                      f"disk={stat['on_disk']} fail={len(failed)} "
                      f"{stat['orig_bytes'] / 1e6:.0f}MB", flush=True)
            flush()

    try:
        with ThreadPoolExecutor(POOL) as ex:
            list(ex.map(work, todo))
    finally:
        with lock:
            flush(force=True)

    print(f"fetched {stat['fetched']} ({stat['orig_bytes'] / 1e6:.1f}MB), "
          f"{stat['on_disk']} already archived, "
          f"{len(failed)} failed, {stat['skipped_deadline']} left to the clock; "
          f"thumbs {stat['thumb_bytes'] / 1e6:.1f}MB", flush=True)
    for img, why in failed[:40]:
        print(f"  fail {img}: {why}", flush=True)
    for img, ctype, n in mislabeled[:20]:
        print(f"  mislabeled {img}: served as {ctype}, {n}B, decoded fine", flush=True)
    for row in drift[:40]:
        print("  drift %s: sweep %s/%s -> now %s/%s" % row, flush=True)
    if len(drift) > 40:
        print(f"  ... and {len(drift) - 40} more changed since the sweep", flush=True)
    left = len(pending())
    print(f"image fetch {'complete' if not left else f'incomplete, {left} to go'}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
