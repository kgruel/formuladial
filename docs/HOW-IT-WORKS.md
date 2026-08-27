# How this works

The reverse-engineering notes behind the dataset: where the numbers come from,
what the official finder does with your data, and every quirk found along the
way. The [README](../README.md) covers what this project is and how to use it.

## What the official finder's email ceremony actually buys them

All from `formula-settings.js` on babybrezza.com. Three destinations, one of
which asks permission:

1. **Every lookup is logged, with no opt-in.** Each search POSTs to
   `babybrezzaserver.com/index.php/without_response/getsetting` carrying
   `email`, `ip_address`, `user_agent`, `city`, `state_prov`, `zip`, `country`,
   `language`, `touch_device`, `lot_number`, and the brand/type/territory you
   looked up. This is not tied to the consent checkbox and fires regardless.
   The location fields come from an IP-geolocation script the page loads, which
   writes them into cookies the logger reads back.
2. **Marketing lists, properly gated.** `optin.babybrezza.com/api/subscribe/listrak`
   on the US site, `/klaviyo` elsewhere — but only when the "I agree to receive
   marketing emails" box is ticked (`if(!optInEl||!optInEl.checked)return`).
3. **Warranty registration**, `portal.babybrezza.com/api/warranty/activate`.
   Optional and skippable.

The email itself is checked by one regex in the browser. The settings API never
asks for it. `validateEmail()` is what gates the territory dropdown, the barcode
scanner and the barcode submit — that is the entire lock.

## Privacy contract of this app

The point of the local snapshot is that a search is a local operation: the
formula text, barcode, market, machine choice, and lot number must not be sent
to any service. The machine and market may be remembered for convenience, but
the current formula query is session-only (in-memory or `sessionStorage`), not
in persistent `localStorage`; closing the tab should clear it. A future change
to persistence needs to preserve that boundary and should never store a lot
number or formula-search history by default. The setting-change timeline is
public source-data history and contains no user activity.

The deployed page must also be self-contained with respect to presentation
assets. Fonts and scripts should be bundled or served from this repository,
not fetched from Google Fonts or another third-party CDN. Otherwise a page
with a local search can still disclose a visit, IP address, and browser
metadata to an asset provider. The barcode decoder is already vendored and
loaded same-origin on demand. These are release requirements, not claims that
the upstream Baby Brezza finder shares this privacy model.

## The API

Unauthenticated GETs. The Canadian site proxies them at
`babybrezza.ca/api/formula-settings/*`; upstream is
`api.babybrezzacloud.com/formulas/finder/*`.

    territories | brands ?territory= | types ?territory=&brand=
    stages ?territory=&brand=&type=
    settings ?territory=&brand=&type=&stage=&alt_mfg_setting=
    settings/upc ?upc=

    {"setting":4,"brand":"Enfamil","type":"A2 Premium","stage":"1",
     "territory":["United States of America"],"upc":["300875126400"],"image":["5a33….jpg"]}

The origin 403s requests without a browser `User-Agent`.

**`settings/upc` is exact-string, and it misses its own data.** Verified live:
`upc=300875126400` returns Enfamil A2 Premium; the same barcode in 13-digit EAN
form, `upc=0300875126400`, returns nothing. The official page's scanner
(QuaggaJS with `upc_reader` + `ean_reader`, behind the same email gate) hands
back exactly that 13-digit form for US tins, so a perfect scan can still show
"No Results Found For Barcode". The dataset itself stores a mix — 3,124
thirteen-digit codes against 674 twelve-digit — so our page canonicalises both
sides of the comparison (a leading 0 on a 13-digit code is dropped) before
matching. Our scanner uses the native `BarcodeDetector` where it has a real
backend, and otherwise the same Quagga in its maintained fork
(`site/vendor/quagga2-1.12.1.min.js`, MIT), loaded same-origin on demand;
frames are decoded on-device.

## One dataset, three machines — and a fourth dimension

No model is ever sent. Advanced, Advanced WiFi and Mini build identical
requests, and Baby Brezza's Mini page justifies it: the Mini uses "the same
precision mixing technology as best-selling Formula Pro Advanced".

