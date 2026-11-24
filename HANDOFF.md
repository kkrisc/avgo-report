# AVGO report: session handoff

Last updated: Tue 24 Nov 2026. Read this first when picking up the work in a new session, then continue from
**9. Next steps**.

> This file is committed to a **public** repo, so it contains no personal or machine-specific details. Those (local
> paths, git credential setup, Claude memory location, links to private pages) are in **`avgo-report-local.md`**, which
> sits next to this file on the user's Mac and is excluded from git.

---

## 0. Update, 24 Nov 2026 evening: multi-ticker site

- The repo now builds **six reports** from `tickers.json`: AVGO, NVDA, TSM, ANT, SPCX, NGNE, each at `/<ticker>/`, with
  an overview page at the site root (`build_hub.py`) and a sticky menu on every page. `run_all.sh` replaces `run.sh` in
  the workflow ("Refresh options reports", timeout 45 min). Broadcom's history carries over from the old root
  `data.json` through `legacy_prev` in `tickers.json`.
- **New sections:** "What the biggest AI buyers are spending" (`capex.py`: quarterly capex and operating cash flow for
  MSFT, GOOGL, AMZN, META, ORCL, on AVGO/NVDA/TSM pages) and "What analysts expect" (consensus revenue/EPS and price
  targets, all tickers). The next-year revenue consensus and mean price target are tracked in the edition history.
- **Thin data:** ANT (listed 19 Nov, options since 23 Nov) had quotes on only 5 of 58 contracts on Yahoo, and NGNE's
  quotes are 70–190% wide with only 1 of 4 expirations usable. Neither builds yet; the overview shows the reason and the
  daily run retries. SPCX builds with a "Read with care" notice (no earnings history yet).
- First live-quote local run, 24 Nov 14:27 ET: AVGO priced ±12.2% for 9 Dec (±10.8% at the 23 Nov close).
- The first scheduled run (24 Nov 15:47 UTC) did not fire; a manual run at 16:39 UTC succeeded. GitHub often skips a new
  workflow's first scheduled slot.

## 1. Where things stand (single-ticker setup, superseded by section 0)

| What | Value |
|---|---|
| Live page | https://kkrisc.github.io/avgo-report/ |
| Repo (public) | https://github.com/kkrisc/avgo-report |
| Workflow | `.github/workflows/report.yml` ("Refresh AVGO report") |
| Schedule | Weekdays 15:47 UTC (10:47 New York in winter, 11:47 in summer) |
| First run | Actions run `45357050085`, 24 Nov 2026, manual with "allow last trades" (market closed). Build + deploy green, page and `data.json` verified live |
| Data on the page after that run | 23 Nov 2026 close, last-trade mode. First live (bid/ask) edition expected from the 24 Nov 15:47 UTC scheduled run |

**Refresh from a phone:** GitHub app → avgo-report → Actions → Refresh AVGO report → Run workflow. Leave "allow last
trades" off during market hours. **Pushing code does not refresh the page**; only the schedule and manual runs do.

---

## 2. How we got here

1. **20 Nov 2026.** AVGO fell 12.2% after a Ming-Chi Kuo report that Google cut ~1M units (~20%) of 2027 TPU 8i orders,
   shifting volume to MediaTek's TPU 8t. The user asked for "futures and options" analysis and price predictions at 7,
   10, 20, 30 and 45 days. There are no AVGO futures (single-stock futures ended in 2020), so the work used the
   options-implied forward and the full options-implied distribution instead of a point forecast. A first report was
   published as a private claude.ai page.
2. **20 Nov, same session.** Added the Nvidia cross-complex read (CEO resignation scandal, SEC probe) and revised the
   9 Dec earnings scenario tree to 22/36/28/14.
3. **24 Nov.** Re-ran the projection on the 23 Nov close. Nvidia had reinstated Jensen Huang on 23 Nov (NVDA +31.5%,
   SMH +15%); AVGO rose only 3%, so its drop became Broadcom-specific. Panic volatility collapsed (7-day ATM IV 84% →
   66%) while the earnings premium held (±9.6% → ±10.8%).
4. **24 Nov.** The user wanted the report on their phone without spending Claude tokens on every refresh. Following the
   same pattern as the user's existing swing-report project, the pipeline became this repo: a scheduled GitHub Actions
   build published to GitHub Pages, hardened the same way.
5. **24 Nov.** The user asked for it to run **continuously**, not stop after the 9 Dec earnings report. The pipeline was
   generalized: the next earnings date comes from Yahoo each run, the calibration is recomputed per run, and each edition
   is compared with the previous one through a running history.

---

## 3. How the user likes to work

- **Build and check locally, show the user, then commit/push only after they approve** (carried over from swing-report).
- Wants to view and refresh from mobile, and to keep Claude token use low: daily refreshes run without Claude, and
  Claude is used for occasional edits.
- Security-conscious about anything hosted: keep everything in section 7.
- Prefers probabilities and ranges over point predictions; the page says it is not investment advice.

