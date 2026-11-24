# Fill report_template.html from one pipeline run.
#   python build_report.py <run_dir> <out.html> [--pages] [--prev prev_data.json] [--capex capex.json]
# <run_dir> holds the outputs of fetch → engine → vmodel → rnd → hist → phys → fix → complex.
# --pages  writes a complete, self-contained document for GitHub Pages (strict Content-Security-Policy allowing
#          only this page's own script by hash, no external loads, no-referrer, noindex) plus data.json beside it.
# --prev   the previous edition's data.json (comparison + running history). Falls back to history_seed.json.
# Exit codes: 4 = data failed sanity checks, 5 = previous data.json unreadable. Either way nothing is written.
import sys, os, json, pickle, re, base64, hashlib, html, datetime as dt
import numpy as np, pandas as pd

argv = sys.argv[1:]
PAGES = '--pages' in argv
PREV_PATH = argv[argv.index('--prev') + 1] if '--prev' in argv else None
CAPEX_PATH = argv[argv.index('--capex') + 1] if '--capex' in argv else None
pos_args = [a for i, a in enumerate(argv) if not a.startswith('--') and not (i > 0 and argv[i - 1] in ('--prev', '--capex'))]
RUN, OUT = pos_args[0], pos_args[1]
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from earn import reactions

P = lambda f: os.path.join(RUN, f)
J_ = lambda f: json.load(open(os.path.join(HERE, f)))
esc = html.escape
tpl = open(os.path.join(HERE, 'report_template.html')).read()

run = json.load(open(P('run.json'))); cx = json.load(open(P('complex.json')))
pos = json.load(open(P('positioning.json'))); calib = json.load(open(P('phys_calib.json')))
term = pd.read_csv(P('term.csv')); rn = pd.read_csv(P('forecast.csv')); ph = pd.read_csv(P('phys.csv'))
vm = pickle.load(open(P('vmodel.pkl'), 'rb')); h = pd.read_pickle(P('hist.pkl'))
chains = pickle.load(open(P('chains.pkl'), 'rb'))
SYM = run.get('sym', 'AVGO')
TICKERS = J_('tickers.json'); TICK = next(t for t in TICKERS if t['sym'] == SYM); NAME = TICK['name']
opt = lambda f, d: J_(f) if os.path.exists(os.path.join(HERE, f)) else d
scen = opt(f'scenarios/{SYM}.json', {}); notes = opt(f'notes/{SYM}.json', []); seed = opt(f'seeds/{SYM}.json', None)
capex = json.load(open(CAPEX_PATH)) if (TICK.get('capex') and CAPEX_PATH and os.path.exists(CAPEX_PATH)) else None

NOW = dt.datetime.fromisoformat(run['now']); MODE = run.get('price_mode', 'mid')
SPOT, PREV = float(run['spot']), float(run['prev'])
v0, vinf, tau, J = vm['p']; HAS = bool(vm.get('has_event')); T_EARN = vm['T_EARN']
if not HAS: J = 0.0
SHOW = HAS and J * 100 >= 2.0          # a priced event worth talking about (a near-zero fit gets neutral wording)
Jd = vm.get('J_direct', float('nan')); PRE, POST = vm.get('pre_exp'), vm.get('post_exp')

S = lambda x, d=1: (f"{x:.{d}f}").replace('-', '−')
sgn = lambda x, d=1: ('+' if x > 0 else '') + S(x, d)
dd = lambda d: d.strftime('%-d %b')
iso = lambda s: dt.date.fromisoformat(s)
WORDS = "None One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve".split()

# ---------------- sanity checks ----------------
problems = []
THIN = len(term) < 12                      # few listed expirations: looser checks, reduced claims
if len(term) < 3: problems.append(f"only {len(term)} expirations fitted")
near = term[term['T'] < 0.25]
if ((near.F / SPOT - 1).abs() > (0.06 if THIN else 0.03)).any(): problems.append("a near-term forward is too far from spot")
if not term.atm_iv.between(10, 300).all(): problems.append("an ATM implied vol is outside 10-300%")
if not ((rn['median'] / SPOT - 1).abs() < 0.15).all(): problems.append("a forecast median is more than 15% from spot")
if problems: sys.exit("STOP (exit 4): data failed sanity checks: " + "; ".join(problems))

# ---------------- labels ----------------
if MODE == 'mid':
    asof = NOW.strftime('%-d %b %Y, %H:%M ET'); asof_short = NOW.strftime('%-d %b %H:%M ET'); asof_col = NOW.strftime('%-d %b %H:%M')
    chg_txt = f"{sgn((SPOT/PREV-1)*100,2)}% today · prev close {PREV:.2f}"
else:
    asof = NOW.strftime('%-d %b %Y') + ' close'; asof_short = NOW.strftime('%-d %b') + ' close'; asof_col = NOW.strftime('%-d %b')
    chg_txt = f"{sgn((SPOT/PREV-1)*100,2)}% on the day · prev {PREV:.2f}"
today = NOW.date().isoformat()

# ---------------- earnings ----------------
EN = iso(run['earn_next']) if run.get('earn_next') else None
when = "after the close" if (run.get('earn_timing') or 'amc') == 'amc' else "before the open"
earn_d = T_EARN * 365.25 if HAS else None
earn_short = dd(EN) if EN else None
earn_long = EN.strftime('%A %-d %B %Y') if EN else None
earn_label = (EN.strftime('%-d %b').upper() + " EARNINGS") if EN else "EARNINGS"
px = h['Adj Close'].dropna()
rx = reactions(px, run.get('earn_past', []))
earn12 = [{"q": d.strftime("%b '%y"), "mv": round(m, 1)} for d, m in rx[-12:]]
mvs = np.array([m for _, m in rx]); r8 = mvs[-8:]
NE = len(mvs)
r8_mean = np.abs(r8).mean() if NE else float('nan'); r8_sd = r8.std(ddof=1) if NE >= 2 else float('nan')
all_mean = np.abs(mvs).mean() if NE else float('nan')
hist_since = px.index[0].strftime('%-d %b %Y') if px.index[0].year >= 2024 else str(px.index[0].year)
n_big = int(sum(abs(e['mv']) > 9 for e in earn12))
hist90 = [{"d": d.strftime('%-d %b'), "p": round(float(v), 2)} for d, v in px.tail(90).items()]

# ---------------- term structure ----------------
term['d'] = term['T'] * 365.25
iv_at = lambda e: float(term.loc[term.exp == e, 'atm_iv'].iloc[0]) if (e and (term.exp == e).any()) else None
cur_term = [{"exp": r.exp, "d": round(float(r.d), 2), "iv": float(r.atm_iv)} for r in term.itertuples()]
cum = lambda T, jump=True: vinf*T + (v0-vinf)*tau*(1-np.exp(-T/tau)) + (J**2 if (jump and T > T_EARN) else 0)
dv7 = np.sqrt(cum(7/365.25, False) / (7/365.25)) * 100
errs = [abs(np.sqrt(cum(r.T)/r.T)*100 - r.atm_iv) for r in term.itertuples() if r.d > 7.5]
fit_err = max(errs) if errs else 0.0
lr = np.sqrt(vinf) * 100

