# Pull a fresh AVGO options chain + spot and write chains.pkl / run.json into the cwd.
#
# During market hours Yahoo returns live bid/ask and we use mids (price_mode='mid').
# Outside market hours Yahoo zeroes bid/ask/OI, so we fall back to each contract's
# last trade from the most recent session, repriced to the closing spot under a
# sticky-strike assumption (solve IV at the spot prevailing when it traded, reprice
# at the close). The adjusted price is written into bid and ask so engine.py runs
# unchanged.
import sys, os, json, pickle, time, datetime as dt
import numpy as np, pandas as pd, yfinance as yf
from scipy.stats import norm
from scipy.optimize import brentq
import warnings; warnings.filterwarnings('ignore')

SYM = os.environ.get("SYM", "AVGO")
RF = 0.04122
tk = yf.Ticker(SYM)

d = tk.history(period="10d", auto_adjust=False)
d.index = d.index.tz_convert('America/New_York')
last_day = d.index[-1]
spot, prev = float(d['Close'].iloc[-1]), float(d['Close'].iloc[-2])
info = tk.info
dy = info.get('dividendYield') or 0.0
DIV = dy / 100 if dy > 0.2 else dy          # Yahoo reports this in percent in current versions
now = last_day.replace(hour=16, minute=0, second=0, microsecond=0).tz_localize(None)

chains = {}
for e in tk.options:
    for _ in range(3):
        try:
            c = tk.option_chain(e); chains[e] = (c.calls.copy(), c.puts.copy()); break
        except Exception:
            time.sleep(2)

# Live quotes? Judge on near-the-money contracts, since thin chains have many far strikes with no bid even when open.
nm = lambda df: df[(df.strike > spot * 0.7) & (df.strike < spot * 1.3)]
live = sum(int((nm(C).bid > 0).sum() + (nm(P).bid > 0).sum()) for C, P in chains.values())
total = sum(len(nm(C)) + len(nm(P)) for C, P in chains.values())
mode = 'mid' if live > 0.5 * total else 'last'
if mode == 'mid':   # live quotes: time-stamp at the actual pull time, not the 16:00 close
    now = pd.Timestamp.now(tz='America/New_York').floor('min').tz_localize(None).to_pydatetime()
print(f"spot {spot:.2f} (prev {prev:.2f}) as of {now}  | contracts {total}, with live bid {live} -> mode={mode}")

if mode == 'last':
    ib = tk.history(start=last_day.strftime('%Y-%m-%d'), interval="5m")
    ib.index = ib.index.tz_convert('America/New_York')
    ib = ib.loc[ib.index.date == last_day.date(), 'Close']
    sess_open = pd.Timestamp(last_day.date()).tz_localize('America/New_York') + pd.Timedelta(hours=9, minutes=30)

    def bs(S, K, T, s, call):
        F = S * np.exp((RF - DIV) * T); D = np.exp(-RF * T); v = s * np.sqrt(T)
        d1 = (np.log(F / K) + 0.5 * v * v) / v; d2 = d1 - v
        return D * (F * norm.cdf(d1) - K * norm.cdf(d2)) if call else D * (K * norm.cdf(-d2) - F * norm.cdf(-d1))

    kept = 0
    for e, (C, P) in chains.items():
        T = (dt.datetime.strptime(e, '%Y-%m-%d').replace(hour=16) - now).total_seconds() / (365.25 * 86400)
        for df, call in ((C, True), (P, False)):
            adj = np.full(len(df), np.nan)
            ltd = pd.to_datetime(df['lastTradeDate']).dt.tz_convert('America/New_York')
            for i, (K, px, t) in enumerate(zip(df['strike'], df['lastPrice'], ltd)):
                if T <= 0 or not (px > 0) or t < sess_open:
                    continue                      # stale: did not trade in the last session
                S_t = float(ib.asof(t.floor('5min'))) if len(ib) else spot
                if not np.isfinite(S_t): S_t = spot
                try:
                    f = lambda s: bs(S_t, K, T, s, call) - px
                    if f(1e-4) * f(6.0) > 0: continue
                    iv = brentq(f, 1e-4, 6.0, xtol=1e-8)
                except Exception:
                    continue
                adj[i] = bs(spot, K, T, iv, call)
            df['bid'] = adj; df['ask'] = adj
            kept += int(np.isfinite(adj).sum())
    print(f"last-trade fallback: kept {kept} contracts that traded on {last_day.date()}, repriced to close {spot:.2f}")

pickle.dump(chains, open('chains.pkl', 'wb'))

# ---- earnings calendar: past reports (for reaction history) and the next one (for the jump) ----
from earn import BASE_PAST, reaction_open
NOWX = pd.Timestamp(now).to_pydatetime()
cal = {d: 'amc' for d in BASE_PAST.get(SYM, [])}
upcoming = []
try:
    ed = tk.get_earnings_dates(limit=40)
    for ts in ed.index:
        ts = ts.tz_convert('America/New_York')
        timing = 'bmo' if ts.hour * 60 + ts.minute < 9 * 60 + 30 else 'amc'
        cal[ts.date().isoformat()] = timing
except Exception as ex:
    print("earnings calendar from Yahoo unavailable:", ex)
for key in ('earningsTimestamp', 'earningsTimestampStart'):
    v = info.get(key)
    if isinstance(v, (int, float)) and v > 1e9:
        ts = pd.Timestamp(v, unit='s', tz='UTC').tz_convert('America/New_York')
        cal.setdefault(ts.date().isoformat(), 'bmo' if ts.hour * 60 + ts.minute < 570 else 'amc')
past = []
for iso, timing in sorted(cal.items()):
    ro = reaction_open(dt.date.fromisoformat(iso), timing)
    (past if ro <= NOWX else upcoming).append([iso, timing, ro])
nxt = upcoming[0] if upcoming and (upcoming[0][2] - NOWX).days <= 120 else None
print("next earnings:", (nxt[0] + ' ' + nxt[1]) if nxt else 'none within 120 days', "| past reports:", len(past))

# ---- analyst expectations (consensus revenue/EPS, price targets) ----
est = {}
try:
    for key, attr in (('rev', 'revenue_estimate'), ('eps', 'earnings_estimate')):
        df = getattr(tk, attr)
        if df is not None and len(df):
            est[key] = {str(i): {k: (float(df.loc[i, k]) if k in df.columns and pd.notna(df.loc[i, k]) else None)
                                 for k in ('avg', 'low', 'high', 'numberOfAnalysts', 'yearAgoRevenue', 'yearAgoEps', 'growth')}
                        for i in df.index}
    pt = tk.analyst_price_targets
    if isinstance(pt, dict): est['pt'] = {k: float(v) for k, v in pt.items() if isinstance(v, (int, float))}
except Exception as ex:
    print("analyst estimates unavailable:", ex)

run = dict(sym=SYM, spot=round(spot, 2), prev=round(prev, 2), now=now.isoformat(), rf=RF, div=round(DIV, 5), est=est,
           beta=info.get('beta'), name=info.get('longName') or info.get('shortName'),
           earn_next=nxt[0] if nxt else None, earn_timing=nxt[1] if nxt else None,
           earn_open=nxt[2].isoformat(timespec='minutes') if nxt else None,
           earn_past=[[d, t] for d, t, _ in past],
           low52=info.get('fiftyTwoWeekLow'), high52=info.get('fiftyTwoWeekHigh'),
           price_mode=mode, market_cap=info.get('marketCap'))
json.dump(run, open('run.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in run.items() if k != 'earn_past'}, indent=1))
