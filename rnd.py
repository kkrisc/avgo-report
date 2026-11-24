import pickle, numpy as np, pandas as pd, datetime as dt
from scipy.stats import norm
from scipy.optimize import least_squares, brentq
import warnings; warnings.filterwarnings('ignore')

from cfg import NOW, SPOT, RF, DIV, LOW52
s=pickle.load(open('surface.pkl','rb')); vm=pickle.load(open('vmodel.pkl','rb'))
v0,vinf,tau,J=vm['p']; T_EARN=vm['T_EARN']

def cumvar(Tx,withjump=True):
    base=vinf*Tx+(v0-vinf)*tau*(1-np.exp(-Tx/tau))
    return base+(J**2)*(np.asarray(Tx)>T_EARN if withjump else 0)

# ---------- SVI fit per expiry ----------
def svi(p,k):
    a,b,rho,m,sg=p
    return a+b*(rho*(k-m)+np.sqrt((k-m)**2+sg**2))

fits={}
for e,v in s.items():
    k,iv,w=v['k'],v['iv'],v['w']; T=v['T']; wobs=iv**2*T
    def r(p):
        a,b,rho,m,sg=p
        if b<0 or abs(rho)>=0.999 or sg<=1e-4 or a+b*sg*np.sqrt(1-rho**2)<0: return np.ones_like(k)*1e3
        return (svi(p,k)-wobs)*np.sqrt(w)*1e3
    best=None
    for g in [[wobs.mean()*0.5,0.3*T,-0.6,0.0,0.15],[wobs.mean()*0.3,0.6*T,-0.4,-0.05,0.3],[wobs.mean()*0.7,0.15*T,-0.8,0.05,0.08]]:
        try:
            rr=least_squares(r,g,max_nfev=6000)
            if best is None or rr.cost<best.cost: best=rr
        except Exception: pass
    rmse=np.sqrt(np.mean((np.sqrt(np.maximum(svi(best.x,k),1e-9)/T)-iv)**2))*100
    fits[e]=dict(p=best.x,T=T,F=v['F'],D=v['D'],kmin=k.min(),kmax=k.max(),rmse=rmse,atm=v['atm'])

print("=== SVI FITS (RMSE in vol pts) ===")
for e,f in sorted(fits.items(),key=lambda x:x[1]['T'])[:12]:
    print("  %s  dte=%3d  rmse=%.2f  k=[%.2f,%.2f]"%(e,round(f['T']*365.25),f['rmse'],f['kmin'],f['kmax']))

# ---------- smile at arbitrary horizon: interpolate total var in cumvar-time ----------
EXPS=sorted(fits.items(),key=lambda x:x[1]['T'])
def smile_at(Tstar,kgrid):
    tau_s=cumvar(Tstar)
    lo=hi=None
    for e,f in EXPS:
        if f['T']<=Tstar: lo=(e,f)
    for e,f in EXPS:
        if f['T']>=Tstar: hi=(e,f); break
    def wof(f,kg):
        kk=np.clip(kg,f['kmin'],f['kmax'])
        wv=svi(f['p'],kk)
        # linear extrapolation in |k| outside fitted range
        sl_l=(svi(f['p'],f['kmin']+1e-3)-svi(f['p'],f['kmin']))/1e-3
        sl_h=(svi(f['p'],f['kmax'])-svi(f['p'],f['kmax']-1e-3))/1e-3
        wv=np.where(kg<f['kmin'],svi(f['p'],f['kmin'])+sl_l*(kg-f['kmin']),wv)
        wv=np.where(kg>f['kmax'],svi(f['p'],f['kmax'])+sl_h*(kg-f['kmax']),wv)
        return np.maximum(wv,1e-8)
    if lo is None: lo=hi
    if hi is None: hi=lo
    if lo[0]==hi[0]:
        w=wof(lo[1],kgrid)*(tau_s/cumvar(lo[1]['T']))
        F=lo[1]['F']*np.exp((RF-DIV)*(Tstar-lo[1]['T']))
    else:
        t1,t2=cumvar(lo[1]['T']),cumvar(hi[1]['T'])
        a=0.0 if t2<=t1 else (tau_s-t1)/(t2-t1); a=np.clip(a,0,1)
        w=(1-a)*wof(lo[1],kgrid)+a*wof(hi[1],kgrid)
        F=(1-a)*lo[1]['F']*np.exp((RF-DIV)*(Tstar-lo[1]['T']))+a*hi[1]['F']*np.exp((RF-DIV)*(Tstar-hi[1]['T']))
    return w,F

def rnd(Tstar):
    D=np.exp(-RF*Tstar)
    Ks=np.linspace(SPOT*0.25,SPOT*3.2,4000)
    _,F=smile_at(Tstar,np.array([0.0]))
    kg=np.log(Ks/F); w,F2=smile_at(Tstar,kg)
    sig=np.sqrt(w/Tstar)
    v=sig*np.sqrt(Tstar); d1=(np.log(F/Ks)+0.5*v*v)/v; d2=d1-v
    C=D*(F*norm.cdf(d1)-Ks*norm.cdf(d2))
    q=np.gradient(np.gradient(C,Ks),Ks)/D
    q=np.maximum(q,0)
    q/= np.trapezoid(q,Ks)
    cdf=np.concatenate([[0],np.cumsum((q[1:]+q[:-1])/2*np.diff(Ks))]); cdf/=cdf[-1]
    return Ks,q,cdf,F,sig,np.interp(0,kg,sig)

HOR=[("Next week (7d)",7),("10 days",10),("20 days",20),("30 days",30),("45 days",45)]
out=[]
dens={}
for name,d in HOR:
    Tstar=d/365.25
    Ks,q,cdf,F,sig,atm=rnd(Tstar)
    Q=lambda p: float(np.interp(p,cdf,Ks))
    pr=lambda lo,hi: float(np.interp(hi,Ks,cdf)-np.interp(lo,Ks,cdf))
    med=Q(0.5); mean=float(np.trapezoid(Ks*q,Ks))
    mode=float(Ks[np.argmax(q)])
    row=dict(horizon=name,dte=d,date=(NOW+dt.timedelta(days=d)).strftime('%Y-%m-%d'),
        fwd=round(F,2),atm_iv=round(atm*100,1),
        p05=round(Q(.05),1),p10=round(Q(.10),1),p25=round(Q(.25),1),median=round(med,1),
        p75=round(Q(.75),1),p90=round(Q(.90),1),p95=round(Q(.95),1),
        mean=round(mean,1),mode=round(mode,1),
        exp_move_pct=round((Q(.8413)-Q(.1587))/2/SPOT*100,2),
        P_up=round(pr(SPOT,1e9)*100,1), P_dn15=round(pr(0,SPOT*0.85)*100,1), P_up15=round(pr(SPOT*1.15,1e9)*100,1),
        P_dn30=round(pr(0,SPOT*0.70)*100,1), P_up30=round(pr(SPOT*1.30,1e9)*100,1))
    out.append(row); dens[name]=(Ks,q,cdf,Tstar,F)

df=pd.DataFrame(out)
pd.set_option('display.width',250)
print("\n=== RISK-NEUTRAL QUANTILES (spot %.2f) ==="%SPOT)
print(df[['horizon','date','dte','fwd','atm_iv','p05','p10','p25','median','p75','p90','p95','mean','mode','exp_move_pct']].to_string(index=False))
print("\n=== PROBABILITIES (%) ===")
print(df[['horizon','P_up','P_dn15','P_up15','P_dn30','P_up30']].to_string(index=False))
pickle.dump(dens,open('dens.pkl','wb')); df.to_csv('forecast.csv',index=False)
