#!/usr/bin/env python3
"""Toza Gilam CRM: dostavchik Zakazlar ekrani faqat ikki bo'limdan iborat bo'ladi:
  - "Olinishi kerak" (olinadigan zakazlar)
  - "Yetkazilishi kerak" (qadoqlangan, yetkazib beriladigan zakazlar, soni bilan)
Dostavchida holat kartalari, qidiruv, Marshrut, Kechikkan va Bekor qilingan tugmalari yashiriladi.
Rahbar va boshqa xodimlarning ekrani o'zgarmaydi.
Ishga tushirish (serverda, root):  python3 install-courier-view.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski faylni qaytaradi.
"""
import os, shutil, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))
MARK = '/* courier-view v1 */'

PATCHES = [
    # 1) dostavchi uchun faqat ikkita tugma, boshlang'ich filtr - "Olinishi kerak"
    ("chips.push(['cancelled',ST.cancelled]);if(isAdmin()||S.me.role==='courier')"
     "chips.unshift(['pickup','Olinishi kerak'],['route','Marshrut'],['late','Kechikkan']);",
     "chips.push(['cancelled',ST.cancelled]);if(isAdmin()||S.me.role==='courier')"
     "chips.unshift(['pickup','Olinishi kerak'],['route','Marshrut'],['late','Kechikkan']);\n    "
     + MARK + "const onlyCourier=S.me.role==='courier'&&!isAdmin();"
     "if(onlyCourier){chips.length=0;chips.push(['pickup','Olinishi kerak'],['queue','Yetkazilishi kerak']);"
     "if(S.filter!=='pickup'&&S.filter!=='queue')S.filter='pickup'}"),
    # 2) holat kartalari yashiriladi
    ('<div class="otiles" id="otiles">',
     '<div class="otiles" id="otiles"${onlyCourier?\' style="display:none"\':\'\'}>'),
    # 3) qidiruv yashiriladi
    ('<input id="oq" type="search" placeholder="Mijoz, telefon yoki zakaz raqami"',
     '<input id="oq" type="search"${onlyCourier?\' style="display:none"\':\'\'} placeholder="Mijoz, telefon yoki zakaz raqami"'),
    # 4) "Yetkazilishi kerak" soni
    ("function renderBody(){const b=$('#body');if(!b)return;",
     "function renderBody(){const b=$('#body');if(!b)return;\n"
     "  if(S.me.role==='courier'){const qc=document.querySelector('#chips [data-f=\"queue\"]');"
     "if(qc)qc.textContent='Yetkazilishi kerak · '+S.orders.filter(o=>o.status==='packed').length}"),
]


def main():
    hp = os.path.join(D, 'index.html')
    h = open(hp, encoding='utf-8').read()
    if MARK in h:
        sys.exit("Allaqachon o'rnatilgan - hech narsa o'zgarmadi.")
    new_h = h
    for old, new in PATCHES:
        n = new_h.count(old)
        if n != 1:
            sys.exit("Mos kelmadi (index.html: %r %d ta) - hech narsa o'zgarmadi." % (old[:50], n))
        new_h = new_h.replace(old, new)

    stamp = time.strftime('%m%d-%H%M%S')
    shutil.copy2(hp, hp + '.bak-' + stamp)
    open(hp, 'w', encoding='utf-8').write(new_h)
    if TEST:
        print('TEST: fayl yozildi.')
        return

    def healthy():
        subprocess.run(['systemctl', 'restart', 'gilam-crm'])
        for _ in range(12):
            time.sleep(1)
            try:
                if urllib.request.urlopen('http://127.0.0.1:%s/api/me' % PORT, timeout=5).status == 200:
                    return True
            except Exception:
                pass
        return False

    if healthy():
        print("Tayyor: dostavchi ekrani yangilandi. CRM sahifasini yangilang.")
    else:
        shutil.copy2(hp + '.bak-' + stamp, hp)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayl qaytarildi.")


main()
