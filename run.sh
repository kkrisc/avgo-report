#!/usr/bin/env bash
# Run the options pipeline for one ticker and build its page.
#   SYM=NVDA ./run.sh [out.html]          (default: site/<sym>/index.html)
# Env: PYTHON (default "python"), SYM (default AVGO),
#      REQUIRE_LIVE=1   exit 10 instead of building when there are no live quotes,
#      PREV_URL         the live site's data.json for this ticker (previous edition + running history),
#      PREV_URL_FALLBACK an older location to try if PREV_URL is 404 (used once when the site layout changed),
#      CAPEX_JSON       shared AI-spending data (built here if missing and the ticker uses it).
# Exit codes: 0 built · 10 skipped, no live quotes · anything else failed (nothing written).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python}"
case "$PY" in */*) PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")" ;; esac   # make a relative path absolute before cd
export SYM="${SYM:-AVGO}"
LOW=$(echo "$SYM" | tr '[:upper:]' '[:lower:]')
OUT="${1:-$HERE/site/$LOW/index.html}"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac
CAPEX="${CAPEX_JSON:-$HERE/work/_shared/capex.json}"
WORK="$HERE/work/$SYM"
rm -rf "$WORK"; mkdir -p "$WORK"
cd "$WORK"

"$PY" "$HERE/fetch.py"
MODE=$("$PY" -c "import json; print(json.load(open('run.json'))['price_mode'])")
if [ "${REQUIRE_LIVE:-0}" = "1" ] && [ "$MODE" != "mid" ]; then
  echo "No live option quotes (market closed or data outage)."
  exit 10
fi

for step in engine vmodel rnd hist phys fix complex; do
  echo "== $step"
  "$PY" "$HERE/$step.py"
done

NEEDS_CAPEX=$("$PY" -c "import json; print(int(any(t['sym']=='$SYM' and t.get('capex') for t in json.load(open('$HERE/tickers.json')))))")
if [ "$NEEDS_CAPEX" = "1" ] && [ ! -s "$CAPEX" ]; then
  mkdir -p "$(dirname "$CAPEX")"; "$PY" "$HERE/capex.py" "$CAPEX" || echo "AI-spending data unavailable"
fi

# Previous edition: a 404 means this ticker has never been published (start from seeds/<SYM>.json if present);
# any other failure stops the run so a network blip can never reset the running history.
get() { curl -sS -L --max-time 30 -o prev_data.json -w "%{http_code}" "$1" || echo "000"; }
PREV_ARGS=()
if [ -n "${PREV_URL:-}" ]; then
  code=$(get "$PREV_URL")
  if [ "$code" = "404" ] && [ -n "${PREV_URL_FALLBACK:-}" ]; then code=$(get "$PREV_URL_FALLBACK"); fi
  if [ "$code" = "200" ]; then PREV_ARGS=(--prev prev_data.json)
  elif [ "$code" = "404" ]; then echo "No previous edition online yet for $SYM"
  else echo "Could not fetch the previous edition for $SYM (HTTP $code)."; exit 1
  fi
fi
"$PY" "$HERE/build_report.py" . "$OUT" --pages --capex "$CAPEX" ${PREV_ARGS[@]+"${PREV_ARGS[@]}"}
