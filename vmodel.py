import pickle, numpy as np, pandas as pd, datetime as dt
from scipy.optimize import least_squares
import warnings; warnings.filterwarnings('ignore')

from cfg import NOW, EARN_OPEN

s=pickle.load(open('surface.pkl','rb'))
T=np.array([v['T'] for v in s.values()]); A=np.array([v['atm'] for v in s.values()])
W=A**2*T                      # observed ATM total variance
o=np.argsort(T); T,A,W=T[o],A[o],W[o]

# The next earnings report is priced as a one-day jump, if it falls inside the listed expirations.
HAS_EVENT = EARN_OPEN is not None and EARN_OPEN > NOW
T_EARN = (EARN_OPEN-NOW).total_seconds()/(365.25*86400) if HAS_EVENT else 1e9
if HAS_EVENT and T_EARN >= T.max(): HAS_EVENT, T_EARN = False, 1e9
print("Earnings resolves %s -> T_e = %.1f days"%(EARN_OPEN, T_EARN*365.25) if HAS_EVENT else "No earnings event inside the listed expirations")

# w(T) = v_inf*T + (v0-v_inf)*tau*(1-exp(-T/tau)) + J^2*1{T>T_e}
def cumvar(p,Tx):
    v0,vinf,tau,J=p
    base=vinf*Tx+(v0-vinf)*tau*(1-np.exp(-Tx/tau))
    return base+ (J**2)*(Tx>T_EARN)

def resid(p):
    if p[2]<=1e-4 or p[0]<=0 or p[1]<=0 or p[3]<0: return np.ones_like(T)*1e3
    mod=cumvar(p,T)
    return (np.sqrt(np.maximum(mod,1e-12)/T)-A)*100*np.sqrt(1/np.sqrt(T))   # fit in vol pts, weight short end

# With few expirations the decay speed isn't identifiable: pin it to ~20 days and fit the rest.
FEW=len(T)<6
lb=[1e-4,1e-4,0.0547 if FEW else 1e-3,0.0]; ub=[6,2,0.0548 if FEW else 5,0.6]
best=None
for g in [[0.8,0.25,0.15,0.08],[1.0,0.2,0.3,0.12],[0.6,0.3,0.08,0.05],[0.9,0.26,0.5,0.10]]:
    g=list(np.clip(g,lb,[u-1e-6 for u in ub])); g[2]=min(max(g[2],lb[2]),ub[2]-1e-6)
    r=least_squares(resid,g,bounds=(lb,ub))
    if best is None or r.cost<best.cost: best=r
v0,vinf,tau,J=best.x
if not HAS_EVENT: J=0.0; best.x[3]=0.0
print("\nFIT: inst vol now=%.1f%%  long-run=%.1f%%  decay tau=%.1f days  EARNINGS JUMP J=%.4f"%(
      np.sqrt(v0)*100,np.sqrt(vinf)*100,tau*365.25,J))
print("  => implied ONE-DAY earnings move (1 s.d.) = +/- %.2f%%"%(J*100)) if HAS_EVENT else None
print("  => implied straddle-equivalent earnings move = +/- %.2f%%"%(J*np.sqrt(2/np.pi)*100))

cmp=pd.DataFrame(dict(dte=np.round(T*365.25).astype(int),obs=np.round(A*100,2),
     model=np.round(np.sqrt(cumvar(best.x,T)/T)*100,2)))
cmp['err']=np.round(cmp.model-cmp.obs,2)
print("\nATM IV fit (%):"); print(cmp.to_string(index=False))
pickle.dump(dict(p=best.x,T_EARN=T_EARN,has_event=HAS_EVENT,cumvar_params=list(best.x)),open('vmodel.pkl','wb'))

# direct earnings-move read from the last expiry before the event and the first one after it
vm_out=pickle.load(open('vmodel.pkl','rb')); vm_out.update(J_direct=float('nan'),pre_exp=None,post_exp=None)
if HAS_EVENT:
    exps=sorted(s.items(),key=lambda kv:kv[1]['T'])
    pre=[e for e,v in exps if v['T']<T_EARN]; post=[e for e,v in exps if v['T']>T_EARN]
    if pre and post:
        a_,b_=s[pre[-1]],s[post[0]]
        wa,wb=a_['atm']**2*a_['T'],b_['atm']**2*b_['T']
        diff=cumvar([v0,vinf,tau,0],np.array([b_['T']]))[0]-cumvar([v0,vinf,tau,0],np.array([a_['T']]))[0]
        vm_out.update(J_direct=float(np.sqrt(max(wb-wa-diff,0))),pre_exp=pre[-1],post_exp=post[0])
        print("\nDirect %s->%s check: total var gap=%.5f, diffusive=%.5f, jump=%.2f%%"%(pre[-1],post[0],wb-wa,diff,vm_out['J_direct']*100))
pickle.dump(vm_out,open('vmodel.pkl','wb'))
