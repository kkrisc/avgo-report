import yfinance as yf, numpy as np, pandas as pd, datetime as dt
import warnings; warnings.filterwarnings('ignore')
h=yf.download("AVGO",start="2019-01-01",progress=False,auto_adjust=False)
if isinstance(h.columns,pd.MultiIndex): h.columns=h.columns.droplevel(1)
h['ret']=np.log(h['Adj Close']).diff()
h.to_pickle('hist.pkl')
px=h['Adj Close']
print("last close in series:",px.index[-1].date(),round(float(px.iloc[-1]),2))

# ---- realized vol
for n in [5,10,20,30,45,60,120,252]:
    rv=h['ret'].tail(n).std()*np.sqrt(252)*100
    print(f"  RV{n:4d}d = {rv:6.2f}%")
# ex-today
r_ex=h['ret'].iloc[:-1]
print("  RV20d excluding today = %.2f%%"%(r_ex.tail(20).std()*np.sqrt(252)*100))
print("  RV60d excluding today = %.2f%%"%(r_ex.tail(60).std()*np.sqrt(252)*100))

# ---- earnings day reactions (next session after each report)
from cfg import EARN_PAST
from earn import reactions
m=pd.DataFrame(reactions(px,EARN_PAST),columns=['earnings','next_day_%']).iloc[::-1]
print("\n=== EARNINGS-DAY REACTIONS (last %d) ==="%len(m))
print(m.head(12).to_string(index=False))
a=m['next_day_%'].abs()
print("\n  mean |move| = %.2f%%   last 8: %.2f%%   up moves %d / %d"%(a.mean(),a.head(8).mean(),(m['next_day_%']>0).sum(),len(m)))

# ---- technicals
c=px
sma=lambda n: float(c.rolling(n).mean().iloc[-1])
print("\n=== TECHNICALS ===")
print("  spot %.2f | SMA20 %.2f | SMA50 %.2f | SMA100 %.2f | SMA200 %.2f"%(float(c.iloc[-1]),sma(20),sma(50),sma(100),sma(200)))
d=c.diff(); up=d.clip(lower=0).rolling(14).mean(); dn=(-d.clip(upper=0)).rolling(14).mean()
rsi=100-100/(1+up/dn); print("  RSI(14) = %.1f"%float(rsi.iloc[-1]))
print("  52w high %.2f (-%.1f%% from high) | 52w low %.2f (+%.1f%% above low)"%(
  float(c.tail(252).max()),(1-float(c.iloc[-1])/float(c.tail(252).max()))*100,
  float(c.tail(252).min()),(float(c.iloc[-1])/float(c.tail(252).min())-1)*100))
# ATR
tr=pd.concat([h['High']-h['Low'],(h['High']-h['Close'].shift()).abs(),(h['Low']-h['Close'].shift()).abs()],axis=1).max(axis=1)
print("  ATR(14) = %.2f (%.2f%% of spot)"%(float(tr.rolling(14).mean().iloc[-1]),float(tr.rolling(14).mean().iloc[-1])/float(c.iloc[-1])*100))
# drawdown history: how often does a -12% day get followed by recovery
r1=h['ret']
big=r1[r1<-0.10]
print("\n=== HISTORY OF <-10%% SINGLE DAYS (n=%d since 2019) ==="%len(big))
res=[]
for d0 in big.index:
    j=c.index.get_loc(d0)
    for k in [5,10,20,30,45]:
        if j+k<len(c): res.append((k,(float(c.iloc[j+k])/float(c.iloc[j])-1)*100))
rr=pd.DataFrame(res,columns=['h','ret'])
print(rr.groupby('h')['ret'].agg(['count','mean','median','min','max']).round(2).to_string())
