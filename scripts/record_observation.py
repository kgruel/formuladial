#!/usr/bin/env python3
"""Record when a complete settings crawl was actually observed upstream."""
import datetime
import hashlib
import json
import os

RAW = "data/raw/settings.jsonl"
OUT = "data/crawl_observation.json"


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def query_count(path):
    latest = set()
    with open(path) as source:
        for line in source:
            try:
                row = json.loads(line)
                query = row.get("query")
                if isinstance(query, list) and len(query) == 4:
                    latest.add(tuple(query))
            except (ValueError, TypeError):
                pass
    return len(latest)


def main():
    if not os.path.exists(RAW):
        raise SystemExit(f"{RAW} is missing")
    observation = {
        "observed": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "queries": query_count(RAW),
        "settings_sha256": digest(RAW),
    }
    with open(OUT, "w") as target:
        json.dump(observation, target, indent=2, sort_keys=True)
        target.write("\n")
    print(f"recorded {observation['queries']} source queries observed "
          f"{observation['observed']}")


if __name__ == "__main__":
    main()
