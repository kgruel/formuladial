"""Client for Baby Brezza's *legacy* settings backend.

The current finder (api.py) only knows the Formula Pro Advanced family.  The
retired page babybrezza.com/pages/formula-pro-settings-old -- still archived in
the Wayback Machine, and whose script `formulapro-old.js` is still served live
from Shopify's CDN -- talks to an older backend that takes a `model_type`
parameter, and `model_type=pro` is the discontinued original Formula Pro
(FRP0045).  That backend is still up.

Everything is POST form-encoded and answers with HTML fragments: <option> lists
for the cascading selects, and a small <table> of stage/setting rows.

    filterproduct                    model_type=                     -> territories
    filterproduct/getbrand           territory_id=&model_type=       -> brands
    filterproduct/gettypepro         brand_id=&territory_id=&model_type=  -> types
    filterproduct/getbrandtosetting  brand_id=&territory_id=&model_type=  -> settings
                                     (used when a brand has no type list)
    filterproduct/getsetting         type_id=&brand_id=&territory_id=&model_type=

Values in the option lists are URL-encoded and must be posted back *as sent*,
so this module keeps the raw encoded value alongside the display label.
"""
import html, re, time, urllib.request

BASE = "https://babybrezzaserver.com/index.php/filterproduct"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://babybrezza.com/",
}

OPTION = re.compile(r'<option\s[^>]*value="([^"]*)"[^>]*>(.*?)</option>', re.S)
ROW = re.compile(r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>', re.S)


def post(path, retries=4, **fields):
    """POST a form and return the raw HTML fragment."""
    url = BASE + (("/" + path) if path else "")
    body = "&".join(f"{k}={v}" for k, v in fields.items())  # values are pre-encoded
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=body.encode(), headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def options(fragment):
    """[(raw_value, label)] for a select fragment, dropping the placeholder."""
    out = []
    for value, label in OPTION.findall(fragment or ""):
        if not value:
            continue
        out.append((value, html.unescape(re.sub(r"<[^>]+>", "", label)).strip()))
    return out


def rows(fragment):
    """[(stage, setting)] from a settings table fragment."""
    out = []
    for stage, setting in ROW.findall(fragment or ""):
        stage = html.unescape(re.sub(r"<[^>]+>", "", stage)).strip()
        setting = html.unescape(re.sub(r"<[^>]+>", "", setting)).strip()
        if stage.upper() == "STAGE" and setting.upper() == "SETTING":
            continue
        out.append((stage, setting))
    return out