What *does* split the line is manufacturing revision:

    altMfgSetting = this.isFormulaProAdvancedActive()
                      ? (lotPrefix.startsWith("11") ? "true" : "false")
                      : ""
    // and, at the bottom of the same file:
    input.getLotPrefix = () => input.value

`isFormulaProAdvancedActive()` matches "wifi" or "formula-pro-advanced" in the
product URL/name, so the **Mini** (`/products/formula-pro-mini`) fails both and
never takes this branch. The lot number is on the sticker underneath the
machine; the field is uppercased and capped at 14 characters.

`crawlers/crawl_alt.py` probes every Advanced record both ways. **99 of 3,867 differ**,
97 of them US formulas, including most mainstream ones:

    Similac 360 Total Care         5 -> 6      Kirkland ProCare          5 -> 6
    Enfamil NeuroPro Gentlease     5 -> 7      Member's Mark Advantage   4 -> 7
    Parent's Choice Sensitivity    5 -> 6      Bobbie Organic +DHA ARA   4 -> 6

Usually +1 or +2, occasionally lower (Wellsley Farms Infant Premium 7 -> 5,
HiPP HA2 Combiotik 4 -> 3), twice a drop to 0. The page takes a lot number and
shows the alternate as the main number with the standard one beside it;
`lookup.py --lot 11X` does the same.

## Dating and observing the data

The settings endpoint has no timestamp, so “page generated” must never be
presented as “source checked.” After a complete crawl,
`scripts/record_observation.py` records the UTC observation date together with
the SHA-256 of `settings.jsonl`; `build_dataset.py` refuses to publish the date
unless the hash still matches. Results can therefore say “Last checked against
Baby Brezza’s data on …” without borrowing an unrelated image date. Complete future
crawls are compared per formula and market, and actual standard or lot-11
movements are appended to `data/setting_history.json` for the result timeline.

Nothing in the API carries a timestamp, but every Advanced record points at an
image on babybrezzacloud.com and those files answer HEAD with `Last-Modified`.
`crawlers/crawl_images.py` sweeps all 3,522.

    2023: 1601    2024: 816    2025: 720    2026: 385
    oldest 2023-01-03   newest 2026-08-25

So the Advanced data is live and actively curated. **Caveat, and it matters:
this dates the image, not the number.** A record whose picture was uploaded in
2023 may have had its setting revised since without the picture changing. Read
it as image provenance, never as the setting’s “last checked” date. The filenames also carry what
looks like a sequential upload id (`20467-<uuid>.png`) which agrees with the
dates about 86% of the time — useful for ordering, not for dating.

## Why the crawl is a full four-level walk

Assuming a (brand, type) means the same thing everywhere is wrong. Measured on
the live API:

* type lists differ across territories for **16 of 30** sampled multi-territory
  brands (Nestlé NAN has 52 types in Albania, 9 in Australia/New Zealand);
* stage lists differ for ~9% of (brand, type) pairs seen in several territories
  (Aptamil Comfort is `From Birth` in the EU, `1`/`2` in Bahrain).

There is no shortcut at the settings layer either. A record's `territory` array
looks like it might name every region it covers — it does not; the API filters
it to whatever you asked for. The walk is exhaustive: 69,520 queries.

Reconciled afterwards, zero gaps:

| layer | expected | crawled | missing |
|---|---|---|---|
| (territory, brand) pairs | 6,479 | 6,479 | 0 |
| (territory, brand, type) triples | 41,297 | 41,297 | 0 |
| settings queries | 69,520 | 69,520 | 0 |
| alternate-setting probes | 3,867 | 3,867 | 0 |
| image dates | 3,522 | 3,522 | 0 |
| legacy (territory, brand) pairs | 556 | 556 | 0 |

## Known data quirks

* **Known but unavailable is not the same as not found.** A current snapshot may
  carry a top-level `unavailable` list alongside `records`. Each entry has
  `brand`, `type`, `stage`, `territories`, `reason`, `upc`, and `image`; it means the
  catalogue recognized the product but the settings endpoint did not publish a
  usable dial value. Builders and clients must keep these rows separate from
  numeric records and show an explicit “known, but no published setting” state.
  A search with no matching `records` or `unavailable` entries is the distinct
  `not_found` state.