# ---------------- forecast tables ----------------
LBL = {"Next week (7d)": "Next week", "10 days": "10 days", "20 days": "20 days", "30 days": "30 days", "45 days": "45 days"}
ph['label'] = ph.horizon.map(LBL)
ph['date_s'] = [dd(NOW + dt.timedelta(days=int(d))) for d in ph.dte]
rows_fc = "\n".join(
    f'      <tr><td class="lbl">{r.label}</td><td>{r.date_s}</td><td class="mid">{r.median:.0f}</td>'
    f'<td class="band">{r.p25:.0f} – {r.p75:.0f}</td><td class="band">{r.p10:.0f} – {r.p90:.0f}</td>'
    f'<td>{r.P_up:.0f}%</td><td>{r.P_dn15:.0f}%</td><td>{r.P_up15:.0f}%</td></tr>' for r in ph.itertuples())
rows_both = "\n".join(
    f'      <tr><td class="lbl">{q.label}</td><td class="band">{a.atm_iv:.1f}%</td><td class="band">{a.p05:.0f}</td><td class="mid">{a.median:.0f}</td>'
    f'<td class="band">{a.p95:.0f}</td><td class="band">{q.p10:.0f}</td><td class="mid">{q.median:.0f}</td><td class="band">{q.p90:.0f}</td></tr>'
    for a, q in zip(rn.itertuples(), ph.itertuples()))
r45 = ph.iloc[-1]
ivh = dict(zip(rn.dte, rn.atm_iv))
hz = list(ph.dte)
before = [d for d in hz if HAS and d < earn_d]; after = [d for d in hz if HAS and d > earn_d]
if HAS and earn_d <= 45 and before and after:
    fc_earn = f"The band jumps between the {before[-1]}-day and {after[0]}-day horizons because the {earn_short} earnings report falls between them."
    fan_earn = f"The step between the {before[-1]}-day and {after[0]}-day horizons is the {earn_short} earnings report. "
elif HAS and earn_d <= 45:
    fc_earn = f"Every horizon includes the {earn_short} earnings report, which is why even the first week is wide."; fan_earn = ""
elif HAS:
    fc_earn = f"The next earnings report, on {earn_short}, falls beyond these horizons, so the bands widen smoothly."; fan_earn = ""
else:
    fc_earn = "No earnings report falls inside the listed expirations, so the bands widen smoothly."; fan_earn = ""
if ivh[20] > ivh[10] and ivh[20] > ivh[30]:
    both_note = (f"The <b>20-day ATM IV of {ivh[20]:.1f}%</b> sits above both the 10-day ({ivh[10]:.1f}%) and the 30-day ({ivh[30]:.1f}%). "
                 "A term structure that rises and then falls is an event priced into one date.")
else:
    both_note = f"ATM IV runs {ivh[7]:.1f}% at 7 days, {ivh[20]:.1f}% at 20 days and {ivh[45]:.1f}% at 45 days."

ratio = (1 / ph.haircut).round(2); r_post = ratio[ph.dte >= 20]
iv_eff = ph.vol / ph.haircut
drift45 = SPOT * (np.exp((0.04122 + float(calib.get('beta', 1.5)) * 0.045 - float(run.get('div', 0))) * 45/365.25) - 1)
a7, a45 = (ph.haircut.iloc[0]-1)*100, (ph.haircut.iloc[-1]-1)*100
side = lambda a: "about the same width as the market's" if abs(a) < 2 else f"{abs(a):.0f}% {'narrower' if a < 0 else 'wider'} than the market's"
CAL = bool(calib.get('calibrated', True))
BETA = float(calib.get('beta', 1.5)); MU = 0.04122 + BETA * 0.045
beta_note = "" if (TICK.get('beta') or run.get('beta')) else " (assumed: too little history to measure it)"
calib_text = (f"On the {calib['n_days']:,} past days when {NAME}'s trailing 20-day realized volatility was between "
              f"{calib['band_lo']*100:.0f}% and {calib['band_hi']*100:.0f}% (it is {calib['rv20_now']*100:.0f}% now), forward 21-day realized "
              f"volatility came in at a {calib['fwd_median']*100:.1f}% median. "
              + (f"Adding one earnings day with a {calib['earn_sd']*100:.1f}% standard deviation, taken from the last {calib['n_earn']} reports, gives "
                 if HAS else "That gives ")
              + f"{ph.vol.min():.0f}–{ph.vol.max():.0f}% expected realized volatility across the five horizons, against {iv_eff.min():.0f}–{iv_eff.max():.0f}% implied. "
              f"So the real-world bands are {side(a7)} at one week and {side(a45)} at 45 days.") if CAL else (
              f"There is not enough trading history ({calib.get('n_hist', 0)} sessions) to measure how {NAME}'s realized volatility "
              "compares with what its options imply, so the real-world bands keep the market's own width and add only the drift.")

# ---------------- previous edition and running history ----------------
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
NUM = ('spot', 'iv7', 'iv30', 'J', 'lr', 'med45', 'p10_45', 'p25_45', 'p75_45', 'p90_45', 'rev1y', 'pt_mean')
OPTIONAL = ('J', 'rev1y', 'pt_mean')
def clean(e, with_term=False):
    """Previous editions come from the live site: keep known fields only, with checked types."""
    if not isinstance(e, dict) or not DATE_RE.match(str(e.get('date', ''))): return None
    o = {'date': e['date'], 'asof': str(e.get('asof', e['date']))[:40], 'mode': 'mid' if e.get('mode') == 'mid' else 'last',
         'earn_next': e.get('earn_next') if DATE_RE.match(str(e.get('earn_next') or '')) else None}
    for k in NUM:
        v = e.get(k); o[k] = float(v) if isinstance(v, (int, float)) and np.isfinite(v) else None
    if any(o[k] is None for k in NUM if k not in OPTIONAL): return None
    if with_term:
        o['term'] = [[t[0], float(t[1])] for t in e.get('term', []) if isinstance(t, list) and len(t) == 2
                     and DATE_RE.match(str(t[0])) and isinstance(t[1], (int, float))]
    return o
prevdata = seed or {'schema': 1, 'edition': None, 'previous': None, 'history': []}
if PREV_PATH and os.path.exists(PREV_PATH):
    try:
        prevdata = json.load(open(PREV_PATH)); assert prevdata.get('schema') == 1 and isinstance(prevdata.get('history'), list)
    except Exception as ex:
        sys.exit(f"STOP (exit 5): previous data.json unreadable ({ex}); refusing to reset the history")
