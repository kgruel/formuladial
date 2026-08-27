# Baby Brezza settings, without the runaround

Baby Brezza's settings finder will not give you a number until you hand over an
email address, and it makes you do it again for every lookup. This pulls the
whole dataset once and gives you a local copy you can grep, plus a searchable
page.

Primary target is the **Formula Pro Advanced** family. The discontinued original
is kept alongside it as a historical record — see the last section.

## What the ceremony actually buys them

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

`crawl_alt.py` probes every Advanced record both ways. **99 of 3,867 differ**,
97 of them US formulas, including most mainstream ones:

    Similac 360 Total Care         5 -> 6      Kirkland ProCare          5 -> 6
    Enfamil NeuroPro Gentlease     5 -> 7      Member's Mark Advantage   4 -> 7
    Parent's Choice Sensitivity    5 -> 6      Bobbie Organic +DHA ARA   4 -> 6

Usually +1 or +2, occasionally lower (Wellsley Farms Infant Premium 7 -> 5,
HiPP HA2 Combiotik 4 -> 3), twice a drop to 0. The page takes a lot number and
shows the alternate as the main number with the standard one beside it;
`lookup.py --lot 11X` does the same.

## Dating the data

Nothing in the API carries a timestamp, but every Advanced record points at an
image on babybrezzacloud.com and those files answer HEAD with `Last-Modified`.
`crawl_images.py` sweeps all 3,522.

    2023: 1601    2024: 816    2025: 720    2026: 385
    oldest 2023-01-03   newest 2026-08-25

So the Advanced data is live and actively curated. **Caveat, and it matters:
this dates the image, not the number.** A record whose picture was uploaded in
2023 may have had its setting revised since without the picture changing. Read
it as "not touched since", never "verified on". The filenames also carry what
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

## Running it

    python3 crawl_types.py        #  6,479 requests
    python3 crawl_stages.py       # 41,297 requests
    python3 crawl_settings.py     # 69,520 requests  -> settings.jsonl
    python3 build_dataset.py      # needed before the next two
    python3 crawl_alt.py          #  lot-11 alternates -> alt_settings.jsonl
    python3 crawl_images.py       #  freshness dates   -> image_dates.jsonl
    python3 build_dataset.py      # -> formula_settings.json
    python3 build_page.py         # -> page.html

Every crawler appends to a `.jsonl` and skips completed work on restart.

## Looking things up

    ./lookup.py similac 360                    # Advanced + original, tagged
    ./lookup.py similac 360 --lot 1123ABC      # numbers for a lot-11 Advanced
    ./lookup.py --upc 070074680644             # barcode (Advanced only)
    ./lookup.py --alt-only enfamil             # only formulas with an alternate
    ./lookup.py kendamil -m pro                # the discontinued original

## Known data quirks

* **43 Advanced records answer with `setting: 0`.** The dial runs 1–10, so 0 is
  not a position on it. Twelve also carry the stage `NC`; the rest are mostly
  toddler drinks, amino-acid formulas and milk powders. Neither of Baby Brezza's
  own UIs special-cases it — they print "0". Shown here as *No dial position*.
  The drift comparison below makes it more interesting: Burt's Bees moved from a
  real 5 to 0, so it is a value they changed *to*, not a missing entry.
* One genuine conflict: `Novalac Allernova AR+`, 0-36 Months, European Union
  returns two rows — settings **8** and **5**. Reported, not silently resolved.
* Territory names differ between the two backends ("European Union" in the old
  set, individual countries in the new; "United States Of America" vs "…of
  America"). The page offers only the selected model's list.
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

**Verified** against `crosscheck_loveorganicbaby.json`, a retailer table listing
both machines: Kendamil 1/2/3 → 2/1/1 and Lebenswert → 7/9/10 on the original,
against 4/4/4 for the same tins on the Advanced.

**How stale.** That backend also holds a frozen `model_type=advanced` copy of a
line that *is* still maintained, which makes it measurable:

    $ python3 crawl_legacy.py advanced && python3 staleness.py
    comparable on exact name: 299
    settings changed        : 81  (27%)

Assuming both halves froze together, ~27% is the best estimate of how far the
original's numbers have drifted. It is an estimate, not a correction — there is
nothing to check them against. Dating it independently: the original's US set has
Bobbie but not ByHeart, Bubs or Kendamil, all of which reached US shelves in
2022; the retired page was still archived in 2023.

This set contains 110 **`NOT COMPATIBLE`** rows — formulas that machine cannot
dispense at all. No barcodes, no lot-number variants, no dates.

**Check the number against your own tin before mixing a bottle.**
