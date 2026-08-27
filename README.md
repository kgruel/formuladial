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
  brand, formula name, or barcode — typed or scanned with your phone's camera,
  decoded on-device.
* **Evidence when a number has moved.** Baby Brezza revises settings with no
  change log or notice. Compared against a frozen ~2022 copy of their own data,
  81 of 299 comparable settings had changed — those results carry a struck-out
  "was" chip on the page.
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
    scripts/        automation: watch.py (the tripwire), remaining.py, refresh_brands.py
    data/raw/       crawl output and logs — gitignored, regenerated and resumed locally
    data/           versioned inputs (brands_by_territory.json, the crosscheck table),
                    watch_baseline.json and staleness.json
    data/legacy/    the original Formula Pro crawl — versioned, because that backend
                    is frozen and will never be crawled again
    docs/           HOW-IT-WORKS.md — the reverse-engineering notes
    site/           what GitHub Pages serves: index.html and data/formula_settings.json
    .github/        the weekly watch and the monthly full crawl

`site/data/formula_settings.json` is the versioned snapshot; it carries a
top-level `generated` date and a `counts` summary so a diff says what changed.
The two builders read only local files — no network — so the page can be rebuilt
from an existing crawl at any time.

## Keeping it fresh

Baby Brezza edits this data — 385 of the images were re-uploaded in 2026 alone —
so the snapshot needs re-crawling, and a 69,520-request walk is too expensive to
run on a hunch. Two workflows, a cheap one and an expensive one:

**`scripts/watch.py`**, weekly (`.github/workflows/watch.yml`). About 10,000
requests, an hour and a half. It re-walks the catalogue's shape
(territories → brands → types), HEADs every image the snapshot references for
its `Last-Modified` and upload id, and re-queries ~30 popular formulas across
the US, Germany, France, the UK and Canada — the lot-11 alternates included,
since those are the numbers known to move. It prints a JSON verdict and exits 0
for *unchanged*, 1 for *changed*. On a change it opens (or comments on) an issue
with the delta and dispatches the full crawl.

Two things it deliberately does not do. It does not diff live type lists against
the snapshot: 194 live (territory, brand, type) combinations legitimately answer
with no setting, so that comparison would cry wolf every week. It diffs against
`data/watch_baseline.json` instead, which the full crawl rewrites each time.
And it does not hardcode the settings it expects — only the queries. The
expected values are read from the committed snapshot at run time, so a real
refresh re-arms the tripwire by itself.

**The full crawl**, monthly or on demand (`.github/workflows/full-crawl.yml`).
The walk takes about ten hours; a GitHub Actions job may live six. Since every
crawler already resumes from its `.jsonl`, a run is one *attempt*: restore
`data/raw/` from the cache, crawl until a 4h40m deadline, save it back, and if
`scripts/remaining.py` still reports work left, dispatch the workflow again one
attempt further along (capped at six). When it finishes, it rebuilds the
dataset, the page and the baseline, commits whatever moved under `site/` with
the count delta in the commit message, and deploys Pages.

The cache resumes a cycle; it never starts one. A fresh run skips the restore
entirely — otherwise next month's crawl would inherit last month's *finished*
cache, find nothing to do, and republish stale data forever.

The original Formula Pro's backend is frozen. It was crawled once and lives in
`data/legacy/`, versioned rather than regenerated, and nothing schedules it.

    python3 scripts/watch.py              # the tripwire; 0 unchanged, 1 changed
    python3 scripts/test_watch.py         # its diff logic, offline
    python3 scripts/remaining.py all      # what a resumed crawl still owes

---

**Once more, because it matters: check the number against your own tin before
mixing a bottle.**