ed = clean(prevdata.get('edition'), True)
base = ed if ed and ed['date'] != today else clean(prevdata.get('previous'), True)
history = [c for c in (clean(e) for e in prevdata['history']) if c and c['date'] != today]
cur = dict(date=today, asof=asof, mode=MODE, spot=SPOT, iv7=float(rn.atm_iv.iloc[0]), iv30=float(ivh[30]),
           J=round(J*100, 2) if HAS else None, lr=round(lr, 1), med45=float(r45['median']), p10_45=float(r45.p10),
           p25_45=float(r45.p25), p75_45=float(r45.p75), p90_45=float(r45.p90), earn_next=run.get('earn_next'),
           rev1y=((run.get('est', {}).get('rev', {}).get('+1y') or {}).get('avg') or None),
           pt_mean=((run.get('est', {}).get('pt') or {}).get('mean') or None))
history = (history + [cur])[-500:]
data_out = dict(schema=1, edition=dict(cur, term=[[r.exp, float(r.atm_iv)] for r in term.itertuples()]), previous=base, history=history)
wk = [e for e in history[:-1] if iso(e['date']) <= NOW.date() - dt.timedelta(days=5)]
wk = wk[-1] if wk and (not base or wk[-1]['date'] != base['date']) else None

cols = [c for c in (wk, base) if c] + [cur]
cmp_head = "".join(f"<th>{esc(dd(iso(c['date'])) if c is not cur else asof_col)}</th>" for c in cols)
METRICS = [(f"{SYM} price", lambda e: f"${e['spot']:.2f}"),
           ("7-day ATM implied vol", lambda e: f"{e['iv7']:.1f}%"),
           ("30-day ATM implied vol", lambda e: f"{e['iv30']:.1f}%"),
           ("Priced earnings move (1 s.d.)", lambda e: f"±{e['J']:.2f}%" if e.get('J') else "–"),
           ("Next earnings date", lambda e: dd(iso(e['earn_next'])) if e.get('earn_next') else "–"),
           ("Long-run implied vol", lambda e: f"{e['lr']:.1f}%"),
           ("45-day central estimate", lambda e: f"${e['med45']:.0f}"),
           ("45-day 50% band", lambda e: f"${e['p25_45']:.0f}–{e['p75_45']:.0f}"),
           ("Next-year revenue consensus", lambda e: f"${e['rev1y']/1e9:,.1f}B" if e.get('rev1y') else "–"),
           ("Mean analyst price target", lambda e: f"${e['pt_mean']:,.0f}" if e.get('pt_mean') else "–")]
rows_cmp = "\n".join(f'      <tr><td class="lbl">{m}</td>' + "".join(
    f'<td class="{"mid" if c is cur else "was"}">{f(c)}</td>' for c in cols) + "</tr>" for m, f in METRICS)

F = []
if base:
    F.append(f"<strong>Price.</strong> {SYM} is ${SPOT:.2f}, {sgn((SPOT/base['spot']-1)*100)}% since the previous edition ({esc(base['asof'])}).")
    d7 = cur['iv7'] - base['iv7']
    F.append(f"<strong>Near-term volatility.</strong> " + (f"Seven-day implied volatility is {cur['iv7']:.1f}%, about the same as the previous {base['iv7']:.1f}%."
             if abs(d7) < 1.5 else f"Seven-day implied volatility {'rose' if d7 > 0 else 'fell'} from {base['iv7']:.1f}% to {cur['iv7']:.1f}%."))
    if HAS and base.get('J') and base.get('earn_next') == run.get('earn_next'):
        jd = J*100 - base['J']; verb = "is steady at" if abs(jd) < 0.3 else ("rose to" if jd > 0 else "eased to")
        F.append(f"<strong>Earnings premium.</strong> The one-day move priced for the {earn_short} report {verb} ±{J*100:.2f}% (previous ±{base['J']:.2f}%).")
    elif HAS and base.get('earn_next') and base['earn_next'] != run.get('earn_next'):
        F.append(f"<strong>New event.</strong> The {dd(iso(base['earn_next']))} report has passed. The options now price the {earn_short} report at ±{J*100:.2f}%.")
    elif HAS:
        F.append(f"<strong>Earnings premium.</strong> The one-day move priced for the {earn_short} report is ±{J*100:.2f}%.")
    else:
        F.append("<strong>No event priced.</strong> No earnings report falls inside the listed expirations.")
    wn, wb = (cur['p75_45']-cur['p25_45'])/SPOT, (base['p75_45']-base['p25_45'])/base['spot']
    rel = wn/wb - 1
    relw = "about as wide as before in percentage terms" if abs(rel) < 0.07 else ("wider than before" if rel > 0 else "narrower than before")
    F.append(f"<strong>Forecast.</strong> The 45-day central estimate is ${cur['med45']:.0f} (previous ${base['med45']:.0f}), and the 50% band of "
             f"${cur['p25_45']:.0f}–{cur['p75_45']:.0f} is {relw}.")
findings = "\n".join(f"  <li>{x}</li>" for x in F) or "  <li>This is the first edition, so there is nothing to compare yet.</li>"
hist_caption = (f"<b>{len(history)} editions so far.</b> Each point is one edition, plotted on the day it was made. The blue line is that edition's "
                "45-day central estimate and the shaded band its 50% range; the grey line is the stock price that day.")

# ---------------- cross-complex ----------------
c5, c20 = cx['chg5'], cx['chg20']
days5 = sorted(cx['daily'].keys())
TKS = cx['tickers']; BENCH = TICK.get('bench', TKS[-1]); BNAME = TICK.get('bench_name', BENCH)
complex_d = [{"t": t, "v": c5[t], "v20": c20[t], "days": [[dd(iso(k)), cx['daily'][k][t]] for k in days5]} for t in TKS]
cell = lambda v, b=False: f'<td class="{"mid " if b else ""}{"up" if v > 0 else "dn"}">{sgn(v,2)}%</td>'
rows_daily = "\n".join(f'      <tr><td class="lbl">{dd(iso(k))}</td>' + "".join(cell(cx['daily'][k][t]) for t in TKS) + "</tr>" for k in days5)
rows_daily += f'\n      <tr><td class="lbl"><b>{cx["n5"]} sessions</b></td>' + "".join(cell(c5[t], True) for t in TKS) + "</tr>"
rel5 = c5[SYM] - c5[BENCH]
relp = (f"lagged {BNAME} by {abs(rel5):.1f} points" if rel5 < -2 else
        f"beat {BNAME} by {rel5:.1f} points" if rel5 > 2 else f"moved roughly in line with {BNAME}")
others = [t for t in TKS[1:] if t != BENCH]
cx_caption = (f"<b>Over {cx['n5']} sessions {SYM} is {sgn(c5[SYM])}%.</b> It has {relp} ({sgn(c5[BENCH])}%). "
              + ", ".join(f"{t} {sgn(c5[t])}%" for t in others) + "."
              + (f" Over {cx['n20']} sessions {SYM} is {sgn(c20[SYM])}% against {sgn(c20[BENCH])}% for {BENCH}." if cx['n20'] > cx['n5'] else ""))
