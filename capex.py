# AI spending tracker: quarterly capital expenditure and operating cash flow of the largest AI buyers.
#   python capex.py <out.json>
# Quarters are mapped to calendar quarters by period-end month (Oracle's fiscal quarters end Feb/May/Aug/Nov).
import sys, json, datetime as dt
import pandas as pd, yfinance as yf
import warnings; warnings.filterwarnings('ignore')

BUYERS = [("MSFT", "Microsoft"), ("GOOGL", "Alphabet"), ("AMZN", "Amazon"), ("META", "Meta"), ("ORCL", "Oracle")]


def cal_q(ts):
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year}-Q{q}"


out = {"asof": dt.date.today().isoformat(), "companies": []}
for sym, name in BUYERS:
    try:
        cf = yf.Ticker(sym).quarterly_cashflow
        capex = cf.loc['Capital Expenditure'] if 'Capital Expenditure' in cf.index else None
        ocf = cf.loc['Operating Cash Flow'] if 'Operating Cash Flow' in cf.index else None
        rows = {}
        for col in cf.columns:
            c = capex.get(col) if capex is not None else None
            if c is None or pd.isna(c):
                continue
            o = ocf.get(col) if ocf is not None else None
            rows[cal_q(col)] = {"end": col.strftime('%Y-%m-%d'), "capex": round(-float(c) / 1e9, 2),
                                "ocf": None if o is None or pd.isna(o) else round(float(o) / 1e9, 2)}
        out["companies"].append({"sym": sym, "name": name, "q": dict(sorted(rows.items()))})
        print(sym, list(rows.items())[:2])
    except Exception as ex:
        print(sym, "unavailable:", ex)
        out["companies"].append({"sym": sym, "name": name, "q": {}})
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else 'capex.json', 'w'), indent=1)