---

## 4. Repository files

| File | Purpose |
|---|---|
| `run.sh` | Runs the whole pipeline in `work/` and writes `site/index.html` + `site/data.json` |
| `fetch.py` | Options chain, spot, earnings calendar → `chains.pkl`, `run.json` (falls back to repriced last trades off-hours) |
| `cfg.py` | Reads `run.json` for every other script |
| `earn.py` | Earnings helpers: fallback list of past reports, NYSE holidays (2026–2028), next-session reaction math |
| `engine.py` | Forward/discount per expiry (put-call parity), implied vol per strike → `term.csv`, `surface.pkl` |
| `vmodel.py` | Variance term structure (diffusion + earnings jump), bracketing pre/post expiries → `vmodel.pkl` |
| `rnd.py` | SVI fits, Breeden–Litzenberger densities at 7/10/20/30/45 days → `forecast.csv`, `dens.pkl` |
| `hist.py` | Price history since 2019 → `hist.pkl` |
| `phys.py` | Real-world forecast; calibration from past days in a similar vol regime → `phys.csv`, `phys_calib.json` |
| `fix.py` | Positioning: OI, put/call, max pain, far-OTM calls → `positioning.json` |
| `complex.py` | AVGO vs NVDA/AMD/SMH/QQQ, 5 and 20 sessions, correlations → `complex.json` |
| `build_report.py` | Fills `report_template.html`; previous-edition comparison and history; `--pages` adds the CSP |
| `report_template.html` | The page: CSS tokens (light/dark), placeholders, chart JS (inline SVG, no libraries) |
| `notes.json` | Hand-written dated notes (trusted HTML: `<strong>` only) |
| `scenarios.json` | Hand-written scenario tree for one earnings date (`event_date`) |
| `history_seed.json` | First two editions (20 and 23 Nov), used only if the live `data.json` doesn't exist yet |
| `snapshot-2026-11-20/`, `snapshot-2026-11-23/` | Small outputs of the first two runs, kept as a record |
| `requirements.in` / `requirements.txt` | Top-level deps / hash-pinned lock (23 packages, cutoff 2026-11-10) |

Not committed: `work/`, `site/`, `.venv/`, `*.pkl`, `_orig-2026-11-20/` (pre-refactor scripts), local report builds.

---

## 5. How the page decides what to say

- **Event logic.** `vmodel.py` prices the next report as a jump only if it falls inside the listed expirations.
  `build_report.py` then uses `HAS` (an event exists) and `SHOW` (the fitted jump is at least 2%) to pick wording: the
  "Is ±X% enough?" section, the earnings band on the chart, the finding callout and the event card.
- **Scenario tree** appears only while `scenarios.json` `event_date` equals the next earnings date. Otherwise the page
  shows "No scenario tree for the <date> report yet".
- **Comparisons.** `run.sh` downloads the live `data.json`. A 404 means "never published" (use the seed); any other
  failure stops the run, so a network blip can't reset the history. Same-day reruns replace that day's entry.
- **Safety stops** (nothing is published, the previous page stays up): no live quotes on a scheduled run; sanity checks
  fail (fewer than 12 expiries, a near forward >3% from spot, ATM IV outside 10–300%, a median >15% from spot);
  previous `data.json` unreadable.
- **Data from the live site is untrusted:** `clean()` keeps known fields with checked types, and the embedded JSON
  escapes `</`.

---

## 6. Key numbers so far

| Measure | 20 Nov close | 23 Nov close |
|---|---|---|
| AVGO | $303.83 | $313.55 |
| 7-day ATM IV | 84.2% | 66.0% |
| Priced 9 Dec move (1 s.d.) | ±9.56% | ±10.77% (direct read ±10.19%) |
| Long-run IV | 48.8% | 50.5% |
| 45-day central / 50% band | $308 / $261–348 | $318 / $270–361 |
| Scenario-weighted after 9 Dec | $281 | $290 (range $290–310 with the pre-Nvidia weights) |

Last eight earnings reactions: mean absolute move 9.88%, signed standard deviation 12.39%. Against that the 9 Dec options
looked fairly priced to slightly cheap; the non-event premium seen on 20 Nov had largely disappeared by 23 Nov.

---

## 7. Security model (keep all of this)

- **Page:** one self-contained document; CSP `default-src 'none'; script-src 'sha256-<hash>'; style-src 'unsafe-inline';
  img-src data:; base-uri 'none'; form-action 'none'; object-src 'none'`, with the hash computed at build time (never
  hardcode it). No external scripts, fonts, images or requests; the Pages build strips the Google Fonts link used by the
  claude.ai version. No inline event handlers. Tooltips use `textContent` only. `no-referrer`, `noindex`.