c2, c6 = cx.get('corr20'), cx.get('corr60')
cstr = lambda c: ", ".join(f"{t} {c[t]:.2f}" for t in TKS[1:] if t in c)
corr_note = ((f"Correlation of daily returns with {SYM} over 20 sessions: {cstr(c2)}." if c2 else
              f"{SYM} has only {cx['sessions']} sessions of history, too few for a meaningful correlation.")
             + (f" Over 60 sessions: {cstr(c6)}." if c6 else ""))
daily_head = "".join(f"<th>{t}</th>" for t in TKS)
peer_names = {"SMH": "the semiconductor ETF (SMH)", "QQQ": "the Nasdaq-100 (QQQ)", "SPY": "the S&P 500 (SPY)", "XBI": "the biotech ETF (XBI)", "IBB": "the biotech index fund (IBB)"}
pl = [peer_names.get(t, t) for t in TKS[1:]]
peer_list = ", ".join(pl[:-1]) + " and " + pl[-1]
peer_syms = ", ".join(TKS[1:-1]) + " and " + TKS[-1]

# ---------------- forward curve ----------------
fexp = []
for tgt in (7, 30, 60, 120, 210, 390, 10000):
    e = term.iloc[(term.d - tgt).abs().argsort().iloc[0]].exp
    if e not in fexp: fexp.append(e)
fr = term.set_index('exp').loc[fexp]
fwd_head = "".join(f"<th>{dt.datetime.strptime(e,'%Y-%m-%d').strftime('%-d %b' + (' %y' if e[:4] != today[:4] else ''))}</th>" for e in fexp)
fwd_row = "".join(f"<td>{r.F:.2f}</td>" for r in fr.itertuples())
fwd_days = "".join(f'<td class="band">{int(round(r.d))}</td>' for r in fr.itertuples())
lastF = fr.iloc[-1]; carry = ((lastF['F'] / SPOT) ** (1 / lastF['T']) - 1) * 100

# ---------------- term section text ----------------
base_term = dict(base['term']) if base and base.get('term') else {}
term_prev = []
for e, v in base_term.items():
    d = (dt.datetime.strptime(e, '%Y-%m-%d').replace(hour=16) - NOW).total_seconds() / 86400
    if d > 0.3: term_prev.append({"exp": e, "d": round(d, 2), "iv": v})
if HAS and PRE and POST:
    term_caption = (f"<b>The kink is the earnings report.</b> The {dd(iso(PRE))} expiry, the last before the {earn_short} report, trades at "
                    f"{iv_at(PRE):.1f}%; the {dd(iso(POST))} expiry, the first after it, trades at {iv_at(POST):.1f}%.")
    if PRE in base_term and POST in base_term:
        term_caption += f" In the previous edition they were {base_term[PRE]:.1f}% and {base_term[POST]:.1f}%."
    term_caption += " The step between them is the market pricing one day."
elif HAS:
    term_caption = f"<b>Every listed expiration spans the {earn_short} report</b>, so its jump is spread across the whole curve."
else:
    term_caption = "<b>No event kink.</b> No earnings report falls inside the listed expirations."
if SHOW:
    prevtxt = f", against ±{base['J']:.2f}% in the previous edition" if base and base.get('J') and base.get('earn_next') == run.get('earn_next') else ""
    direct = f" Read directly off the {dd(iso(PRE))} / {dd(iso(POST))} pair it is <b>±{Jd*100:.2f}%</b>." if np.isfinite(Jd) and PRE else ""
    event_card = (f'<div class="minicard"><div class="mt">Earnings jump</div><div class="mv">±{J*100:.2f}%</div><div class="md">A one-day move of '
                  f'±{J*100:.2f}% (one standard deviation) priced for the {earn_long} report{prevtxt}.{direct}</div></div>')
    market_position = (f"The market's position is that volatility settles toward {lr:.0f}%, except for one day that could move the stock by "
                       f"about {J*100*np.sqrt(2/np.pi):.0f}% on average.")
elif HAS:
    event_card = (f'<div class="minicard"><div class="mt">Earnings jump</div><div class="mv">±{J*100:.1f}%</div><div class="md">The options price little '
                  f'or no extra move for the {earn_long} report so far. That usually means the expirations around it are still thinly traded.</div></div>')
    market_position = f"The market's position is that volatility settles toward {lr:.0f}%."
else:
    event_card = ('<div class="minicard"><div class="mt">Earnings jump</div><div class="mv">none priced</div><div class="md">No earnings report '
                  'falls inside the listed expirations, so the model fits the diffusive part only.</div></div>')
    market_position = f"The market's position is that volatility settles toward {lr:.0f}%."

# ---------------- earnings verdict ----------------
if NE >= 8:
    earn_caption = (f"<b>{WORDS[n_big]} of the last {len(earn12)} reports moved the stock more than 9%.</b> Over all {NE} reports since {hist_since} the "
                    f"average absolute move is {all_mean:.2f}%. Over the last eight it is <b>{r8_mean:.2f}%</b>, with a signed standard deviation of <b>{r8_sd:.2f}%</b>.")
elif NE:
    earn_caption = (f"<b>Only {WORDS[NE].lower()} report{'s' if NE > 1 else ''} since {hist_since}.</b> The average absolute next-session move was "
                    f"{all_mean:.2f}%. That is too few to judge whether the options are cheap or rich for the next one.")
else:
    earn_caption = f"<b>No earnings reports since {hist_since}.</b> There is no history yet to compare the options with."
earn_era = ("Broadcom's record splits sharply by era." if SYM == 'AVGO' else
            "Here is what the stock has done after recent reports." if NE >= 4 else
            f"{NAME} has little or no earnings history as a listed company, so this comparison is limited.")
if SHOW and NE >= 4:
    J_abs = J*100*np.sqrt(2/np.pi); q = J_abs / r8_mean
    verdict = "look cheap relative to" if q < 0.9 else ("look fairly priced against" if q <= 1.1 else "look rich relative to")
    p1 = (f"<p><strong>The {earn_short} options {verdict} recent history.</strong> A ±{J*100:.2f}% one-day standard deviation corresponds to an "
          f"average absolute move of about {J_abs:.1f}%, against {r8_mean:.2f}% over the last eight reports and a {r8_sd:.2f}% signed dispersion.</p>")
    lo_, hi_ = r_post.min(), r_post.max()
    if not CAL:
        p2 = ""
    elif hi_ <= 1.05:
        p2 = f"<p>Over 20–45 days, implied volatility is roughly equal to the expected realized level ({lo_:.2f}–{hi_:.2f}×), so there is little premium outside the event.</p>"
    elif lo_ >= 1.10:
        p2 = (f"<p>Over 20–45 days, implied volatility runs {lo_:.2f}–{hi_:.2f}× the expected realized level. That gap is premium outside the event"
              + (", and with the event itself not expensive the surface points to a calendar spread: short non-event volatility, long the event.</p>" if q <= 1.1 else ".</p>"))
    else:
        p2 = f"<p>Over 20–45 days, implied volatility sits slightly above the expected realized level ({lo_:.2f}–{hi_:.2f}×).</p>"
    finding_call = f'<div class="call">\n  <div class="ct">Finding</div>\n  {p1}\n  {p2}\n</div>'
