#!/usr/bin/env python3
"""Toza Gilam CRM: yuvuvchi (washer) Zakazlar ekrani soddalashadi:
  - faqat yuvilmagan zakazlar (yangi va yuvilayotgan) ko'rinadi
  - har bir zakaz kartasida tugma: "Yuvishga olish" (yangi), "Yuvildi" (yuvilayotgan)
  - holat kartalari, qidiruv va "Bekor qilindi" tugmasi yashiriladi
Rahbar va boshqa xodimlarning ekrani o'zgarmaydi.
Ishga tushirish (serverda, root):  python3 install-washer-view.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski faylni qaytaradi.
"""
import os, re, shutil, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))
MARK = '/* washer-view v1 */'

CHIPS_ANCHOR = "chips.unshift(['pickup','Olinishi kerak'],['route','Marshrut'],['late','Kechikkan']);"
BODY_ANCHOR = "function renderBody(){const b=$('#body');if(!b)return;"
NEXT_ANCHOR = "function nextActions(o){"
CARD_RE = re.compile(r"(\$\{fullDate\(o\.createdAt\)\}[^`]*?)</div></button>")

QUICK_JS = MARK + r'''
function quickBtn(o){
  if(S.me.role!=='washer'||isPick(o))return '';
  const a=nextActions(o)[0];if(!a)return '';
  return '<span role="button" class="btn pri" data-quick="'+a[0]+'" data-id="'+esc(o.id)+'" style="display:block;text-align:center;margin-top:10px">'+a[1]+'</span>';
}
document.addEventListener('click',e=>{
  const q=e.target&&e.target.closest?e.target.closest('[data-quick]'):null;if(!q)return;
  e.stopImmediatePropagation();e.preventDefault();
  openOrder(q.dataset.id);
  const b=document.querySelector('[data-act="status"][data-st="'+q.dataset.quick+'"]');
  if(b)b.click();
},true);
'''


def main():
    hp = os.path.join(D, 'index.html')
    h = open(hp, encoding='utf-8').read()
    if MARK in h:
        sys.exit("Allaqachon o'rnatilgan - hech narsa o'zgarmadi.")
    for pat in (CHIPS_ANCHOR, BODY_ANCHOR, NEXT_ANCHOR):
        n = h.count(pat)
        if n != 1:
            sys.exit("Mos kelmadi (index.html: %r %d ta) - hech narsa o'zgarmadi." % (pat[:45], n))
    if len(CARD_RE.findall(h)) != 1:
        sys.exit("Mos kelmadi (zakaz kartasi: %d ta) - hech narsa o'zgarmadi." % len(CARD_RE.findall(h)))

    new_h = h.replace(CHIPS_ANCHOR, CHIPS_ANCHOR + "\n    " + MARK +
                      "if(S.me.role==='washer'){chips.length=0;chips.push(['queue','Yuvilmagan zakazlar']);"
                      "if(S.filter!=='queue')S.filter='queue'}")
    new_h = new_h.replace(BODY_ANCHOR, BODY_ANCHOR +
                          "\n  if(S.me.role==='washer'){['otiles','oq'].forEach(i=>{const e=document.getElementById(i);"
                          "if(e)e.style.display='none'});"
                          "const qc=document.querySelector('#chips [data-f=\"queue\"]');"
                          "if(qc)qc.textContent='Yuvilmagan zakazlar · '+"
                          "S.orders.filter(o=>(o.status==='new'||o.status==='washing')&&!isPick(o)).length}")
    new_h = new_h.replace(NEXT_ANCHOR, QUICK_JS.lstrip('\n') + NEXT_ANCHOR)
    new_h = CARD_RE.sub(lambda m: m.group(1) + "</div>${quickBtn(o)}</button>", new_h, count=1)

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
        print("Tayyor: yuvuvchi ekrani yangilandi. CRM sahifasini yangilang.")
    else:
        shutil.copy2(hp + '.bak-' + stamp, hp)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayl qaytarildi.")


main()
