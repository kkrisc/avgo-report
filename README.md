# AVGO options outlook

A daily, options-implied forecast for Broadcom (AVGO) at 7, 10, 20, 30 and 45 days, rebuilt from a fresh options chain
every trading day and published to GitHub Pages.

- **Live page:** https://kkrisc.github.io/avgo-report/
- **Refresh from a phone:** GitHub app → this repo → Actions → *Refresh AVGO report* → Run workflow. Reload the page after
  about five minutes. Leave "allow last trades" off unless the market is closed and you want a lower-quality build anyway.
- **Automatic refresh:** weekdays at 15:47 UTC (10:47 New York in winter, 11:47 in summer). If there are no live quotes
  (holiday, outage), the run skips publishing and the previous page stays up.

Educational analysis, not investment advice.

## How it works

`run.sh` runs the pipeline in `work/` and writes `site/index.html` plus `site/data.json`:

| Step | Script | What it does |
|---|---|---|
| 1 | `fetch.py` | Options chain, spot, and Yahoo's earnings calendar (next report + past reports). Off-hours it falls back to repriced last trades. |
| 2 | `engine.py` | Implied forward and discount factor per expiry (put-call parity), implied vol per strike |
| 3 | `vmodel.py` | Variance term structure: mean-reverting diffusion + a one-day jump on the next earnings date (if inside the listed expiries) |
| 4 | `rnd.py` | SVI smile per expiry, Breeden–Litzenberger risk-neutral densities at 5 horizons |
| 5 | `hist.py` | Daily price history, realized vol, earnings reactions |
| 6 | `phys.py` | Real-world forecast: volatility calibrated to the current regime + equity drift |
| 7 | `fix.py` | Positioning (open interest, put/call, max pain) |
| 8 | `complex.py` | AVGO vs NVDA, AMD, SMH, QQQ over 5 and 20 sessions |
| 9 | `build_report.py` | Fills `report_template.html`, compares with the previous edition, writes the page |

Each run downloads the live `data.json` to compare with the previous edition and extend the running history.
If that download fails for any reason other than "not published yet", the run stops so the history is never reset.
`history_seed.json` holds the first two editions (20 and 23 Nov 2026).

## Hand-written inputs

Everything on the page is computed from market data except two files, which only change when edited:

- `notes.json`: dated context notes (news, interpretation). Shown newest first.
- `scenarios.json`: the earnings scenario tree. It is tied to one report date and only appears while that report is
  still ahead. After it passes, the page shows a placeholder until a new tree is written.

## Run locally

```bash
uv venv --python 3.14 .venv && uv pip sync --require-hashes --python .venv/bin/python requirements.txt
PYTHON=.venv/bin/python ./run.sh site/index.html && open site/index.html
```

## Security

- The page is one self-contained file with a strict Content-Security-Policy: only its own inline script (allowed by
  SHA-256 hash, computed at build time), no external scripts, fonts, images or requests, no inline event handlers,
  `no-referrer`, `noindex`. Tooltips set text only.
- `requirements.txt` pins exact versions with SHA-256 hashes (built with `uv pip compile --generate-hashes`, using only
  releases at least two weeks old). CI installs with `--require-hashes --no-deps`.
- Actions are pinned to full commit SHAs. The workflow grants nothing by default: build gets `contents: read`, deploy gets
  `pages: write` + `id-token: write`. No secrets. Triggers are `workflow_dispatch` and `schedule` only.

## Maintenance

- **Dependency lock** (every month or two):
  `uv pip compile requirements.in --universal --python-version 3.14 --generate-hashes --exclude-newer <two weeks ago> -o requirements.txt`
- **Scheduled runs pause** if the repo has no activity for 60 days. GitHub emails a warning; re-enable from the
  Actions tab, or push any change (for example a new note).
- **NYSE holidays** in `earn.py` cover 2026–2028; extend the list before 2029.

## Limits

Yahoo data can be delayed or incomplete, earnings dates can be estimates, and the volatility calibration overlaps
heavily in time. The page's own "What this cannot tell you" section has the full list.