else:
    finding_call = ""

# ---------------- scenario section ----------------
if HAS and scen.get('event_date') == run.get('earn_next'):
    sc = scen['scenarios']; ev = sum(s['p']*s['move'] for s in sc); sd = np.sqrt(sum(s['p']*(s['move']-ev)**2 for s in sc)) * 100
    alt = scen.get('alternative'); ev_alt = sum(p*m for p, m in zip(alt['p'], alt['move'])) if alt else None
    def srow(p, title, desc, mv, tot=False):
        bar = '' if tot else f'<div class="sbar"><i style="width:{p}%"></i></div>'
        return (f'  <div class="srow{" tot" if tot else ""}"><div><div class="sp">{p}%</div>{bar}</div>\n    <div class="sl"><b>{esc(title)}</b>{esc(desc)}</div>\n'
                f'    <div class="smv {"up" if mv > 0 else "dn"}">{sgn(mv*100, 1 if tot else 0)}%</div><div class="spx">${SPOT*(1+mv):.0f}</div></div>')
    rows = "\n".join([srow(int(round(s['p']*100)), s['title'], s['desc'], s['move']) for s in sc] +
                     [srow(100, "Probability-weighted", f"Dispersion of {sd:.1f}% against the ±{J*100:.2f}% the options imply", ev, True)])
    written = dd(iso(scen['written'])) + (f", revised {dd(iso(scen['revised']))}" if scen.get('revised') else "")
    scenario_section = (
        f'<div class="col">\n<section>\n  <div class="kicker">{earn_short} earnings</div>\n  <h2>The decision tree</h2>\n'
        f'  <p>Because one event dominates the outlook, a scenario tree is more useful than a continuous distribution. The swing variable is narrow: '
        f'<strong>{esc(scen["swing"])}</strong>. Prices below apply each move to {SPOT:.2f}.</p>\n</section>\n</div>\n'
        f'<div class="scen">\n{rows}\n</div>\n<div class="col">\n<section>\n'
        f'  <p>The weights were written by hand ({written}). My scenario dispersion of {sd:.1f}% compares with the ±{J*100:.2f}% the market charges. '
        f'The weighted outcome is ${SPOT*(1+ev):.0f}, {sgn(ev*100)}% from today\'s price, but that average describes almost none of the possible worlds. '
        f'This is a <strong>bimodal event</strong>, and the mean sits between the two modes.</p>\n</section>\n</div>\n'
        + (f'<div class="call">\n  <div class="ct">Sensitivity to the weights</div>\n  <p>{esc(alt["why"])} Using {esc(alt["label"])} gives '
           f'<strong>${SPOT*(1+ev_alt):.0f}</strong>. Treat <strong>${min(SPOT*(1+ev),SPOT*(1+ev_alt)):.0f}–{max(SPOT*(1+ev),SPOT*(1+ev_alt)):.0f}</strong> '
           f'as the range for the probability-weighted outcome. The guidance itself matters far more than where in that range the weights sit.</p>\n</div>' if alt else ""))
    scen_limit = (f"<li><strong>Scenario probabilities are judgment.</strong> The tree for the {earn_short} report was written by hand ({written}). "
                  "It is not extracted from prices the way the rest of the page is.</li>")
else:
    last = dd(iso(scen['event_date'])) if scen.get('event_date') else None
    if not scen: last = None
    scenario_section = (
        '<div class="col">\n<section>\n  <div class="kicker">Earnings scenarios</div>\n'
        f'  <h2>No scenario tree for the {earn_short + " " if earn_short else "next "}report yet</h2>\n'
        '  <p>A scenario tree is judgment rather than market data, so it is written by hand for each report'
        + (f'. The last one covered the {last} report' if last else '') +
        '. Until a new one is written, the market-implied distribution above is the full picture.</p>\n</section>\n</div>')
    scen_limit = ""

# ---------------- positioning ----------------
tot_oi = sum(p['oi_c'] + p['oi_p'] for p in pos['positions'])
if tot_oi > 0:
    prow = []
    for p in pos['positions']:
        e = dt.datetime.strptime(p['exp'], '%Y-%m-%d').strftime('%-d %b %y')
        tc = ", ".join(f"{k:.0f}" for k, v in p['top_calls'][:3]); tp = ", ".join(f"{k:.0f}" for k, v in p['top_puts'][:3])
        prow.append(f'      <tr><td class="lbl">{e}</td><td>{(p["oi_c"]+p["oi_p"]):,}</td><td>{p["pc_oi"]:.2f}</td><td>{p["pc_vol"]:.2f}</td>'
                    f'<td class="mid">{"$%.0f" % p["max_pain"] if p["max_pain"] else "–"}</td><td class="band">{tc}</td><td class="band">{tp}</td></tr>')
    pos_table = ('<div class="tbl">\n  <table>\n    <caption>Open interest by expiration</caption>\n'
                 '    <thead><tr><th>Expiry</th><th>Open interest</th><th>Put/call OI</th><th>Put/call volume</th><th>Max pain</th><th>Largest call strikes</th><th>Largest put strikes</th></tr></thead>\n'
                 '    <tbody>\n' + "\n".join(prow) + '\n    </tbody>\n  </table>\n</div>')
    big = max(pos['positions'], key=lambda p: p['oi_c'] + p['oi_p'])
    mp = [p['max_pain'] for p in pos['positions'] if p['max_pain']]
    pos_prose = (f"<p>The {dt.datetime.strptime(big['exp'], '%Y-%m-%d').strftime('%-d %B')} expiration is the largest of the near ones, with "
                 f"{(big['oi_c']+big['oi_p']):,} contracts outstanding and a put/call open-interest ratio of <strong>{big['pc_oi']:.2f}</strong>. "
                 f"Max pain across these expirations runs ${min(mp):.0f}–{max(mp):.0f}, against a spot of ${SPOT:.0f}. Max pain records where open "
                 "interest was written. It is not a forecast.</p>")
    far = pos.get('far_calls', [])
    if far:
        parts = " and ".join(f"{v:,} contracts at the ${k:.0f} strike ({dd(iso(e))})" for e, k, v in far)
        pos_prose += (f"<p>Far out-of-the-money calls still carry open interest: {parts}, at least 50% above today's price. Positioning like this "
                      "was written when the stock was higher, and its decay works against a rally because dealers short those calls have little left to hedge.</p>")
