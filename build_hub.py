# Overview page linking every ticker report.  python build_hub.py <site_dir>
# Reads <site_dir>/<sym>/summary.json for each ticker in tickers.json. No script on this page.
import sys, os, json, html, datetime as dt

SITE = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
TICKERS = json.load(open(os.path.join(HERE, 'tickers.json')))
esc = html.escape
S = lambda x, d=1: f"{x:.{d}f}".replace('-', '−')
sgn = lambda x, d=1: ('+' if x > 0 else '') + S(x, d)
cls = lambda x: 'up' if x > 0 else 'dn' if x < 0 else ''

cards, asofs = [], []
for t in TICKERS:
    low = t['sym'].lower(); path = os.path.join(SITE, low, 'summary.json')
    if not os.path.exists(path):
        st = os.path.join(SITE, low, 'status.json')
        why = json.load(open(st)).get('reason', '') if os.path.exists(st) else ''
        why = why[:1].upper() + why[1:]
        cards.append(f'<div class="card off"><div class="top"><span class="sym">{t["sym"]}</span><span class="nm">{esc(t["name"])}</span></div>'
                     f'<p class="msg">No report yet. {esc(why)} The report starts on its own once a daily run succeeds.</p></div>')
        continue
    s = json.load(open(path)); asofs.append(s['asof'])
    ev = (f"{dt.date.fromisoformat(s['earn_next']).strftime('%-d %b')}" + (f" · priced ±{s['J']:.1f}%" if s.get('J') else "")) if s.get('earn_next') else "not announced"
    chips = ('<span class="chip warn">Read with care</span>' if s.get('limited') else '') + ('' if s['mode'] == 'mid' else '<span class="chip">Last-trade data</span>')
    cards.append(f'''<a class="card" href="{low}/index.html">
  <div class="top"><span class="sym">{s["sym"]}</span><span class="nm">{esc(s["name"])}</span>{chips}</div>
  <div class="px"><span class="v">{s["spot"]:,.2f}</span><span class="{cls(s["chg_day"])}">{sgn(s["chg_day"], 2)}%</span></div>
  <dl>
    <div><dt>{s["n5"]} sessions</dt><dd class="{cls(s["ch5"])}">{sgn(s["ch5"])}%</dd></div>
    <div><dt>30-day IV</dt><dd>{s["iv30"]:.1f}%</dd></div>
    <div><dt>45-day central</dt><dd>${s["med45"]:,.0f}</dd></div>
    <div><dt>45-day 50% band</dt><dd>${s["p25_45"]:,.0f}–{s["p75_45"]:,.0f}</dd></div>
    <div class="wide"><dt>Next earnings</dt><dd>{esc(ev)}</dd></div>
  </dl>
  <div class="go">Open the {esc(s["name"])} report →</div>
</a>''')

