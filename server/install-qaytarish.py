#!/usr/bin/env python3
"""Toza Gilam CRM: bekor qilingan zakazni qaytarish tugmasi.

Nima qo'shadi:
  - Bekor qilingan zakaz oynasida (rahbar uchun) "Qaytarish" tugmasi chiqadi.
  - Tugma zakazni bekor qilinishidan oldingi holatiga qaytaradi
    (zakaz tarixidan olinadi; topilmasa - birinchi holat).
  - Holat o'zgarishi oddiy "status" tugmalari orqali o'tadi, shuning uchun tarix va
    bildirishnomalar avvalgidek ishlaydi.

Ishga tushirish (serverda, root):  python3 install-qaytarish.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski faylni qaytaradi.
"""
import os, shutil, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))

FUNC = ("/* qaytarish-v1 */\n"
        "function _prevSt(o){const l=(o.log||[]).slice().reverse().find(x=>x.st&&x.st!=='cancelled'&&ST[x.st]);"
        "return l?l.st:Object.keys(ST).filter(k=>k!=='cancelled')[0]}\n")

BTN_OLD = ("isAdmin()&&o.status!=='cancelled'&&o.status!=='delivered'?"
           "`<button class=\"btn bad\" data-act=\"status\" data-st=\"cancelled\">Bekor qilish</button>`:'',")
BTN_NEW = ("isAdmin()&&o.status==='cancelled'?"
           "`<button class=\"btn pri grow\" data-act=\"status\" data-st=\"${_prevSt(o)}\">↩ Qaytarish</button>`:'',\n    "
           + BTN_OLD)

# (eski matn, yangi matn) - har biri index.html'da aynan 1 marta bo'lishi shart
EDITS = [
    ("function openOrder(id){", FUNC + "function openOrder(id){"),
    (BTN_OLD, BTN_NEW),
]


def main():
    hp = os.path.join(D, 'index.html')
    h = open(hp, encoding='utf-8').read()
    if '/* qaytarish-v1' in h:
        sys.exit("Allaqachon o'rnatilgan - hech narsa o'zgarmadi.")
    new_h = h
    for old, new in EDITS:
        n = new_h.count(old)
        if n != 1:
            sys.exit("Mos kelmadi (%r: %d ta) - hech narsa o'zgarmadi." % (old[:50], n))
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
        print("Tayyor: bekor qilingan zakazda 'Qaytarish' tugmasi paydo bo'ldi. CRM sahifasini yangilang.")
    else:
        shutil.copy2(hp + '.bak-' + stamp, hp)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayl qaytarildi.")


main()