else:
    pos_table = ""
    pos_prose = ("<p>Open interest was not available in this data pull (the source publishes zeros outside market hours), so positioning and "
                 "max pain could not be refreshed in this edition.</p>")

# ---------------- notes ----------------
notes_html = "\n".join(
    f'  <div class="note"><div class="nd">{iso(n["date"]).strftime("%-d %B %Y")}</div><h3>{esc(n["title"])}</h3>' +
    "".join(f"<p>{p}</p>" for p in n["paras"]) + "</div>"
    for n in sorted(notes, key=lambda n: n['date'], reverse=True)) or "  <p>No notes written for this stock yet.</p>"

# ---------------- data quality ----------------
if MODE == 'mid':
    data_limit_head = "Intraday quotes move."
    data_limit = (f"This edition uses bid/ask mids taken at {NOW.strftime('%H:%M ET')} on {NOW.strftime('%-d %B')}. Yahoo Finance option quotes can lag "
                  "the stock by several minutes, so very short-dated figures carry extra noise.")
    method_prices = "Mid prices are filtered for two-sided quotes and spreads under 150% of mid."
    method_fwd = ""; fwd_note = ""
else:
    data_limit_head = "This edition uses last trades."
    data_limit = ("It was built outside market hours, when the data source shows no live quotes. Each contract's last trade from the session was "
                  "repriced to the closing stock price, which is noisier than bid/ask mids, and open interest was unavailable.")
    method_prices = ("Built outside market hours, so each contract's last trade from the latest session stands in for a mid, repriced to the closing "
                     "stock price under a sticky-strike assumption.")
    method_fwd = " (in this edition pinned to cost of carry, because unsynchronised last trades make the parity regression noisy)"
    fwd_note = " In this edition the forward is pinned to carry because the quotes were last trades."

n_contracts = sum(len(C) + len(Pp) for C, Pp in chains.values())
from_high = (1 - SPOT / float(run['high52'])) * 100
standfirst = (f"{NAME}'s options chain, {len(term)} expirations and every strike, holds the market's own probability distribution for where the "
              f"stock goes next. This page re-reads it every trading day. As of {asof_short} the stock is ${SPOT:.2f}, {from_high:.0f}% below its "
              "52-week high" + (f", and the <em>{earn_short}</em> earnings report dominates every horizon that includes it." if HAS and earn_d <= 45 else
                                (f". The next earnings report, on <em>{earn_short}</em>, is {int(earn_d)} days away." if HAS else ".")))

# ---------------- menu (Pages only; the claude.ai copy is a single page) ----------------
if PAGES:
    links = "".join(f'<a href="../{t["sym"].lower()}/index.html"' + (' aria-current="page"' if t['sym'] == SYM else '') + f'>{t["sym"]}</a>' for t in TICKERS)
    nav = f'<nav class="topnav" aria-label="Reports"><div class="navin"><a class="home" href="../index.html">All reports</a>{links}</div></nav>'
else:
    nav = ""

# ---------------- reduced-data notice ----------------
why = []
if THIN: why.append(f"only {len(term)} option expirations are listed, so the term structure and the earnings jump rest on few points")
if not CAL: why.append(f"the stock has {calib.get('n_hist', 0)} sessions of trading history, too few to calibrate the real-world bands")
if NE < 4: why.append("there is little or no earnings history to compare the options with")
limited_note = ('<div class="col"><div class="call limited"><div class="ct">Read with care</div><p>This report runs on thinner data than a '
                'mature, heavily traded stock: ' + "; ".join(why) + ". The market-implied ranges are still informative, but treat the finer "
                "details as rough.</p></div></div>") if why else ""

# ---------------- AI spending by the largest buyers ----------------
capex_d = None; capex_section = ""
if capex and capex.get('companies'):
    allq = sorted({q for c in capex['companies'] for q in c['q']})
    qs = [q for q in allq if sum(q in c['q'] for c in capex['companies']) >= 4]
    if qs:
        q0 = qs[-1]; qy = f"{int(q0[:4]) - 1}-Q{q0[-1]}"
        quarters = [q for q in allq if q <= q0][-5:]
        capex_d = {"quarters": quarters,
                   "cos": [{"name": c['name'], "vals": [c['q'].get(q, {}).get('capex') for q in quarters],
                            "ocf": [c['q'].get(q, {}).get('ocf') for q in quarters]} for c in capex['companies']]}
        both = [c for c in capex['companies'] if q0 in c['q'] and qy in c['q']]
        cap0 = sum(c['q'][q0]['capex'] for c in both); capy = sum(c['q'][qy]['capex'] for c in both)
        ocf0 = sum(c['q'][q0]['ocf'] or 0 for c in both); ocfy = sum(c['q'][qy]['ocf'] or 0 for c in both)
        g = (cap0 / capy - 1) * 100 if capy else float('nan')
        i0 = cap0 / ocf0 * 100 if ocf0 else float('nan'); iy = capy / ocfy * 100 if ocfy else float('nan')
        gw = ("still growing very fast" if g >= 40 else "growing strongly" if g >= 15 else "growing slowly" if g >= 0 else "falling")
        inten = ("Spending now exceeds the cash their operations generate, so the difference comes from cash reserves or borrowing. "
                 "Whether that can continue is the main question for how long AI demand stays this strong." if i0 >= 100
                 else "That is a high share, which leaves less room to raise spending further without borrowing or cutting buybacks." if i0 >= 70
                 else "The share is rising, so spending is growing faster than the cash that pays for it." if i0 - iy >= 10 else "")
        crow = []
        for c in capex['companies']:
            if not c['q']:
                crow.append(f'<tr><td class="lbl">{esc(c["name"])}</td><td>–</td><td>–</td><td>–</td><td>–</td></tr>'); continue
            lq = sorted(c['q'])[-1]; v = c['q'][lq]; pv = c['q'].get(f"{int(lq[:4]) - 1}-Q{lq[-1]}")
            yoy = f"{sgn((v['capex'] / pv['capex'] - 1) * 100, 0)}%" if pv and pv['capex'] else "–"
            ic = f"{v['capex'] / v['ocf'] * 100:.0f}%" if v.get('ocf') else "–"
            crow.append(f'<tr><td class="lbl">{esc(c["name"])}</td><td>{lq.replace("-", " ")}</td><td class="mid">${v["capex"]:.1f}B</td><td>{yoy}</td><td>{ic}</td></tr>')
        crows = "\n      ".join(crow)
        tie = f" It is the demand backdrop the {earn_short} report will be judged against." if EN else ""
        capex_section = (
            '<div class="col">\n<section>\n  <div class="kicker">AI spending</div>\n  <h2>What the biggest AI buyers are spending</h2>\n'
            f'  <p>{esc(NAME)} sells into a data-center buildout funded by a handful of very large buyers, so their capital spending is the clearest '
            f'public read on demand for its products. In {q0.replace("-", " ")} the {len(both)} largest US spenders with comparable data put '
            f'<strong>${cap0:.0f}B</strong> into capex, {sgn(g, 0)}% from a year earlier, so spending is {gw}.</p>\n'
            f'  <p>That spending absorbed <strong>{i0:.0f}%</strong> of their combined operating cash flow, against {iy:.0f}% a year earlier. {inten}</p>\n'
            '</section>\n</div>\n<figure>\n  <div class="figtitle">Quarterly capital spending, largest AI buyers</div>\n'
            '  <div class="figsub">$ billions · calendar quarters · latest quarter highlighted</div>\n'
            '  <div class="chartbox"><div class="chart" id="c-capex"></div></div>\n'
            f'  <figcaption>None of this enters the options-implied forecast directly, because option prices already reflect what traders know.{tie} '
            "Reported capex lags spending plans; changes to those plans arrive with each buyer's own earnings report.</figcaption>\n</figure>\n"
            '<div class="tbl fit">\n  <table>\n    <caption>Latest reported quarter by buyer</caption>\n'
            '    <thead><tr><th>Buyer</th><th>Quarter</th><th>Capex</th><th>vs a year ago</th><th>Share of operating cash flow</th></tr></thead>\n'
            f'    <tbody>\n      {crows}\n    </tbody>\n  </table>\n'
            "  <div class=\"tnote\">Source: company cash-flow statements via Yahoo Finance. Quarters are mapped to calendar quarters by period end; "
            "Oracle's fiscal quarters end in February, May, August and November. A dash means the quarter is missing from the data source.</div>\n</div>")