links = "".join(f'<a href="{t["sym"].lower()}/index.html">{t["sym"]}</a>' for t in TICKERS)
csp = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; object-src 'none'"
page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex, nofollow">
<title>Options Outlooks</title>
<style>
/* Layout: a single column of report cards that becomes a grid on wider screens. */
:root{{color-scheme:light;
  --paper:#E9EDF2;--surface:#FBFCFD;--surface-2:#F1F4F8;--ink:#121821;--ink-2:#3E4A5A;--muted:#6F7B87;--rule:#D2D9E2;--rule-soft:#E3E8EF;
  --accent:#A66A12;--accent-ink:#8A5710;--accent-wash:rgba(166,106,18,.10);--accent-line:rgba(166,106,18,.34);--teal:#0A8F78;--red:#D13F3E;
  --shadow:0 1px 2px rgba(18,24,33,.05),0 6px 20px -8px rgba(18,24,33,.10);
  --f-disp:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --f-body:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,"Helvetica Neue",Arial,sans-serif;
  --f-mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;
  --paper:#0D1117;--surface:#151B24;--surface-2:#1B222D;--ink:#E8EEF5;--ink-2:#A7B3C1;--muted:#7D8A97;--rule:#293441;--rule-soft:#202935;
  --accent:#C9882F;--accent-ink:#E3AC61;--accent-wash:rgba(201,136,47,.13);--accent-line:rgba(201,136,47,.40);--teal:#27A888;--red:#E66767;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -10px rgba(0,0,0,.6)}}}}
:root[data-theme="dark"]{{color-scheme:dark;
  --paper:#0D1117;--surface:#151B24;--surface-2:#1B222D;--ink:#E8EEF5;--ink-2:#A7B3C1;--muted:#7D8A97;--rule:#293441;--rule-soft:#202935;
  --accent:#C9882F;--accent-ink:#E3AC61;--accent-wash:rgba(201,136,47,.13);--accent-line:rgba(201,136,47,.40);--teal:#27A888;--red:#E66767;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -10px rgba(0,0,0,.6)}}
*{{box-sizing:border-box}}
html,body{{margin:0}}
body{{background:var(--paper);color:var(--ink);font-family:var(--f-body);font-size:15.5px;line-height:1.6;padding-block:0 64px;
     padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
.wrap{{max-width:1000px;margin:0 auto}}
.topnav{{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--rule);margin:0 calc(-1*max(16px,env(safe-area-inset-left,0px)));padding:0 max(16px,env(safe-area-inset-left,0px))}}
.navin{{max-width:1000px;margin:0 auto;display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;padding:8px 0}}
.navin a{{font-family:var(--f-mono);font-size:12px;letter-spacing:.06em;text-decoration:none;color:var(--ink-2);padding:6px 10px;border-radius:3px;white-space:nowrap;border:1px solid transparent}}
.navin a:hover{{background:var(--surface-2)}}
.navin a:focus-visible,.card:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.navin a.home{{font-family:var(--f-body);letter-spacing:0;color:var(--ink);font-weight:600}}
.navin a[aria-current="page"]{{color:var(--accent-ink);border-color:var(--accent-line);background:var(--accent-wash);font-weight:600}}
header{{padding:36px 0 6px}}
.eyebrow{{font-family:var(--f-mono);font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}}
h1{{font-family:var(--f-disp);font-weight:600;font-size:clamp(34px,5.5vw,52px);line-height:1.05;letter-spacing:-.02em;margin:12px 0 0}}
.lede{{font-size:16.5px;color:var(--ink-2);max-width:660px;margin:14px 0 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px;margin-top:28px}}
.card{{display:block;background:var(--surface);border:1px solid var(--rule);border-radius:5px;box-shadow:var(--shadow);padding:16px 18px;color:inherit;text-decoration:none;min-width:0}}
a.card:hover{{border-color:var(--accent-line)}}
.card.off{{opacity:.7}}
.top{{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}}
.sym{{font-family:var(--f-mono);font-size:13px;font-weight:600;letter-spacing:.06em;color:var(--accent-ink)}}
.nm{{font-family:var(--f-disp);font-size:20px;font-weight:600}}
.chip{{font-family:var(--f-mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border:1px solid var(--rule);border-radius:3px;padding:1px 6px}}
.chip.warn{{color:var(--accent-ink);border-color:var(--accent-line);background:var(--accent-wash)}}
.px{{display:flex;align-items:baseline;gap:10px;margin-top:8px;font-family:var(--f-mono);font-variant-numeric:tabular-nums}}
.px .v{{font-size:26px;font-weight:500;letter-spacing:-.02em}}
dl{{display:grid;grid-template-columns:1fr 1fr;gap:8px 14px;margin:12px 0 0}}
dl div{{min-width:0}} dl .wide{{grid-column:1/-1}}
dt{{font-family:var(--f-mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}}
dd{{margin:2px 0 0;font-family:var(--f-mono);font-variant-numeric:tabular-nums;font-size:14px}}
.go{{margin-top:14px;font-size:13px;color:var(--accent-ink);font-weight:600}}
.msg{{color:var(--muted);font-size:14px}}
.up{{color:var(--teal)}} .dn{{color:var(--red)}}
footer{{margin-top:48px;padding-top:18px;border-top:1px solid var(--rule);font-size:12.5px;color:var(--muted)}}
</style>
</head>
<body>
<nav class="topnav" aria-label="Reports"><div class="navin"><a class="home" href="index.html" aria-current="page">All reports</a>{links}</div></nav>
<div class="wrap">
<header>
  <div class="eyebrow">Options-implied analysis · refreshed each trading day</div>
  <h1>Options Outlooks</h1>
  <p class="lede">Each report reads a stock's full options chain and turns it into probability ranges at 7, 10, 20, 30 and 45 days, then adds the context around it: earnings, peers, positioning and, for the chip makers, AI spending by the largest buyers.</p>
</header>
<div class="grid">
{chr(10).join(cards)}
</div>
<footer>Latest data: {esc(max(asofs) if asofs else "none yet")}. Quantitative analysis, not investment advice. Options involve substantial risk of loss.</footer>
</div>
</body>
</html>
'''
open(os.path.join(SITE, 'index.html'), 'w').write(page)

# A short page for each ticker without a report, so its menu item never leads to a missing page.
head = page.split('<body>')[0]
for t in TICKERS:
    low = t['sym'].lower()
    if os.path.exists(os.path.join(SITE, low, 'summary.json')): continue
    os.makedirs(os.path.join(SITE, low), exist_ok=True)
    st = os.path.join(SITE, low, 'status.json')
    why = json.load(open(st)).get('reason', '') if os.path.exists(st) else ''
    why = why[:1].upper() + why[1:]
    sub = "".join(f'<a href="../{x["sym"].lower()}/index.html"' + (' aria-current="page"' if x['sym'] == t['sym'] else '') + f'>{x["sym"]}</a>' for x in TICKERS)
    open(os.path.join(SITE, low, 'index.html'), 'w').write(
        head.replace('<title>Options Outlooks</title>', f'<title>{esc(t["title"])}</title>')
        + f'<body>\n<nav class="topnav" aria-label="Reports"><div class="navin"><a class="home" href="../index.html">All reports</a>{sub}</div></nav>\n'
        + f'<div class="wrap"><header><div class="eyebrow">{t["sym"]} · {esc(t.get("legal", t["name"]))}</div><h1>{esc(t["title"])}</h1>'
        + f'<p class="lede">No report yet. {esc(why)} The daily run tries again each trading day, and this page is replaced as soon as one succeeds.</p></header></div>\n</body>\n</html>\n')
print(f"wrote overview page with {len(asofs)} of {len(TICKERS)} reports")
