# Cross-complex read: the ticker vs its peers over rolling windows. Writes complex.json into the cwd.
import json, numpy as np, pandas as pd, yfinance as yf
import warnings; warnings.filterwarnings('ignore')
from cfg import SYM, CONF

TK = [SYM] + CONF.get('peers', ['SMH', 'QQQ'])
start = max(pd.Timestamp(CONF.get('hist_start', '2019-01-01')), pd.Timestamp.now() - pd.Timedelta(days=370))
px = yf.download(TK, start=start.strftime('%Y-%m-%d'), progress=False, auto_adjust=True)['Close'][TK].dropna(how='any')
r = px.pct_change()
n = len(px)
chg = lambda k: ((px.iloc[-1] / px.iloc[-1 - min(k, n - 1)] - 1) * 100).round(2).to_dict()
corr = lambda k: r.tail(k).corr()[SYM].drop(SYM).round(2).to_dict() if n > k else None
daily = {d.strftime('%Y-%m-%d'): (r.loc[d] * 100).round(2).to_dict() for d in px.index[max(1, n - 5):]}
out = dict(sym=SYM, tickers=TK, last=px.index[-1].strftime('%Y-%m-%d'), sessions=n,
           n5=min(5, n - 1), n20=min(20, n - 1), chg5=chg(5), chg20=chg(20), daily=daily, corr20=corr(20), corr60=corr(60))
json.dump(out, open('complex.json', 'w'), indent=1)
print(json.dumps({k: out[k] for k in ('last', 'sessions', 'chg5', 'chg20', 'corr20')}, indent=1))
