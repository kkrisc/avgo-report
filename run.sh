#!/usr/bin/env bash
# Run the whole AVGO options pipeline and build the web page.
#   ./run.sh [out.html]            (default: site/index.html)
# Env: PYTHON (default "python"), REQUIRE_LIVE=1 to skip building when there are no live quotes,
#      PREV_URL = the live site's data.json (previous edition + running history; history_seed.json if unset).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python}"
case "$PY" in */*) PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")" ;; esac   # make a relative path absolute before cd
OUT="${1:-$HERE/site/index.html}"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac
WORK="$HERE/work"
rm -rf "$WORK"; mkdir -p "$WORK"
cd "$WORK"

emit() { if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "$1" >> "$GITHUB_OUTPUT"; fi; }

"$PY" "$HERE/fetch.py"
MODE=$("$PY" -c "import json; print(json.load(open('run.json'))['price_mode'])")
if [ "${REQUIRE_LIVE:-0}" = "1" ] && [ "$MODE" != "mid" ]; then
  echo "No live option quotes (market closed or data outage). Keeping the current page."
  emit "deploy=false"
  exit 0
fi

for step in engine vmodel rnd hist phys fix complex; do
  echo "== $step"
  "$PY" "$HERE/$step.py"
done

# Previous edition: a 404 means the site has never been published (use the seed); any other failure stops the
# run so a network blip can never reset the running history.
PREV_ARGS=()
if [ -n "${PREV_URL:-}" ]; then
  code=$(curl -sS -L --max-time 30 -o prev_data.json -w "%{http_code}" "$PREV_URL" || echo "000")
  if [ "$code" = "200" ]; then PREV_ARGS=(--prev prev_data.json)
  elif [ "$code" = "404" ]; then echo "No previous edition online yet; starting from history_seed.json"
  else echo "Could not fetch the previous edition (HTTP $code). Keeping the current page."; emit "deploy=false"; exit 1
  fi
fi
"$PY" "$HERE/build_report.py" . "$OUT" --pages ${PREV_ARGS[@]+"${PREV_ARGS[@]}"}
emit "deploy=true"
