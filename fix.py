import pandas as pd, numpy as np, pickle, json
import warnings; warnings.filterwarnings('ignore')
from cfg import SPOT, EARN_PAST
from earn import reactions
h=pd.read_pickle('hist.pkl'); px=h['Adj Close']

# ---------- earnings reactions ----------
m=pd.DataFrame(reactions(px,EARN_PAST),columns=['earnings','mv']).iloc[::-1]   # newest first
a=m.mv.abs()
print("MOST RECENT 8 earnings reactions:", [f"{x:+.1f}%" for x in m.mv.head(8)])
print("  last  8 : mean|mv| = %.2f%%  median = %.2f%%  signed sd = %.2f%%"%(a.head(8).mean(),a.head(8).median(),m.mv.head(8).std()))
print("  all %d  : mean|mv| = %.2f%%"%(len(m),a.mean()))

# Wilder RSI
d=px.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
ag=g.ewm(alpha=1/14,adjust=False).mean(); al=l.ewm(alpha=1/14,adjust=False).mean()
print("\nWilder RSI(14) = %.1f"%float((100-100/(1+ag/al)).iloc[-1]))
print("last 10 closes:", [round(float(x),1) for x in px.tail(10)])

# ---------- POSITIONING ----------
# Show the four expirations with the most open interest among the nearest ten, in date order.
ch=pickle.load(open('chains.pkl','rb'))
print("\n=== POSITIONING ===")
near=sorted(ch.keys())[:10]
oi=lambda e: float(ch[e][0].openInterest.fillna(0).sum()+ch[e][1].openInterest.fillna(0).sum())
pick=sorted(sorted(near,key=lambda e:-oi(e))[:4]) if sum(oi(e) for e in near)>0 else near[:4]
pos=[]
for e in pick:
    C,P=ch[e]
    oc,op=C.openInterest.fillna(0),P.openInterest.fillna(0)
    Ks=sorted(set(C.strike)|set(P.strike)); cm=dict(zip(C.strike,oc)); pm=dict(zip(P.strike,op))
    pain=[(S,sum(cm[k]*max(S-k,0) for k in cm)+sum(pm[k]*max(k-S,0) for k in pm)) for S in Ks]
    mp=min(pain,key=lambda x:x[1])[0]
    t=C.assign(oi=oc).nlargest(4,'oi'); tp=P.assign(oi=op).nlargest(4,'oi')
    pos.append(dict(exp=e, oi_c=int(oc.sum()), oi_p=int(op.sum()),
        pc_oi=round(float(op.sum()/max(oc.sum(),1)),2),
        pc_vol=round(float(P.volume.fillna(0).sum()/max(C.volume.fillna(0).sum(),1)),2),
        max_pain=float(mp) if oc.sum()+op.sum()>0 else None,
        top_calls=[[float(r.strike),int(r.oi)] for r in t.itertuples()],
        top_puts=[[float(r.strike),int(r.oi)] for r in tp.itertuples()]))
    print("-- %s  OI %d  P/C(OI)=%.2f  max pain %s"%(e,oc.sum()+op.sum(),pos[-1]['pc_oi'],pos[-1]['max_pain']))
# Far out-of-the-money call open interest (strikes at least 50% above spot) within about a year.
far=[]
for e in sorted(ch.keys()):
    if (pd.Timestamp(e)-pd.Timestamp.now()).days>400: break
    C=ch[e][0]; f=C[C.strike>=1.5*SPOT]
    far+= [[e,float(k),int(v)] for k,v in zip(f.strike,f.openInterest.fillna(0)) if v>0]
far=sorted(far,key=lambda x:-x[2])[:2]
json.dump(dict(positions=pos, far_calls=far), open('positioning.json','w'), indent=1)