# ---------------- analyst expectations ----------------
est = run.get('est') or {}
REV, EPS, PT = est.get('rev') or {}, est.get('eps') or {}, est.get('pt') or {}
expect_section = ""
if REV or EPS:
    money = lambda v: "–" if v is None else (f"${v / 1e9:,.1f}B" if abs(v) >= 1e9 else f"${v / 1e6:,.0f}M")
    pct = lambda v: "–" if v is None else f"{sgn(v * 100, 0)}%"
    epsf = lambda v: "–" if v is None else S(v, 2)
    erow = []
    for k, l in (('0q', 'Current quarter'), ('+1q', 'Next quarter'), ('0y', 'Current fiscal year'), ('+1y', 'Next fiscal year')):
        r_, e_ = REV.get(k) or {}, EPS.get(k) or {}
        if not r_ and not e_: continue
        n_ = r_.get('numberOfAnalysts') or e_.get('numberOfAnalysts')
        erow.append(f'<tr><td class="lbl">{l}</td><td class="mid">{money(r_.get("avg"))}</td><td>{pct(r_.get("growth"))}</td>'
                    f'<td>{epsf(e_.get("avg"))}</td><td>{pct(e_.get("growth"))}</td><td>{int(n_) if n_ else "–"}</td></tr>')
    erows = "\n      ".join(erow)
    ptxt = ""
    if PT.get('mean'):
        up = (PT['mean'] / SPOT - 1) * 100
        rng = f" (range ${PT['low']:,.0f}–{PT['high']:,.0f})" if PT.get('low') and PT.get('high') else ""
        ptxt = (f"<p>The mean analyst price target is <strong>${PT['mean']:,.0f}</strong>, {sgn(up, 0)}% from today's price{rng}. "
                + ("Targets often lag sharp price moves, so a gap this large usually narrows partly through target cuts." if abs(up) > 40 else "") + "</p>")
    r1 = (REV.get('+1y') or {}).get('avg'); g1 = (REV.get('+1y') or {}).get('growth')
    rev_txt = ""
    if base and base.get('rev1y') and r1:
        ch = (r1 / base['rev1y'] - 1) * 100
        rev_txt = (" Since the previous edition the next-year revenue consensus has "
                   + ("barely moved" if abs(ch) < 0.5 else f"{'risen' if ch > 0 else 'fallen'} {abs(ch):.1f}%")
                   + f" (${base['rev1y'] / 1e9:,.1f}B to ${r1 / 1e9:,.1f}B).")
    lead = (f"Analysts expect {esc(NAME)}'s revenue to grow <strong>{g1 * 100:.0f}%</strong> next fiscal year." if g1 is not None
            else "Consensus estimates for the coming periods are below.")
    expect_section = (
        '<div class="col">\n<section>\n  <div class="kicker">Expectations</div>\n  <h2>What analysts expect</h2>\n'
        f'  <p>{lead} The options price how far the stock can move. Consensus estimates show what the business has to deliver to support the current price.{rev_txt}</p>\n'
        f'  {ptxt}\n</section>\n</div>\n<div class="tbl">\n  <table>\n    <caption>Consensus estimates</caption>\n'
        '    <thead><tr><th>Period</th><th>Revenue</th><th>Growth</th><th>EPS</th><th>Growth</th><th>Analysts</th></tr></thead>\n'
        f'    <tbody>\n      {erows}\n    </tbody>\n  </table>\n'
        '  <div class="tnote">Source: analyst consensus via Yahoo Finance. Fiscal periods follow the company\'s own calendar. The next-year revenue '
        'consensus and the mean price target are tracked edition by edition in the table near the top of the page.</div>\n</div>')


D = dict(sym=SYM, n5=cx['n5'], n20=cx['n20'], capex=capex_d, spot=SPOT, term=cur_term, term_prev=term_prev, jump=round(J*100, 2) if SHOW else 0, earn_d=round(earn_d, 2) if HAS else None,
         earn_label=earn_label, pre_exp=PRE if HAS else None, post_exp=POST if HAS else None, earn=earn12, hist=hist90,
         rn=rn[['dte', 'p05', 'p95', 'median']].to_dict('records'),
         phys=[dict(dte=int(r.dte), date=r.date_s, label=r.label, p10=r.p10, p25=r.p25, median=r.median, p75=r.p75, p90=r.p90) for r in ph.itertuples()],
         complex=complex_d,
         history=[{k: e[k] for k in ('date', 'asof', 'spot', 'med45', 'p25_45', 'p75_45', 'iv7', 'J')} for e in history])

