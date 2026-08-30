# Formula Dial

A free, searchable page with every powder setting Baby Brezza publishes for
the Formula Pro Advanced family: Advanced, Advanced WiFi, and Mini. No email
address, no lookup limit, no tracking. Type a brand, get the number.

**Use it here: https://formuladial.com/**

Two things to know before you trust any number, from here or anywhere:

* **Check the number against your own tin before mixing a bottle.** This is
  infant food prep. Manufacturers reformulate, and the setting for the same
  brand name can differ by stage, market, and even your machine's lot number.
  If what the tin says and what the finder says disagree, believe neither —
  ask Baby Brezza.
* **The one date the finder shows is when the data was last checked.** It is
  bound to the hash of a complete crawl, so it says what it means. The
  dataset's own `image_date` is a different and weaker claim — when Baby
  Brezza last replaced a record's product image, "not touched since" rather
  than "verified on" — so the page does not carry it at all.

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
never leaves your device, and persists only if you ask the page to remember
it. The receipts — which requests fire, what they carry,
what is and isn't consent-gated — are in
[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## What's in it

* **3,867 Formula Pro Advanced settings** across 78 markets/territories, searchable by
  brand, formula name, or barcode — typed or scanned with your phone's camera,
  decoded on-device — or browsable without typing anything. Machine, market, and
  exact-tin steps stay visibly separate so a dial number only appears after all
  three are resolved.
* **Candidates narrow instead of piling up.** Rather than listing every match at
  once, the page folds them on the coarsest thing that still tells them apart —
  brand, then formula, then stage — skipping any level that would offer a single
  choice. Within one market those three fields are a primary key, so the ladder
  always ends on exactly one tin. An empty search with a market chosen browses
  the brand list, which is also where the common brands sit.
* **Markets you can name the way you say them.** The market box is a real
  combobox: it takes `USA`, `Poland`, `UK`, `Holland` and 400 other aliases, and
  rewrites itself to the market it resolved to, so the page never filters by a
  country it has not shown you. A button opens the full list without typing.
* **A way back out.** Every field clears on its own, *Start over* drops the
  current lookup while keeping your machine, market and lot, and *Forget this
  device* erases everything the page has stored.
* **Inspectable tins.** Locally served product images enlarge on hover, keyboard
  focus, click, or tap.
* **Evidence when a number has moved.** Baby Brezza revises settings with no
  change log or notice. Compared against a frozen ~2022 copy of their own data,
  59 of 276 unambiguous settings had changed — those results carry a struck-out
  "was" chip on the page.
* **Lot-11 alternates, asked for rather than whispered.** Advanced and Advanced
  WiFi machines whose lot number (sticker underneath) starts with 11 use
  different numbers for 99 formulas — including Similac 360, Enfamil NeuroPro
  Gentlease, and Kirkland ProCare. On those 99 the lot number is a fourth gate:
  the page shows no dial number until you enter it, then shows the one right
  number. Everywhere else it stays optional, and the Mini never uses it.

The discontinued original Formula Pro is intentionally not part of the app.
Its frozen raw data remains under `data/legacy/` as a historical research
artifact; it is not deployed, searched, or presented as usable current data.
Details are in [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Command-line lookup

If you have the repo checked out:

    ./lookup.py similac 360                    # the Advanced line — the default
    ./lookup.py similac 360 --lot 1123ABC      # required where a formula has
                                               # an alternate; 11… selects it
    ./lookup.py --upc 070074680644             # barcode (Advanced only)
    ./lookup.py --alt-only enfamil             # only formulas with an alternate

The command-line lookup has the same confidence boundary as the page. A single
market-specific match with nothing else beside it is `unique`; a missing
`--territory`, several text matches, a barcode mapping to different tins, a
formula whose setting depends on a lot number no `--lot` supplied, or a
same-named row Baby Brezza publishes no setting for is `ambiguous`, and
settings are withheld until the lookup is narrowed. A formula that Baby Brezza knows about
but for which it publishes no usable setting is `known_unavailable`; no match
at all is `not_found`. With `--json`, non-unique and unavailable outcomes use
an envelope with `state`, `results`, and `unavailable` fields. The original
Formula Pro is never a CLI lookup mode: its values remain only in the raw
archive under `data/legacy/`.

## Rebuilding the dataset

Everything is crawled from Baby Brezza's public, unauthenticated endpoints.
Run from the repo root:

    python3 crawlers/crawl_types.py     #  6,479 requests
    python3 crawlers/crawl_stages.py    # 41,297 requests
    python3 crawlers/crawl_settings.py  # 69,520 requests  -> data/raw/settings.jsonl
    python3 build_dataset.py            # needed before the next two
    python3 crawlers/crawl_alt.py       #  lot-11 alternates -> data/raw/alt_settings.jsonl
    python3 crawlers/crawl_images.py    #  freshness dates   -> data/raw/image_dates.jsonl
    python3 scripts/record_observation.py # bind the source-observation date to this crawl
    python3 build_dataset.py            # -> site/data/formula_settings.json
    python3 build_page.py               # -> site/index.html

Every crawler appends to a `.jsonl` under `data/raw/` and skips successfully
completed work on restart; failed requests remain retryable. Why the crawl has
to be an exhaustive four-level walk — and how it reconciles to zero gaps — is covered in
[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Layout

    crawlers/       API clients (api.py, legacy_api.py) and the crawl_*.py walks
    scripts/        automation: watch.py (the tripwire), remaining.py, refresh_brands.py
    data/raw/       crawl output and logs — gitignored, regenerated and resumed locally
    data/           versioned inputs (brands_by_territory.json, the crosscheck table),
                    watch_baseline.json, crawl_observation.json, setting_history.json
    data/legacy/    frozen historical crawls — archived, never deployed by the app
    docs/           HOW-IT-WORKS.md — the reverse-engineering notes
    site/           what GitHub Pages serves: index.html, current snapshot,
                    256px product previews, and self-hosted licensed fonts
    .github/        the weekly watch and the monthly full crawl

`site/data/formula_settings.json` is the versioned snapshot of the live
Advanced family; it carries separate `generated` and hash-bound `observed` dates
and a `counts` summary so a diff says what changed without calling a rebuild a
source check. `data/setting_history.json` begins empty and accumulates standard
or lot-11 movements between complete future crawls. The builder reads only local files — no network —
so the page can be rebuilt from an existing crawl at any time. Historical data
under `data/legacy/` is outside that build and deployment path.

The snapshot may also carry a top-level `unavailable` list. These are known
catalogue products for which the current API returned no usable dial setting;
each row records `brand`, `type`, `stage`, `territories`, `reason`, `upc`, and
`image`. They are deliberately separate from `records`: an unavailable row
must never be rendered as a guessed or blank number. Consumers should expose
it as “known, but no published setting” and direct the owner to Baby Brezza.

## Keeping it fresh

Baby Brezza edits this data — 385 of the images were re-uploaded in 2026 alone —
so the snapshot needs re-crawling, and a 69,520-request walk is too expensive to
run on a hunch. Two workflows, a cheap one and an expensive one:

**`scripts/watch.py`**, weekly (`.github/workflows/watch.yml`). About 10,000
requests, an hour and a half. It re-walks the catalogue's shape
(territories → brands → types), HEADs every image the snapshot references for
its `Last-Modified`, and re-queries ~30 popular formulas across the US,
Germany, France, the UK and Canada — the lot-11 alternates included,
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
`data/legacy/` as an archive; nothing schedules, publishes, or serves it.

    python3 scripts/watch.py              # the tripwire; 0 unchanged, 1 changed
    python3 scripts/test_watch.py         # its diff logic, offline
    python3 scripts/remaining.py all      # what a resumed crawl still owes

---

**Once more, because it matters: check the number against your own tin before
mixing a bottle.**
