#!/usr/bin/env bash
# Build every ticker in tickers.json plus the overview page.
#   ./run_all.sh [site_dir]                 (default: site/)
# Env: PYTHON, REQUIRE_LIVE=1 (skip the whole run when the market has no live quotes),
#      BASE_URL = the live site (e.g. https://kkrisc.github.io/avgo-report), used for previous editions and
#      to keep yesterday's page for a ticker whose run fails today.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python}"
case "$PY" in */*) PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")" ;; esac
SITE="${1:-$HERE/site}"
case "$SITE" in /*) ;; *) SITE="$PWD/$SITE" ;; esac
rm -rf "$SITE"; mkdir -p "$SITE" "$HERE/work/_shared"
emit() { if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "$1" >> "$GITHUB_OUTPUT"; fi; }

export CAPEX_JSON="$HERE/work/_shared/capex.json"
rm -f "$CAPEX_JSON"
"$PY" "$HERE/capex.py" "$CAPEX_JSON" > "$HERE/work/_shared/capex.log" 2>&1 || echo "AI-spending data unavailable this run"

conf() { "$PY" -c "import json,sys; t=[t for t in json.load(open('$HERE/tickers.json')) if t['sym']=='$1'][0]; print(t.get('$2',''))"; }
SYMS=$("$PY" -c "import json; print(' '.join(t['sym'] for t in json.load(open('$HERE/tickers.json'))))")

first=1; built=0
for S in $SYMS; do
  LOW=$(echo "$S" | tr '[:upper:]' '[:lower:]')
  LEGACY=$(conf "$S" legacy_prev)
  REQ=0; if [ "$first" = "1" ] && [ "${REQUIRE_LIVE:-0}" = "1" ]; then REQ=1; fi   # the first (most liquid) ticker decides
  SYM="$S" REQUIRE_LIVE="$REQ" PYTHON="$PY" \
    PREV_URL="${BASE_URL:+$BASE_URL/$LOW/data.json}" \
    PREV_URL_FALLBACK="$( [ -n "${BASE_URL:-}" ] && [ -n "$LEGACY" ] && echo "$BASE_URL/$LEGACY" )" \
    bash "$HERE/run.sh" "$SITE/$LOW/index.html" > "$HERE/work/$S.log" 2>&1
  rc=$?
  if [ "$rc" = "10" ]; then
    echo "No live quotes for $S; the market looks closed. Keeping the current site."
    emit "deploy=false"; exit 0
  fi
  first=0
  if [ "$rc" = "0" ]; then
    built=$((built+1)); echo "$S: built · $(grep -E '^wrote ' "$HERE/work/$S.log" | tail -1)"
  else
    echo "$S: FAILED (exit $rc). Last lines:"; tail -4 "$HERE/work/$S.log" | sed 's/^/    /'
    rm -rf "$SITE/$LOW"; mkdir -p "$SITE/$LOW"; kept=0
    if [ -n "${BASE_URL:-}" ]; then
      for f in index.html data.json summary.json; do
        if curl -sfL --max-time 30 -o "$SITE/$LOW/$f" "$BASE_URL/$LOW/$f"; then kept=1; else rm -f "$SITE/$LOW/$f"; fi
      done
    fi
    if [ "$kept" = "1" ] && [ -s "$SITE/$LOW/index.html" ]; then echo "    kept the previous $S page"
    else
      rm -rf "$SITE/$LOW"; mkdir -p "$SITE/$LOW"; echo "    no previous $S page to keep"
      REASON=$(grep -h '^STOP' "$HERE/work/$S.log" | tail -1 | sed -E 's/^STOP[^:]*: //')
      "$PY" -c "import json,sys; json.dump({'reason': sys.argv[1]}, open(sys.argv[2], 'w'))" "${REASON:-The data source returned too little data for this report.}" "$SITE/$LOW/status.json"
    fi
  fi
done

if [ "$built" = "0" ]; then echo "Nothing built; keeping the current site."; emit "deploy=false"; exit 1; fi
"$PY" "$HERE/build_hub.py" "$SITE" || { echo "overview page failed"; emit "deploy=false"; exit 1; }
emit "deploy=true"
