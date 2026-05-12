#!/usr/bin/env python3
"""Student Cribs Timesheet Dashboard — Daily Generator"""
import os, json, xml.etree.ElementTree as ET, urllib.request, sys
from datetime import date, timedelta
from collections import defaultdict

AUTH = os.environ.get('SC_API_AUTH', '')
if not AUTH:
    print("ERROR: SC_API_AUTH not set", file=sys.stderr)
    sys.exit(1)

BASE = "https://api.student-cribs.com/api/xmls/timesheet-issues"

def fetch(d_from, d_to):
    url = f"{BASE}?auth={AUTH}&date_from={d_from}&date_to={d_to}"
    print(f"  Fetching {d_from} -> {d_to}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={'User-Agent': 'SC-Dashboard/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            content = r.read()
        root = ET.fromstring(content)
        return root.findall('.//timesheet_issue')
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return []

CATS = [
    (['fire alarm', 'testing'], 'Fire Alarms'),
    (['weekly check'], 'Weekly Checks'),
    (['monthly check'], 'Monthly Checks'),
    (['fra', 'remedial'], 'FRA Remedials'),
    (['plumbing'], 'Plumbing'),
    (['electrical'], 'Electrical'),
    (['appliance'], 'Appliances'),
    (['internal finish'], 'Internal Finishes'),
    (['internal fixture', 'fitting'], 'Internal Fixtures'),
    (['elevation', 'window', 'door'], 'Elevations / Doors'),
    (['external'], 'External Areas'),
    (['wifi', 'wi-fi', 'router', 'service'], 'Services'),
    (['compliance'], 'Compliance'),
]

def cat_label(raw):
    if not raw: return 'Other'
    c = raw.lower()
    for keys, lbl in CATS:
        if any(k in c for k in keys): return lbl
    return 'Other'

def agg(issues):
    cities, engs, cats = defaultdict(int), defaultdict(int), defaultdict(int)
    urg = {'Emergency': 0, 'Urgent': 0, 'Non Urgent': 0, 'No Priority': 0, 'PPM': 0}
    emergencies = []
    months = defaultdict(int)
    for iss in issues:
        city = (iss.findtext('city_name') or '').strip()
        if city: cities[city] += 1
        u = (iss.findtext('urgency') or '').strip()
        if u in urg: urg[u] += 1
        else: urg['No Priority'] += 1
        e = (iss.findtext('completed_by_name') or '').strip()
        if e: engs[e] += 1
        cats[cat_label(iss.findtext('issue_category'))] += 1
        sched = (iss.findtext('scheduled_at') or '').strip()
        if len(sched) >= 7:
            months[sched[:7]] += 1
        if u == 'Emergency':
            emergencies.append({
                'address': (iss.findtext('property_address_name') or '').strip(),
                'city': city,
                'notes': (iss.findtext('issue_completion_notes') or '').strip()[:80]
            })
    return {
        'total': len(issues),
        'urgency': urg,
        'cities': sorted(cities.items(), key=lambda x: -x[1])[:15],
        'engineers': sorted(engs.items(), key=lambda x: -x[1])[:20],
        'categories': sorted(cats.items(), key=lambda x: -x[1]),
        'emergencies': emergencies[:15],
        'months': dict(sorted(months.items()))
    }

def fmt(d):
    return f"{d.day} {d.strftime('%b %Y')}"

today = date.today()
week_start = today - timedelta(days=7)
month_start = today.replace(day=1)
ytd_start = date(today.year if today.month >= 7 else today.year - 1, 7, 1)

print("Fetching weekly data...", file=sys.stderr)
weekly = agg(fetch(week_start, today))
print("Fetching monthly data...", file=sys.stderr)
monthly = agg(fetch(month_start, today))
print("Fetching YTD data...", file=sys.stderr)
ytd = agg(fetch(ytd_start, today))

meta = {
    'generated': today.strftime('%d %b %Y'),
    'week': f"{fmt(week_start)} – {fmt(today)}",
    'week_upper': f"{fmt(week_start)} – {fmt(today)}".upper(),
    'month': today.strftime('%B %Y'),
    'ytd_label': f"1 Jul {ytd_start.year} – {fmt(today)}",
    'ytd_from_year': ytd_start.year,
}

data_js = f"""const WEEKLY = {json.dumps(weekly)};
const MONTHLY = {json.dumps(monthly)};
const YTD = {json.dumps(ytd)};
const META = {json.dumps(meta)};"""

script_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(script_dir, 'template.html'), 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('// <!--INJECT_DATA-->', data_js)

with open(os.path.join(script_dir, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Done. weekly={weekly['total']} monthly={monthly['total']} ytd={ytd['total']}", file=sys.stderr)