- **Supply chain:** hash-pinned `requirements.txt`, installed with `--require-hashes --no-deps`; only package versions at
  least two weeks old. Actions pinned to full commit SHAs (same SHAs as swing-report):
  checkout `3d3c42e…` (v7.0.1), setup-python `6d4fd22…` (v7.1.0), upload-pages-artifact `fc324d3…` (v5.0.0),
  deploy-pages `368f825…` (v5.0.1).
- **Workflow:** `permissions: {}`; build `contents: read`; deploy `pages: write` + `id-token: write`;
  `persist-credentials: false`; triggers `workflow_dispatch` and `schedule` only; no secrets.
- **Repo settings (applied 24 Nov via `gh api`, verified):** only GitHub-owned actions, SHA pinning required, read-only
  default token, PR approval by workflows disabled, fork-PR workflows need approval, vulnerability alerts on, Pages
  `build_type=workflow`, HTTPS enforced.

---

## 8. Maintenance

```bash
PYTHON=.venv/bin/python ./run.sh site/index.html && open site/index.html     # build + preview locally
gh workflow run report.yml -R kkrisc/avgo-report                              # live refresh (market hours)
gh workflow run report.yml -R kkrisc/avgo-report -f allow_last_trades=true    # refresh when the market is closed
gh run list -R kkrisc/avgo-report --workflow report.yml --limit 3
gh run view <run-id> -R kkrisc/avgo-report --log-failed
```
- **Dependency lock:** `uv pip compile requirements.in --universal --python-version 3.14 --generate-hashes --exclude-newer <two weeks ago> -o requirements.txt`, then `uv pip sync --require-hashes --python .venv/bin/python requirements.txt` and a full local run.
- **Action SHAs:** look up a release at least two weeks old and its commit SHA; keep the tag as a comment.
- **Headless checks used before pushing:** CSP hash matches the script, exactly one `<script>`, zero external
  `src/href`, zero `on…=` handlers, `node --check` on the extracted script, six SVGs render, and a phone-width screenshot
  (Chrome won't go below ~500px, so load the page in a 390px `<iframe>` with `--allow-file-access-from-files`).

---

## 9. Next steps

**Multi-ticker follow-ups**
- [ ] After the first multi-ticker deploy: check every page and the overview live, and that `/avgo/` shows 3+ editions.
- [ ] ANT and NGNE: decide whether to add a price-based fallback (ranges from the stock's own realized volatility) for
      stocks whose options are too thin. ANT should start working on its own as Yahoo's option quotes fill in.
- [ ] Write first notes for NVDA, TSM and SPCX, and optional scenario trees for their next reports
      (NVDA 24 Feb, TSM 14 Jan, SPCX 9 Feb).
- [ ] Rename Broadcom's title to match the others ("Broadcom Options Outlook") if the user agrees (`tickers.json`).

**Soon**
- [ ] Confirm the first scheduled live run (24 Nov, 15:47 UTC) published a bid/ask edition ("24 Nov 2026, HH:MM ET" in
      the header) and that the comparison table shows 23 Nov as the previous edition. If it didn't run, trigger it manually.
- [ ] After Thanksgiving (26 Nov closed, 27 Nov early close): check the holiday run skipped publishing cleanly.

**Around the 9 Dec earnings report**
- [ ] 10 Dec: check that Yahoo moved 9 Dec into the past list and the reaction appears in the earnings chart, and that
      the page rolled over to the next report (expected early March 2027).
- [ ] Write a dated note in `notes.json` on the outcome: guidance vs the ~$115B FY27 AI target and which scenario bucket
      it landed in (Bull/Base/Bear/Tail).
- [ ] Once the March 2027 date is confirmed, decide whether to write a new `scenarios.json` for it (judgment work).

**Watch list for notes**
- [ ] Follow-ups on the Google TPU order story (Google or Broadcom comments, further Kuo notes).
- [ ] Nvidia: SEC civil probe, export-control investigations, anything that spills over to Broadcom's disclosures.
- [ ] Anthropic's first earnings date as a public company (expected late Feb to early Mar 2027). Broadcom has a lending
      commitment to and an equity stake in Anthropic.

**Decisions for the user**
- [ ] The page title is still "Pricing the Broadcom Drop", which fits less as time passes. Consider an evergreen name
      (for example "Broadcom Options Outlook"). The title lives in `report_template.html` (`<title>` and `<h1>`).

**Maintenance**
- [ ] Refresh the dependency lock and action SHAs around late January 2027, or on a vulnerability alert.
- [ ] GitHub pauses schedules after 60 days without repo activity; any commit (a new note) resets the clock.
- [ ] Extend the NYSE holiday list in `earn.py` before 2029.

**Ideas not started**
- Positioning history (open interest and max pain over time).
- A second history chart for 30-day IV and the priced earnings move.
- Archive each report's scenario tree next to its outcome.
- A notification when the priced earnings move or the 45-day band changes sharply.

### How to resume in a new session
Open Claude Code in this folder and say:
> Read HANDOFF.md and avgo-report-local.md, then continue from where we left off.