vals = dict(
    title=esc(TICK['title']), sym=SYM, name=esc(NAME), legal=esc(TICK.get('legal', NAME)),
    first_edition=TICK.get('first_edition') or dd(iso(history[0]['date'])) + ' ' + history[0]['date'][:4],
    NAV=nav, LIMITED_NOTE=limited_note, CAPEX_SECTION=capex_section, EXPECT_SECTION=expect_section,
    DAILY_HEAD=daily_head, n5=cx['n5'], group=esc(TICK.get('group', '')), peer_list=peer_list, peer_syms=peer_syms,
    div=f"{float(run.get('div', 0)) * 100:.2f}", earn_era=earn_era, beta=f"{BETA:.2f}", beta_note=beta_note,
    mu=f"{MU * 100:.1f}", mu_m=f"{MU * 100 / 12:.1f}", hist_since=hist_since,
    asof=asof, asof_short=asof_short, chip="Refreshed each trading day", standfirst=standfirst,
    spot=f"{SPOT:.2f}", spot0=f"{SPOT:.0f}", chg_txt=chg_txt,
    ch5=sgn(c5[SYM]), ch5_cls='dn' if c5[SYM] < 0 else 'up',
    ch5_sub=" · ".join(f"{t} {sgn(c5[t])}%" for t in [BENCH] + [t for t in TKS[1:] if t != BENCH][:1]),
    iv30=f"{ivh[30]:.1f}", iv30_sub=(f"previous edition {base['iv30']:.1f}%" if base else "30-day at-the-money"),
    dte_earn=(f"{(EN - NOW.date()).days}d" if EN else "–"), earn_sub=(f"{EN.strftime('%a %-d %b')}, {when}" if EN else "next date not announced"),
    from_high=f"{from_high:.1f}", high52=f"{float(run['high52']):.2f}", low52=f"{float(run['low52']):.2f}", low_lbl=f"{round(float(run['low52'])):.0f}",
    b45_lo=f"{r45.p25:.0f}", b45_hi=f"{r45.p75:.0f}", b45_w=f"{r45.p75-r45.p25:.0f}", fc_earn=fc_earn,
    CMP_HEAD=cmp_head, ROWS_COMPARE=rows_cmp, FINDINGS=findings, hist_caption=hist_caption,
    cx_last=dd(iso(cx['last'])) + (" (intraday)" if MODE == 'mid' else " close"), cx_caption=cx_caption, ROWS_DAILY=rows_daily, corr_note=corr_note,
    FWD_HEAD=fwd_head, FWD_ROW=fwd_row, FWD_DAYS=fwd_days, carry=f"{carry:.1f}", fwd_note=fwd_note,
    term_h2=("The term structure has an earnings kink" if HAS else "The term structure"),
    term_intro_event=(f", and where one expiration jumps back up because it spans the {earn_short} report" if HAS and PRE else ""),
    n_exp=len(term), prev_label=(f"Previous edition ({dd(iso(base['date']))})" if term_prev else ""), prev_hidden=("" if term_prev else " hidden"),
    term_caption=term_caption, lr=f"{lr:.1f}", dv7=f"{dv7:.1f}", EVENT_CARD=event_card, fit_err=f"{fit_err:.1f}", market_position=market_position,
    earn_h2=(f"Is ±{J*100:.1f}% enough?" if SHOW else "How Broadcom moves on earnings"), n_earn_shown=len(earn12),
    band_hidden=("" if SHOW else " hidden"), J1=f"{J*100:.1f}", earn_caption=earn_caption, FINDING_CALL=finding_call,
    d0=dd(NOW), d45=dd(NOW + dt.timedelta(days=45)), fan_earn=fan_earn, calib_text=calib_text, drift45=f"{drift45:.0f}",
    ROWS_FORECAST=rows_fc, ROWS_BOTH=rows_both, both_note=both_note, SCENARIO_SECTION=scenario_section, SCEN_LIMIT=scen_limit,
    POS_PROSE=pos_prose, POS_TABLE=pos_table, NOTES=notes_html,
    data_limit_head=data_limit_head, data_limit=data_limit, n_contracts=f"{n_contracts:,}", method_prices=method_prices, method_fwd=method_fwd,
    mcap=f"{(run.get('market_cap') or 0)/1e12:.2f}",
    earn_footer=(f"Next earnings {earn_long}, {when}" if EN else "Next earnings date not yet announced"),
    DATA=json.dumps(D, separators=(',', ':')).replace('</', '<\\/'),
)
out = tpl
for k, v in vals.items():
    out = out.replace('{{' + k + '}}', str(v))
left = re.findall(r'\{\{\w+\}\}', out)
if left: sys.exit(f"unfilled placeholders: {sorted(set(left))}")

if PAGES:
    # Self-contained document: drop the web-font link and the claude.ai-only meta, lock scripts to this one by hash.
    out = re.sub(r'<link [^>]*fonts\.(googleapis|gstatic)\.com[^>]*>\n?', '', out)
    out = re.sub(r'<meta name="claude:[^>]*>\n?', '', out)
    scripts = re.findall(r'<script>(.*?)</script>', out, flags=re.S)
    assert len(scripts) == 1 and '<script ' not in out, "expected exactly one inline script"
    sha = base64.b64encode(hashlib.sha256(scripts[0].encode('utf-8')).digest()).decode()
    csp = (f"default-src 'none'; script-src 'sha256-{sha}'; style-src 'unsafe-inline'; img-src data:; "
           "base-uri 'none'; form-action 'none'; object-src 'none'")
    head, body = out.split('<div id="tip"', 1)
    out = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           f'<meta http-equiv="Content-Security-Policy" content="{csp}">\n'
           '<meta name="referrer" content="no-referrer">\n<meta name="robots" content="noindex, nofollow">\n'
           '<style>html,body{margin:0}[hidden]{display:none!important}</style>\n'
           + head.strip() + '\n</head>\n<body>\n<div id="tip"' + body + '\n</body>\n</html>\n')
    if re.search(r'<(link|img|iframe|script|object|embed|use)\b[^>]*\b(src|href)\s*=\s*"https?:', out):
        sys.exit("external resource found in Pages build")
    if re.search(r'\son[a-z]+\s*=', out.split('<script>')[0]):
        sys.exit("inline event handler found in Pages build")

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
open(OUT, 'w').write(out)
if PAGES:
    json.dump(data_out, open(os.path.join(os.path.dirname(os.path.abspath(OUT)), 'data.json'), 'w'), separators=(',', ':'))
    summary = dict(sym=SYM, name=NAME, title=TICK['title'], asof=asof, mode=MODE, spot=SPOT, chg_day=round((SPOT / PREV - 1) * 100, 2),
                   ch5=c5[SYM], n5=cx['n5'], iv30=float(ivh[30]), earn_next=run.get('earn_next'), earn_when=when if EN else None,
                   J=round(J * 100, 2) if SHOW else None, med45=float(r45['median']), p25_45=float(r45.p25), p75_45=float(r45.p75),
                   limited=bool(why), editions=len(history))
    json.dump(summary, open(os.path.join(os.path.dirname(os.path.abspath(OUT)), 'summary.json'), 'w'), separators=(',', ':'))
print(f"wrote {OUT} ({len(out):,} bytes) · asof {asof} · mode {MODE} · event {run.get('earn_next')} (priced: {HAS}) · editions {len(history)}")
print("  base:", base['date'] if base else None, "| week-ago:", wk['date'] if wk else None, "| J", round(J*100, 2), "| J_direct", round(Jd*100, 2) if np.isfinite(Jd) else None)
