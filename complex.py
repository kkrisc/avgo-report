# Cross-complex read: AVGO vs NVDA / AMD / SMH / QQQ over rolling windows. Writes complex.json into the cwd.
import json, numpy as np, pandas as pd, yfinance as yf
import warnings; warnings.filterwarnings('ignore')

TK = ["AVGO", "NVDA", "AMD", "SMH", "QQQ"]
px = yf.download(TK, period="1y", progress=False, auto_adjust=True)['Close'].dropna(how='any')
r = px.pct_change()
chg = lambda n: ((px.iloc[-1] / px.iloc[-1 - n] - 1) * 100).round(2).to_dict()
daily = {d.strftime('%Y-%m-%d'): (r.loc[d] * 100).round(2).to_dict() for d in px.index[-5:]}
out = dict(last=px.index[-1].strftime('%Y-%m-%d'), chg5=chg(5), chg20=chg(20), daily=daily,
           corr20=r.tail(20).corr()['AVGO'].drop('AVGO').round(2).to_dict(),
           corr60=r.tail(60).corr()['AVGO'].drop('AVGO').round(2).to_dict())
json.dump(out, open('complex.json', 'w'), indent=1)
print(json.dumps({k: out[k] for k in ('last', 'chg5', 'chg20', 'corr20')}, indent=1))
