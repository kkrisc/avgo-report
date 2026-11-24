# Earnings calendar helpers shared by the pipeline scripts.
import datetime as dt
import pandas as pd

# Fallback list of past reports (all after the close). fetch.py adds anything newer from Yahoo.
BASE_PAST = ["2019-06-13", "2019-09-12", "2019-12-12", "2020-06-04", "2020-09-03", "2020-12-10", "2021-03-04",
             "2021-06-03", "2021-09-02", "2021-12-09", "2022-03-03", "2022-09-01", "2022-12-08", "2023-03-02",
             "2023-06-01", "2023-08-31", "2023-12-07", "2024-03-07", "2024-06-12", "2024-09-05", "2024-12-12",
             "2025-03-06", "2025-06-05", "2025-09-04", "2025-12-11", "2026-03-04", "2026-06-03", "2026-09-02"]

# NYSE full-day closures, used only to find the first session after a report.
HOLIDAYS = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
            "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24", "2028-01-17", "2028-02-21",
            "2028-04-14", "2028-05-29", "2028-06-19", "2028-07-04", "2028-09-04", "2028-11-23", "2028-12-25"}


def next_session(d: dt.date) -> dt.date:
    d += dt.timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in HOLIDAYS:
        d += dt.timedelta(days=1)
    return d


def reaction_open(date: dt.date, timing: str) -> dt.datetime:
    """09:30 ET of the first session that trades on the news."""
    day = date if timing == "bmo" else next_session(date)
    return dt.datetime.combine(day, dt.time(9, 30))


def reactions(px: pd.Series, past):
    """[(report_date, next-session % move)] oldest first, for [[iso_date, timing], ...]."""
    out = []
    for iso, timing in past:
        d = pd.Timestamp(iso)
        idx = px.index[px.index >= d] if timing == "bmo" else px.index[px.index > d]
        if not len(idx):
            continue
        j = px.index.get_loc(idx[0])
        if j == 0:
            continue
        out.append((d, (float(px.iloc[j]) / float(px.iloc[j - 1]) - 1) * 100))
    return sorted(out)
