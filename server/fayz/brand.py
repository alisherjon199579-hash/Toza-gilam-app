#!/usr/bin/env python3
"""Fayz Gilam: bot/CRM matnlarini Fayzga almashtiradi. FAQAT /opt/fayz-crm ichida ishlaydi.
Ishga tushirish (root): python3 brand.py"""
import os, re, sys, shutil, time, subprocess
D = os.environ.get('FAYZ_DIR', '/opt/fayz-crm')
TEST = os.environ.get('FAYZ_TEST')
if 'gilam-crm' in D:
    sys.exit('Bu skript faqat Fayz uchun!')
FILES = ['bot.py', 'tgbot.py', 'reports.py', 'server.py', 'index.html']
REPL = [
 ('Toza Gilam', 'Fayz Gilam'),
 ('toza-gilam-baza', 'fayz-gilam-baza'),
 ('93 841 89 00', '91 240 97 01, 94 892 97 01'),
 ('08:00-21:00', '09:00-20:00'),
 ('8:00-12:00', '9:00-12:00'),
 ('17:00-21:00', '17:00-20:00'),
 ('https://www.instagram.com/gilam_yuvish_korxonasii', 'https://www.instagram.com/fayz_gilam_yuvish'),
]
stamp = time.strftime('%m%d-%H%M%S')
changed = {}
for f in FILES:
    p = os.path.join(D, f)
    if not os.path.exists(p): continue
    s = open(p, encoding='utf-8').read(); o = s
    for a, b in REPL: s = s.replace(a, b)
    if s != o:
        shutil.copy2(p, p + '.bak-brand-' + stamp)
        open(p, 'w', encoding='utf-8').write(s); changed[f] = p
print('O\'zgargan fayllar:', list(changed))
ok = True
for f, p in changed.items():
    if f.endswith('.py') and subprocess.call([sys.executable, '-m', 'py_compile', p]) != 0: ok = False
if not ok:
    for f, p in changed.items(): shutil.copy2(p + '.bak-brand-' + stamp, p)
    sys.exit('Xato: py_compile. Hammasi qaytarildi.')
if not TEST:
    subprocess.call(['systemctl', 'restart', 'fayz-crm']); time.sleep(3)
    if subprocess.call(['systemctl', 'is-active', '--quiet', 'fayz-crm']) != 0:
        for f, p in changed.items(): shutil.copy2(p + '.bak-brand-' + stamp, p)
        subprocess.call(['systemctl', 'restart', 'fayz-crm']); sys.exit('Ishga tushmadi. Qaytarildi.')
    print('fayz-crm: active')
print('--- Qolgan "toza" so\'zlari (kerak bo\'lsa ko\'rib chiqamiz):')
n = 0
for f in FILES:
    p = os.path.join(D, f)
    if not os.path.exists(p): continue
    for i, l in enumerate(open(p, encoding='utf-8'), 1):
        if re.search(r'toza|gilam_yuvish_korx|93 ?841', l, re.I):
            print('%s:%d: %s' % (f, i, l.strip()[:110])); n += 1
            if n >= 25: sys.exit(0)
