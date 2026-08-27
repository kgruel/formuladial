#!/usr/bin/env bash
# Run the crawl in order until it finishes or the job clock runs out.
#
# The full walk is 69,520 requests at the crawlers' pacing -- about 10 hours,
# where a GitHub-hosted job may live 6.  Every crawler appends to a .jsonl and
# skips completed work on restart, so the shape of the fix is: run each layer
# under `timeout`, stop at a deadline comfortably inside the job limit, let the
# workflow persist data/raw/ and re-dispatch, and pick up exactly where this
# attempt stopped.  Nothing is lost and nothing is re-requested.
#
# Writes `status=complete` or `status=incomplete` to $GITHUB_OUTPUT (or stdout
# when run outside Actions) and always exits 0 -- "not finished yet" is the
# expected case, not a failure.
#
# Env:
#   DEADLINE_MIN  minutes this attempt may spend crawling (default 280)
set -uo pipefail
cd "$(dirname "$0")/../.."

DEADLINE_MIN="${DEADLINE_MIN:-280}"
deadline=$(( DEADLINE_MIN * 60 ))
start=$SECONDS
left() { echo $(( deadline - (SECONDS - start) )); }

emit() {
  if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "status=$1" >> "$GITHUB_OUTPUT"; fi
  echo "status=$1"
}

# layer <name> <script...>  -- returns 1 if the layer is still unfinished.
layer() {
  local name="$1"; shift
  local n
  n=$(python3 scripts/remaining.py "$name" 2>/dev/null) || true
  if [ "${n:-1}" = "0" ]; then
    echo "== $name: already complete"
    return 0
  fi
  local budget; budget=$(left)
  if [ "$budget" -lt 120 ]; then
    echo "== $name: $n to go, out of clock"
    return 1
  fi
  echo "== $name: $n to go, ${budget}s of budget"
  timeout "${budget}s" "$@"
  local rc=$?
  [ $rc -eq 124 ] && echo "== $name: hit the deadline, will resume next attempt"
  n=$(python3 scripts/remaining.py "$name" 2>/dev/null) || true
  echo "== $name: $n remaining after this attempt"
  [ "${n:-1}" = "0" ]
}

# Layers 1-3 walk the catalogue.  A partial settings crawl must not be built
# into the snapshot -- crawl_alt.py and crawl_images.py take their work list
# *from* that snapshot, so building early would send them at half a dataset.
layer types    python3 crawlers/crawl_types.py    || { emit incomplete; exit 0; }
layer stages   python3 crawlers/crawl_stages.py   || { emit incomplete; exit 0; }
layer settings python3 crawlers/crawl_settings.py || { emit incomplete; exit 0; }

echo "== building the interim dataset (alt/images take their work list from it)"
python3 build_dataset.py || { emit incomplete; exit 0; }

layer alt    python3 crawlers/crawl_alt.py    || { emit incomplete; exit 0; }
layer images python3 crawlers/crawl_images.py || { emit incomplete; exit 0; }

# The legacy backend is frozen -- crawled once, kept as a historical record.
# It is deliberately not part of any schedule.

emit complete
exit 0
