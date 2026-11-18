#!/usr/bin/env python3
"""Fayz Gilam CRM: narxlarni (services) qo'shadi. root bilan: python3 add-prices.py
Fayz xizmatini to'xtatadi, yozadi, qayta ishga tushiradi. Qayta ishga tushirish xavfsiz."""
import sqlite3, json, os, subprocess, sys
FAYZ = '/var/lib/fayz-crm/crm.db'
TOZA = '/var/lib/gilam-crm/crm.db'
# (id, nomi, narx, birlik)
ITEMS = [
 ('gilam',        'Gilam',            12000, 'm2'),
 ('korpacha-2m',  "Ko'rpacha 2 m",    40000, 'dona'),
 ('korpacha-25m', "Ko'rpacha 2.5 m",  45000, 'dona'),
 ('korpacha-3m',  "Ko'rpacha 3 m",    50000, 'dona'),
 ('korpa',        "Ko'rpa",           60000, 'dona'),
 ('adyol',        'Adyol',            60000, 'dona'),
 ('yostiq',       'Yostiq',           20000, 'dona'),
 ('parda',        'Parda (metri)',    20000, 'm'),
]
if not os.path.exists(FAYZ):
    sys.exit('Fayz bazasi topilmadi: ' + FAYZ)
# Parda birligini Toza'dan olamiz (bo'lsa)
try:
    t = sqlite3.connect('file:%s?mode=ro' % TOZA, uri=True)
    for p, d in t.execute("select path,data from docs where coll='services'"):
        j = json.loads(d)
        if 'parda' in p.lower() or 'parda' in j.get('name', '').lower():
            ITEMS[-1] = ITEMS[-1][:3] + (j.get('unit', 'm'),)
            print('Parda birligi Toza dan:', j.get('unit'))
except Exception as e:
    print('Toza o\'qilmadi (muammo emas):', e)
subprocess.call(['systemctl', 'stop', 'fayz-crm'])
try:
    c = sqlite3.connect(FAYZ)
    mx = max(c.execute('select coalesce(max(ver),0) from docs').fetchone()[0],
             c.execute('select coalesce(max(ver),0) from tomb').fetchone()[0])
    meta = dict(c.execute('select k,v from meta').fetchall())
    print('meta kalitlari:', [k for k in meta if 'secret' not in k.lower() and 'code' not in k.lower() and 'pass' not in k.lower()])
    v = mx
    for i, (sid, name, price, unit) in enumerate(ITEMS, 1):
        v += 1
        path = 'services/' + sid
        data = json.dumps({'name': name, 'order': i, 'price': price, 'unit': unit}, ensure_ascii=False, separators=(',', ':'))
        c.execute('delete from tomb where path=?', (path,))
        c.execute('insert or replace into docs(path,coll,data,ver) values(?,?,?,?)', (path, 'services', data, v))
    for k in ('ver', 'version', 'seq', 'rev'):
        if k in meta:
            try:
                if int(meta[k]) < v:
                    c.execute('update meta set v=? where k=?', (str(v), k)); print('meta', k, '->', v)
            except ValueError:
                pass
    c.commit(); c.close()
finally:
    subprocess.call(['chown', '-R', 'fayzcrm', '/var/lib/fayz-crm'])
    subprocess.call(['systemctl', 'start', 'fayz-crm'])
c = sqlite3.connect('file:%s?mode=ro' % FAYZ, uri=True)
for p, d in c.execute("select path,data from docs where coll='services' order by ver"):
    print(p, d)
