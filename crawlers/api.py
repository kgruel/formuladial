"""Thin client for Baby Brezza's public formula-settings API.

Discovered on the Canadian site's settings finder (an Astro/Vue island that
calls its own server routes).  No auth, no email gate -- the email field on the
official page is validated client-side only and is never sent anywhere here.

Endpoints, all GET under BASE:
    territories
    brands    ?territory=
    types     ?territory=&brand=
    stages    ?territory=&brand=&type=
    settings  ?territory=&brand=&type=&stage=&alt_mfg_setting=false
    settings/upc ?upc=&alt_mfg_setting=false

`settings` returns one record; `settings/upc` returns a list.  A record looks
like:
    {"setting": 4, "brand": "Enfamil", "type": "A2 Premium", "stage": "1",
     "territory": ["United States of America"], "upc": ["300875126400"],
     "image": ["5a33fc11-....jpg"]}

The `territory` array lists *every* territory the record belongs to, which is
what makes the crawl's de-duplication lossless.
"""
import json, time, urllib.error, urllib.parse, urllib.request

BASE = "https://babybrezza.ca/api/formula-settings"
IMAGE_BASE = "https://babybrezzacloud.com/uploads/formulaprotool/original/"

# The origin 403s requests without a browser User-Agent.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://babybrezza.ca/en/formula-pro-settings-finder",
}


class EmptyResponse(Exception):
    """The endpoint answered 200 with a body that isn't JSON (no match)."""


def get(path, retries=4, **params):
    """GET a JSON endpoint, retrying transport/HTTP failures but not no-match."""
    url = f"{BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                body = r.read()
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
            continue
        try:
            return json.loads(body)
        except ValueError:
            # 200 with an empty/plain body means "no such combination".
            raise EmptyResponse(url)
    raise last


def head(url, retries=3):
    """HEAD a URL with the same browser headers, returning the response headers.

    Used for the image `Last-Modified` sweep (crawl_images.py) and the weekly
    tripwire (scripts/watch.py) -- one place that knows how to talk to the
    origin, so neither has to hand-roll a urllib request.
    """
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as r:
                return dict(r.headers)
        except urllib.error.HTTPError as e:
            raise                                   # 404/403 are answers, not flakes
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last
