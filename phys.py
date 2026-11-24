import pickle, json, numpy as np, pandas as pd, datetime as dt
import warnings; warnings.filterwarnings('ignore')
from cfg import SPOT, RF, NOW, DIV, LOW52, EARN_PAST, CONF, _c as RUNJ
from earn import reactions
dens=pickle.load(open('dens.pkl','rb')); vm=pickle.load(open('vmodel.pkl','rb'))
v0,vinf,tau,J=vm['p']; T_EARN=vm['T_EARN']
h=pd.read_pickle('hist.pkl'); r=h['ret'].dropna()

# --- volatility calibration, recomputed every run ----------------------------
# Expected diffusive vol = median forward 21-day realized vol on past days whose trailing 20-day
# realized vol sat in a band around today's. Widen the band until there are enough days.
rv20=r.rolling(20).std()*np.sqrt(252); fwd21=r.shift(-21).rolling(21).std()*np.sqrt(252)
cur=float(rv20.iloc[-1]) if len(r)>=20 else float('nan')
lo=hi=float('nan'); sel=pd.Series(dtype=float)
if np.isfinite(cur):
    for k in (1.25,1.4,1.6,2.0,3.0):
        lo,hi=cur/k,cur*k; sel=fwd21[(rv20>=lo)&(rv20<=hi)].dropna()
        if len(sel)>=40: break
CALIBRATED = len(sel)>=40          # too little history (young listings) -> no real-world volatility adjustment
RV_DIFF=float(sel.median()) if CALIBRATED else float('nan')
# Earnings day: signed standard deviation of the last eight next-session reactions.
mv=[m for _,m in reactions(h['Adj Close'],EARN_PAST)][-8:]
EARN_SD=float(np.std(mv,ddof=1))/100 if len(mv)>=4 else 0.10
BETA=CONF.get('beta') or RUNJ.get('beta') or CONF.get('beta_default',1.3)
json.dump(dict(calibrated=CALIBRATED,rv20_now=cur,band_lo=lo,band_hi=hi,n_days=int(len(sel)),fwd_median=RV_DIFF,earn_sd=EARN_SD,
               n_earn=len(mv),n_hist=int(len(r)),beta=float(BETA)),open('phys_calib.json','w'),indent=1)
if CALIBRATED: print("Calibration: trailing RV20 %.1f%% -> %d past days with RV20 in %.0f-%.0f%% -> forward RV21 median %.1f%%; earnings-day sd %.2f%%"%(
      cur*100,len(sel),lo*100,hi*100,RV_DIFF*100,EARN_SD*100))

def phys_vol(days):
    T=days/365.25
    if not CALIBRATED: return None
    v=RV_DIFF**2
    if T>T_EARN: v += (EARN_SD**2)/T      # one earnings day inside the window
    return np.sqrt(v)

print("=== VARIANCE RISK PREMIUM ===")
for name,(Ks,q,cdf,T,F) in dens.items():
    d=round(T*365.25)
    lo_,hi_=float(np.interp(.1587,cdf,Ks)),float(np.interp(.8413,cdf,Ks))
    iv_eff=np.log(hi_/lo_)/2/np.sqrt(T); pv=phys_vol(d) or iv_eff
    print("  %-16s %2dd  implied=%.1f%%  phys_est=%.1f%%  ratio=%.2fx"%(name,d,iv_eff*100,pv*100,iv_eff/pv))

# --- physical distribution: risk-neutral shape kept, width rescaled, equity drift added
ERP=0.045
mu_ann=RF+BETA*ERP
print("\nPhysical drift: r %.2f%% + beta %.2f x ERP %.1f%% = %.2f%%/yr"%(RF*100,BETA,ERP*100,mu_ann*100))

rows=[]
for name,(Ks,q,cdf,T,F) in dens.items():
    d=int(round(T*365.25))
    lo_,hi_=float(np.interp(.1587,cdf,Ks)),float(np.interp(.8413,cdf,Ks))
    iv_eff=np.log(hi_/lo_)/2/np.sqrt(T)
    hc=(phys_vol(d)/iv_eff) if CALIBRATED else 1.0
    med=float(np.interp(.5,cdf,Ks))
    Ks2=SPOT*np.exp(np.log(Ks/med)*hc)*np.exp((mu_ann-DIV)*T)
    Q=lambda p: float(np.interp(p,cdf,Ks2))
    pr=lambda a,b: float(np.interp(b,Ks2,cdf)-np.interp(a,Ks2,cdf))
    rows.append(dict(horizon=name,dte=d,date=(NOW+dt.timedelta(days=d)).strftime('%b %d'),
      vol=round((phys_vol(d) if CALIBRATED else iv_eff)*100,1),haircut=round(hc,2),
      p10=round(Q(.10),1),p25=round(Q(.25),1),median=round(Q(.5),1),p75=round(Q(.75),1),p90=round(Q(.90),1),
      P_up=round(pr(SPOT,1e9)*100,1),P_dn15=round(pr(0,SPOT*0.85)*100,1),P_up15=round(pr(SPOT*1.15,1e9)*100,1)))
p=pd.DataFrame(rows); pd.set_option('display.width',250)
print("\n=== PHYSICAL-MEASURE FORECAST ===")
print(p.to_string(index=False))
p.to_csv('phys.csv',index=False)
