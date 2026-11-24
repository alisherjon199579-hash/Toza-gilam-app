#!/usr/bin/env python3
"""Toza Gilam CRM: zakaz tuzilmasini ko'rish (faqat o'qiydi, hech narsani o'zgartirmaydi).
Mijoz ismi, telefoni, manzili chiqarilmaydi - faqat maydon nomlari va holatlar."""
import os, re, json, sqlite3, collections
D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
DATA = os.environ.get('CRM_DATA', '/var/lib/gilam-crm')
c = sqlite3.connect('file:%s?mode=ro' % os.path.join(DATA, 'crm.db'), uri=True)
print('== Jadvallar (coll: soni)')
colls = c.execute("SELECT coll,count(*) FROM docs GROUP BY coll").fetchall()
for k, n in colls:
    print(' ', k, n)
SAFE = re.compile(r'^(status|st|state|paid|pay|total|sum|disc|discM|delivery|num|id|type|kind|done|at|t|ts|ready)$', re.I)
for k, n in colls:
    if not re.search(r'order|zakaz|ord', k or '', re.I):
        continue
    print('\n== %s: maydonlar' % k)
    keys = collections.OrderedDict()
    stat = collections.Counter()
    sample = None
    for (d,) in c.execute("SELECT data FROM docs WHERE coll=?", (k,)):
        try:
            o = json.loads(d)
        except Exception:
            continue
        if sample is None:
            sample = o
        for kk, vv in o.items():
            keys[kk] = type(vv).__name__
        for sk in ('status', 'st', 'state'):
            if sk in o:
                stat[(sk, str(o[sk]))] += 1
    print(' ', ', '.join('%s:%s' % kv for kv in keys.items()))
    print('  holatlar:', dict(stat))
    if sample:
        print('  namuna (xavfsiz maydonlar):', {a: b for a, b in sample.items() if SAFE.match(a) and not isinstance(b, (dict, list))})
        for a, b in sample.items():
            if isinstance(b, list) and b and isinstance(b[0], dict):
                print('  ro\'yxat "%s" elementi maydonlari:' % a, list(b[0].keys()))
            if isinstance(b, dict):
                print('  ichki "%s" maydonlari:' % a, list(b.keys()))
print('\n== server.py: yetkaz/deliver/status qatorlari')
try:
    for i, l in enumerate(open(os.path.join(D, 'server.py'), encoding='utf-8'), 1):
        if re.search(r"yetkaz|deliver|'/api/|\"/api/", l, re.I) and len(l) < 200:
            print(' ', i, l.rstrip())
except Exception as e:
    print('  server.py:', e)
print('\n== index.html: Yetkazildi atrofi')
try:
    t = open(os.path.join(D, 'index.html'), encoding='utf-8').read()
    for m in list(re.finditer(r'Yetkazildi', t))[:6]:
        s = t[max(0, m.start() - 160):m.end() + 160].replace('\n', ' ')
        print('  ...', s, '...')
except Exception as e:
    print('  index.html:', e)
