#!/usr/bin/env python3
"""How much of a crawl layer is left, without crawling anything.

The full walk is ~10h at the crawlers' pacing, which is longer than a GitHub
Actions job may live.  The crawlers already resume from their `.jsonl`, so the
workflow runs each layer under `timeout`, then asks *this* whether the layer
finished and re-dispatches itself if not.

That question has to be answered from the same resume logic the crawler itself
uses -- not by scraping "0 to go" out of a log line -- so every count here is
computed by importing the crawler module and calling its own functions.

    python3 scripts/remaining.py types      # -> "1234"
    python3 scripts/remaining.py all        # -> one "layer count" line each

Run from the repo root; the crawlers use root-relative paths.  Exit code is 0
when the named layer has nothing left, 1 when work remains, 2 on error (e.g. an
input file the previous layer has not produced yet).
"""
import json, os, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "crawlers"))

SNAPSHOT = "site/data/formula_settings.json"


def types_remaining():
    import crawl_types
    bbt = json.load(open("data/brands_by_territory.json"))
    pairs = {(t, b) for t, bs in bbt.items() for b in bs}
    return len(pairs - crawl_types.done_keys())


def stages_remaining():
    import crawl_stages
    triples = set(crawl_stages.load_triples())
    return len(triples - crawl_stages.done_keys())


def settings_remaining():
    import crawl_settings
    queries = set(crawl_settings.load_queries())
    return len(queries - crawl_settings.resume())


def alt_remaining():
    import crawl_alt
    data = json.load(open(SNAPSHOT))
    queries = {(r["territories"][0], r["brand"], r["type"], r["stage"])
               for r in data["records"]
               if r["model"] == "advanced" and r["territories"]}
    return len(queries - crawl_alt.done_keys())


def images_remaining():
    import crawl_images
    data = json.load(open(SNAPSHOT))
    imgs = {r["image"] for r in data["records"] if r.get("image")}
    return len(imgs - crawl_images.done())


def thumbs_remaining():
    # Its own resume logic, like every other layer here -- and answerable
    # without Pillow, which fetch_images.py imports only to encode.
    import fetch_images
    return len(fetch_images.pending())


LAYERS = {"types": types_remaining, "stages": stages_remaining,
          "settings": settings_remaining, "alt": alt_remaining,
          "images": images_remaining, "thumbs": thumbs_remaining}


def main(argv):
    if len(argv) != 2 or argv[1] not in LAYERS and argv[1] != "all":
        print("usage: remaining.py {%s|all}" % "|".join(LAYERS), file=sys.stderr)
        return 2
    if argv[1] == "all":
        left = 0
        for name, fn in LAYERS.items():
            try:
                n = fn()
            except Exception as e:
                print("%s ? (%s)" % (name, e))
                continue
            print("%s %d" % (name, n))
            left += n
        return 1 if left else 0
    try:
        n = LAYERS[argv[1]]()
    except Exception as e:
        print("error: %s" % e, file=sys.stderr)
        return 2
    print(n)
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
