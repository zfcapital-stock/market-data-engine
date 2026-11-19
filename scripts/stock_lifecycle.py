"""Company-wide lifecycle; screening predicates remain untouched."""
from collections import defaultdict

ABSENCE_RESET_DAYS = 20

def classify_results(results, trading_dates, reset_days=ABSENCE_RESET_DAYS):
    """Annotate hits and emit absence days 1..20 (day 20 = expired).

    Dates are market-specific sessions, ascending. Volume-only hits do not
    count. Unknown initial history is never represented as a confirmed new hit.
    Each input row stays separate, including VCP and sanxian on the same day.
    """
    by_date = defaultdict(list)
    for row in results:
        by_date[row['d']].append(row)
    dates = sorted(set(trading_dates) | set(by_date))
    last = {}
    absent = []
    for pos, day in enumerate(dates):
        hits = defaultdict(list)
        for row in by_date[day]:
            if row['t'] == 'sx' or (row['t'] == 'vcp' and (row.get('s') or row.get('h'))):
                hits[row['id']].append(row)
        for sid, rows in hits.items():
            previous = last.get(sid)
            gap = pos - previous[0] - 1 if previous else None
            state = ('old' if gap == 0 else 'return' if gap is not None and gap < reset_days
                     else 'new' if gap is not None or pos >= reset_days else 'unknown')
            for row in rows:
                row['lc'] = state
                if state == 'return': row['gap'] = gap
            last[sid] = (pos, rows[0])
        for sid, (seen, info) in list(last.items()):
            if sid in hits: continue
            gap = pos - seen
            if gap <= reset_days:
                absent.append({'d': day, 'id': sid, 'm': info['m'], 'n': info['n'],
                               'i': info['i'], 't': 'absent',
                               'lc': 'expired' if gap == reset_days else 'missing', 'gap': gap})
            if gap >= reset_days: del last[sid]
    return absent