* **Lookup confidence has four states.** A single market-specific result is `unique`;
  multiple candidates are `ambiguous`; a known product without a usable value
  is `known_unavailable`; and an empty search is `not_found`. Barcode results
  with conflicting settings must remain non-actionable until a territory is
  selected. Text searches may display identifying candidate details, but no
  setting, until a market and exact tin reduce the result to one.
* **76 completed queries publish no dial record.** Forty catalogue types expose
  no stage even though the settings endpoint requires one; they are recorded as
  explicit no-matches. Another 36 return a structured record with
  `setting: null`. Both are upstream answers rather than transport failures,
  and both remain visible in the snapshot's `crawl_stats` instead of being
  converted into a number.
* **43 Advanced records answer with `setting: 0`.** The dial runs 1–10, so 0 is
  not a position on it. Twelve also carry the stage `NC`; the rest are mostly
  toddler drinks, amino-acid formulas and milk powders. Neither of Baby Brezza's
  own UIs special-cases it — they print "0". Shown here as *No dial position*.
  The drift comparison below makes it more interesting: Burt's Bees moved from a
  real 5 to 0, so it is a value they changed *to*, not a missing entry.
* The historical original-Pro archive contains one genuine conflict:
  `Novalac Allernova AR+`, 0-36 Months, European Union has rows for settings
  **8** and **5**. This is one reason it is not exposed as current app data.
* Territory names differ between the current data and historical archive
  ("European Union" in the old set, individual countries in the new;
  "United States Of America" vs "…of America"). The app uses only the current
  API's territory list.
* Search highlighting is skipped on names containing a character NFKD expands
  (`Reguline™`), since folding shifts every offset after it. Matching is
  unaffected.

## The original Formula Pro, kept for the record

Discontinued (FRP0045) and dropped from Baby Brezza's finder entirely. Its data
survives only because the retired page `babybrezza.com/pages/formula-pro-settings-old`
hardcodes `model_type=pro`, its script `formulapro-old.js` is still served from
Shopify's CDN, and the backend it points at still answers:

    filterproduct                    model_type=            -> territories
    filterproduct/getbrand           territory_id=&model_type=
    filterproduct/gettypepro         brand_id=&territory_id=&model_type=
    filterproduct/getbrandtosetting  brand_id=&territory_id=&model_type=
    filterproduct/getsetting         type_id=&brand_id=&territory_id=&model_type=

POST form-encoded, HTML fragments back. `getsetting` returns every stage in one
table. Brands whose `gettypepro` is empty are answered by `getbrandtosetting` —
skip that branch and you drop them silently.

**Verified** against `data/crosscheck_loveorganicbaby.json`, a retailer table listing
both machines: Kendamil 1/2/3 → 2/1/1 and Lebenswert → 7/9/10 on the original,
against 4/4/4 for the same tins on the Advanced.

**How stale.** That backend also holds a frozen `model_type=advanced` copy of a
line that *is* still maintained, which makes it measurable:

    $ python3 crawlers/crawl_legacy.py advanced && python3 staleness.py
    unambiguous exact-name comparisons: 276
    settings changed                  : 59  (21%)

Assuming both halves froze together, ~21% is the best estimate of how far the
original's numbers have drifted. It is an estimate, not a correction — there is
nothing to check them against. Only unambiguous, single-valued comparisons
surface on the page: where the frozen copy disagrees with today's number, the
matching Advanced results carry a struck-out *was N* chip. Multi-valued
regional comparisons are excluded. Dating it independently: the original's US set has
Bobbie but not ByHeart, Bubs or Kendamil, all of which reached US shelves in
2022; the retired page was still archived in 2023.

This set contains 110 **`NOT COMPATIBLE`** rows — formulas that machine cannot
dispense at all. No barcodes, no lot-number variants, no dates.

It is not published by the app. The raw crawl remains versioned under
`data/legacy/` solely as a historical research artifact; current builds and the
deployed page do not read, embed, search, or link its values as a lookup mode.
