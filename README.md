# Brezza Setting Finder

A free, searchable page with every powder setting Baby Brezza publishes for
their formula makers — the Formula Pro Advanced family (Advanced, Advanced
WiFi, Mini) and the discontinued original Formula Pro. No email address, no
lookup limit, no tracking. Type a brand, get the number.

**Use it here: https://USER.github.io/REPO/**

Two things to know before you trust any number, from here or anywhere:

* **Check the number against your own tin before mixing a bottle.** This is
  infant food prep. Manufacturers reformulate, and the setting for the same
  brand name can differ by stage, country, and even your machine's lot number.
  If what the tin says and what the finder says disagree, believe neither —
  ask Baby Brezza.
* **"Dated" means "not touched since", never "verified on".** The dates shown
  come from when Baby Brezza last replaced a record's product image. A record
  dated 2023 may have had its setting revised since without the picture
  changing. They are a freshness hint, not a verification stamp.

This site is **unofficial and not affiliated with Baby Brezza**. Every number
comes from Baby Brezza's own public data, collected as described in
[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Why this exists

Baby Brezza's own settings finder will not give you a number until you type an
email address — and it makes you do it again for every lookup. Worse, each
search you run there is logged on their server with your email, IP address,
city, region, ZIP, browser, lot number and what you looked up, with no opt-in;
the consent checkbox only gates the marketing list, not the logging. The
settings API behind the page never actually requires the email — it is checked
by a single regex in your browser.

So this project pulled the whole dataset once and put it in a page that runs
entirely in your browser. Searching sends nothing anywhere; your lot number
never leaves the tab. The receipts — which requests fire, what they carry,
what is and isn't consent-gated — are in
[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## What's in it

* **3,867 Formula Pro Advanced settings** across 78 countries, searchable by
  brand, formula name, or barcode.
* **Lot-11 alternates.** Advanced and Advanced WiFi machines whose lot number
  (sticker underneath) starts with 11 use different numbers for 99 formulas —
  including Similac 360, Enfamil NeuroPro Gentlease, and Kirkland ProCare.
  Enter your lot number and the page shows the right one. The Mini never uses
  these.
* **The discontinued original Formula Pro**, which Baby Brezza's finder no
  longer offers at all. Its numbers come from a retired backend and have
  drifted an estimated ~27% since it froze — treat them as a starting point,
  not gospel. Details in [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Command-line lookup

If you have the repo checked out:

    ./lookup.py similac 360                    # Advanced + original, tagged
    ./lookup.py similac 360 --lot 1123ABC      # numbers for a lot-11 Advanced
    ./lookup.py --upc 070074680644             # barcode (Advanced only)
    ./lookup.py --alt-only enfamil             # only formulas with an alternate
    ./lookup.py kendamil -m pro                # the discontinued original

## Rebuilding the dataset

Everything is crawled from Baby Brezza's public, unauthenticated endpoints.
Run from the repo root:

    python3 crawlers/crawl_types.py     #  6,479 requests
    python3 crawlers/crawl_stages.py    # 41,297 requests
    python3 crawlers/crawl_settings.py  # 69,520 requests  -> data/raw/settings.jsonl
    python3 build_dataset.py            # needed before the next two
    python3 crawlers/crawl_alt.py       #  lot-11 alternates -> data/raw/alt_settings.jsonl
    python3 crawlers/crawl_images.py    #  freshness dates   -> data/raw/image_dates.jsonl
    python3 build_dataset.py            # -> site/data/formula_settings.json
    python3 build_page.py               # -> site/index.html

Every crawler appends to a `.jsonl` under `data/raw/` and skips completed work
on restart. Why the crawl has to be an exhaustive four-level walk — and how it
reconciles to zero gaps — is covered in
[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Layout

    crawlers/       API clients (api.py, legacy_api.py) and the crawl_*.py walks
    data/raw/       crawl output and logs — gitignored, regenerated and resumed locally
    data/           versioned inputs (brands_by_territory.json, the crosscheck table)
                    and staleness.json
    docs/           HOW-IT-WORKS.md — the reverse-engineering notes
    site/           what GitHub Pages serves: index.html and data/formula_settings.json

`site/data/formula_settings.json` is the versioned snapshot; it carries a
top-level `generated` date and a `counts` summary so a diff says what changed.
The two builders read only local files — no network — so the page can be rebuilt
from an existing crawl at any time.

---

**Once more, because it matters: check the number against your own tin before
mixing a bottle.**
