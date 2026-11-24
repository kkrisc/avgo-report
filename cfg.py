# Shared run configuration. fetch.py writes run.json into the working directory;
# every other script imports its constants from here instead of hardcoding them.
import json, datetime as dt

_c = json.load(open('run.json'))
SYM    = _c.get('sym', 'AVGO')
import os as _os
CONF   = next((t for t in json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'tickers.json'))) if t['sym'] == SYM), {})
SPOT   = float(_c['spot'])                                  # underlying close used as "now"
PREV   = float(_c['prev'])                                  # prior session close
NOW    = dt.datetime.fromisoformat(_c['now'])               # ET timestamp of the snapshot
RF     = float(_c.get('rf', 0.04122))                       # risk-free rate (cont.)
DIV    = float(_c.get('div', 0.0075))                       # dividend yield
EARN_OPEN = dt.datetime.fromisoformat(_c['earn_open']) if _c.get('earn_open') else None   # first session trading on the next report
EARN_NEXT = _c.get('earn_next')                              # ISO date of the next report, or None
EARN_TIMING = _c.get('earn_timing')                          # 'amc' (after close) or 'bmo'
EARN_PAST = _c.get('earn_past', [])                          # [[iso_date, timing], ...] oldest first
LOW52  = float(_c.get('low52', 289.77))
HIGH52 = float(_c.get('high52', 495.0))
PRICE_MODE = _c.get('price_mode', 'mid')                    # 'mid' (live bid/ask) or 'last' (adjusted last trade)
