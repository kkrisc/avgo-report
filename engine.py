import pickle, numpy as np, pandas as pd, datetime as dt
from scipy.stats import norm
from scipy.optimize import brentq, least_squares
import json, sys, warnings
warnings.filterwarnings('ignore')

from cfg import SPOT, NOW, RF, DIV, PRICE_MODE

chains = pickle.load(open('chains.pkl','rb'))

def bs_fwd(F,K,T,sig,D,call=True):
    if sig<=0 or T<=0: 
        return D*max(F-K,0) if call else D*max(K-F,0)
    v=sig*np.sqrt(T); d1=(np.log(F/K)+0.5*v*v)/v; d2=d1-v
    return D*(F*norm.cdf(d1)-K*norm.cdf(d2)) if call else D*(K*norm.cdf(-d2)-F*norm.cdf(-d1))

def iv_fwd(px,F,K,T,D,call=True):
    lo,hi=1e-4,6.0
    try:
        f=lambda s: bs_fwd(F,K,T,s,D,call)-px
        if f(lo)*f(hi)>0: return np.nan
        return brentq(f,lo,hi,xtol=1e-8,maxiter=200)
    except Exception: return np.nan

def mid(df):
    b,a=df['bid'].values,df['ask'].values
    m=np.where((b>0)&(a>0)&(a>=b),(b+a)/2,np.nan)
    return m

rows=[]
surface={}
# Thin chains (few listed expirations): accept wider quotes and fewer strikes per expiry, and say so on the page.
THIN=len(chains)<8
MAX_SPREAD=3.0 if THIN else 1.5; MIN_PTS=4 if THIN else 6
for exp,(C,P) in chains.items():
    ed=dt.datetime.strptime(exp,'%Y-%m-%d').replace(hour=16)
    T=(ed-NOW).total_seconds()/(365.25*86400)
    if T<=1/365.25/24: continue
    c=C.copy(); p=P.copy()
    c['mid']=mid(c); p['mid']=mid(p)
    c=c[['strike','mid','bid','ask','volume','openInterest']].dropna(subset=['mid'])
    p=p[['strike','mid','bid','ask','volume','openInterest']].dropna(subset=['mid'])
    m=c.merge(p,on='strike',suffixes=('_c','_p'))
    m=m[(m['mid_c']>0.02)&(m['mid_p']>0.02)]
    # put-call parity: C-P = D*F - D*K  (use near-ATM band)
    band=m[(m.strike>SPOT*0.80)&(m.strike<SPOT*1.20)]
    if len(band)<4: band=m
    if len(band)<3: continue
    y=(band['mid_c']-band['mid_p']).values; K=band['strike'].values
    w=np.minimum(band['openInterest_c'].fillna(0)+band['openInterest_p'].fillna(0),5000)+10
    A=np.vstack([np.ones_like(K),K]).T
    W=np.diag(w)
    coef=np.linalg.lstsq(W@A,W@y,rcond=None)[0]
    b0,b1=coef; D=-b1; 
    if not (0.90<D<=1.0005): D=np.exp(-RF*T)
    F=b0/D
    if not (SPOT*0.85<F<SPOT*1.15): F=SPOT*np.exp(RF*T)
    if PRICE_MODE=="last":   # unsynchronised last trades make the parity regression noisy; forward is pure carry anyway
        D=np.exp(-RF*T); F=SPOT*np.exp((RF-DIV)*T)
    # IVs: use OTM side (calls above F, puts below F)
    ks,ivs,wts=[],[],[]
    for _,r in m.iterrows():
        Kx=r['strike']
        if Kx>=F:
            px,isc=r['mid_c'],True; oi=r['openInterest_c']; sp=r['ask_c']-r['bid_c']
        else:
            px,isc=r['mid_p'],False; oi=r['openInterest_p']; sp=r['ask_p']-r['bid_p']
        if px<=0.03: continue
        if sp>0 and sp/px>MAX_SPREAD: continue
        s=iv_fwd(px,F,Kx,T,D,isc)
        if not np.isfinite(s) or s<0.05 or s>3.5: continue
        k=np.log(Kx/F)
        if abs(k)>0.85: continue
        vg=D*F*norm.pdf((k+0.5*s*s*T)/(s*np.sqrt(T)))*np.sqrt(T)
        ks.append(k); ivs.append(s); wts.append(max(vg,1e-6)*(1+np.log1p(np.nan_to_num(oi))))
    if len(ks)<MIN_PTS: continue
    ks=np.array(ks); ivs=np.array(ivs); wts=np.array(wts)
    o=np.argsort(ks); ks,ivs,wts=ks[o],ivs[o],wts[o]
    # ATM iv = interp at k=0
    atm=float(np.interp(0.0,ks,ivs))
    surface[exp]=dict(T=T,F=F,D=D,k=ks,iv=ivs,w=wts,atm=atm)
    dte=(ed.date()-NOW.date()).days
    rows.append(dict(exp=exp,dte=dte,T=T,F=round(F,2),D=round(D,5),atm_iv=round(atm*100,2),
                     n=len(ks),oi_c=int(C['openInterest'].fillna(0).sum()),oi_p=int(P['openInterest'].fillna(0).sum()),
                     vol_c=int(C['volume'].fillna(0).sum()),vol_p=int(P['volume'].fillna(0).sum())))

if len(rows)<3:
    sys.exit(f"STOP: only {len(rows)} of {len(chains)} expirations have enough quoted strikes to price. Options data is too sparse for this report yet.")
tt=pd.DataFrame(rows).sort_values('dte')
print("=== TERM STRUCTURE (spot %.2f, r=%.3f%%) ==="%(SPOT,RF*100))
print(tt.to_string(index=False))
pickle.dump(surface,open('surface.pkl','wb'))
tt.to_csv('term.csv',index=False)
