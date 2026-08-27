#!/usr/bin/env python3
"""Offline checks for the tripwire's diff logic.  No network.

Builds the observation the live API *would* return if nothing had changed --
straight out of the committed baseline and snapshot -- asserts that reads as
"unchanged", then perturbs it one way at a time and asserts each perturbation
is caught.  This is the half of watch.py that can be wrong silently; the
collection half is just crawlers/api.py.

    python3 scripts/test_watch.py
"""
import copy, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watch  # noqa: E402

BASELINE = json.load(open(watch.BASELINE))
SNAPSHOT = json.load(open(watch.SNAPSHOT))
EXP_IMAGES, EXP_SETTINGS = watch.expectations(SNAPSHOT)

failures = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        failures.append(name)


def quiet_observation():
    """What collect() would return from an API that has not moved."""
    sentinels = {}
    for terr, brand, typ, stage, want_alt in watch.SENTINELS:
        key = watch.skey(terr, brand, typ, stage)
        want = EXP_SETTINGS.get(key)
        if want is None:
            continue                       # reported separately by test_sentinels_exist
        got = {"false": want["setting"]}
        if want_alt:
            got["true"] = (want["alt_setting"] if want["alt_setting"] is not None
                           else want["setting"])
        sentinels[key] = got
    return {
        "territories": sorted(BASELINE["territories"]),
        "brands": copy.deepcopy(BASELINE["brands"]),
        "types": copy.deepcopy(BASELINE["types"]),
        "images": dict(EXP_IMAGES),
        "sentinels": sentinels,
        "errors": [],
    }


def verdict(obs):
    return watch.diff(BASELINE, EXP_IMAGES, EXP_SETTINGS, obs)


def main():
    print("sentinel queries resolve against the snapshot")
    missing = [s[:4] for s in watch.SENTINELS
               if watch.skey(*s[:4]) not in EXP_SETTINGS]
    check("all %d sentinels present in snapshot" % len(watch.SENTINELS), not missing,
          "missing: %s" % json.dumps(missing, ensure_ascii=False) if missing else "")

    print("baseline covers the catalogue")
    check("78 territories", len(BASELINE["territories"]) == 78)
    check("6479 (territory, brand) pairs",
          sum(len(v) for v in BASELINE["types"].values()) == 6479)

    print("quiet API reads as unchanged")
    base_obs = quiet_observation()
    d = verdict(base_obs)
    check("verdict unchanged", d["changed"] is False, watch.summarize(d))

    print("each perturbation is caught")

    o = copy.deepcopy(base_obs)
    o["brands"]["Canada"] = sorted(o["brands"]["Canada"] + ["Brand New Formula Co"])
    d = verdict(o)
    check("new brand", d["changed"] and "Brand New Formula Co"
          in d["brands"]["Canada"]["added"])

    o = copy.deepcopy(base_obs)
    t = "Canada"
    b = sorted(o["types"][t])[0]
    dropped = o["types"][t][b][0]
    o["types"][t][b] = o["types"][t][b][1:]
    d = verdict(o)
    check("removed type", d["changed"]
          and dropped in d["types"][t][b]["removed"])

    o = copy.deepcopy(base_obs)
    o["territories"] = [x for x in o["territories"] if x != "Albania"]
    d = verdict(o)
    check("removed territory", d["changed"]
          and "Albania" in d["territories"]["removed"])

    o = copy.deepcopy(base_obs)
    img = sorted(o["images"])[0]
    o["images"][img] = "2099-01-01"
    d = verdict(o)
    check("image re-dated", d["changed"] and d["images"]["moved_total"] == 1
          and d["images"]["moved"][0]["now"] == "2099-01-01")

    o = copy.deepcopy(base_obs)
    img = sorted(o["images"])[1]
    o["images"][img] = {"error": "HTTP Error 404: Not Found"}
    d = verdict(o)
    check("image unreachable", d["changed"] and d["images"]["unreachable_total"] == 1)

    # A brand-new upload id: the highest-numbered image answers under a bigger id.
    o = copy.deepcopy(base_obs)
    top = max(i for i in o["images"] if watch.seq_of(i) is not None)
    hot = "999999-" + top.split("-", 1)[1]
    o["images"][hot] = o["images"].pop(top)
    d = verdict(o)
    check("max upload id moved", d["changed"]
          and d["images"]["max_seq_now"] == 999999
          and d["images"]["max_seq_was"] != 999999)

    o = copy.deepcopy(base_obs)
    key = watch.skey(*watch.SENTINELS[0][:4])
    was = o["sentinels"][key]["false"]
    o["sentinels"][key]["false"] = (was or 0) + 1
    d = verdict(o)
    check("sentinel standard setting moved", d["changed"] and len(d["sentinels"]) == 1
          and d["sentinels"][0]["alt_mfg_setting"] is False)

    alt_key = next(watch.skey(*s[:4]) for s in watch.SENTINELS
                   if s[4] and watch.skey(*s[:4]) in base_obs["sentinels"])
    o = copy.deepcopy(base_obs)
    o["sentinels"][alt_key]["true"] = (o["sentinels"][alt_key]["true"] or 0) + 3
    d = verdict(o)
    check("sentinel lot-11 alternate moved", d["changed"] and len(d["sentinels"]) == 1
          and d["sentinels"][0]["alt_mfg_setting"] is True)

    o = copy.deepcopy(base_obs)
    o["sentinels"][key]["false"] = "__no-match__"
    d = verdict(o)
    check("sentinel vanished", d["changed"] and d["sentinels"][0]["now"] is None)

    print("transport errors are reported but do not flip the verdict on their own")
    o = copy.deepcopy(base_obs)
    o["errors"] = ["types Canada/Similac: timed out"]
    d = verdict(o)
    check("errors alone stay unchanged", d["changed"] is False and d["errors"])

    print("report shape")
    rep = watch.build_report(BASELINE, SNAPSHOT, base_obs)
    check("verdict field", rep["verdict"] == "unchanged")
    check("request count is the ~10k we advertise",
          9000 < rep["requests"] < 12000, str(rep["requests"]))
    check("summary is human-readable", "No differences" in rep["summary"])

    print("\n%d failed" % len(failures) if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
