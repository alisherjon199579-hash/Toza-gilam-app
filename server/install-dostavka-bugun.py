#!/usr/bin/env python3
"""Toza Gilam CRM: xodim oynasida dostavchining bugungi yetkazgan tushumi.

Nima qo'shadi:
  - Xodimlar bo'limida dostavchini bossangiz, oyna tepasida "Bugun yetkazgan (N ta)" va
    shu zakazlarning jami summasi chiqadi (bugun 00:00 dan boshlab, "Yetkazildi" bosilgan zakazlar).
  - Hisob oylik hisobot bilan bir xil manbadan olinadi, shuning uchun raqamlar mos tushadi.

Ishga tushirish (serverda, root):  python3 install-dostavka-bugun.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski faylni qaytaradi.
"""
import os, shutil, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))

FUNC = ("/* dostavka-bugun-v1 */\n"
        "function _stToday(x){try{if(!x||x.role!=='courier')return '';const d=new Date();d.setHours(0,0,0,0);"
        "const a=d.getTime(),s=staffMonth({ma:a,mb:a+86400000}).find(v=>v.x.id===x.id);if(!s)return '';"
        "return '<div class=\"card stack\" style=\"margin-bottom:10px\"><div class=\"row\"><span class=\"grow\">Bugun yetkazgan ('"
        "+s.w.delivered+' ta)</span><b class=\"sum\">'+money(s.rev)+'</b></div></div>'}catch(e){return ''}}\n")

NAME_OLD = '<label class="f">Ism<input id="sf-name"'
NAME_NEW = '${_stToday(x)}' + NAME_OLD

# (eski matn, yangi matn) - har biri index.html'da aynan 1 marta bo'lishi shart
EDITS = [
    ("function openStaffForm(id){", FUNC + "function openStaffForm(id){"),
    (NAME_OLD, NAME_NEW),
]


def main():
    hp = os.path.join(D, 'index.html')
    h = open(hp, encoding='utf-8').read()
    if '/* dostavka-bugun-v1' in h:
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
        print("Tayyor: dostavchi oynasida bugungi tushum paydo bo'ldi. CRM sahifasini yangilang.")
    else:
        shutil.copy2(hp + '.bak-' + stamp, hp)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayl qaytarildi.")


main()
