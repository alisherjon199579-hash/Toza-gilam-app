#!/usr/bin/env python3
"""Toza Gilam CRM: zakazga qo'lda chegirma (skidka) foizi.

Nima qo'shadi:
  - Zakaz oynasida (yangi zakaz va tahrirlash) "Chegirma, %" maydoni va 5/10/15/20% tugmalari.
    Dostavchik ham, rahbar ham kirita oladi. Dostavchik uchun eng ko'pi CG_MAX_COURIER (30%),
    rahbar uchun 100%.
  - "Jami" summa chegirma bilan o'zi kamayadi; qarz, kirim va hisobotlar shu summadan hisoblanadi.
  - Zakaz kartasida va tafsilotida "Chegirma -10%" ko'rinadi (qaytish bonusi esa "Bonus").
  - Chegirma kiritilsa, qaytish bonusi o'rniga shu qo'llanadi; bo'sh qoldirilsa, bonus avvalgidek ishlaydi.

Ishga tushirish (serverda, root):  python3 install-chegirma.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski faylni qaytaradi.
"""
import os, shutil, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))
CG_MAX_COURIER = int(os.environ.get('CG_MAX_COURIER', '30'))

BLOCK = r'''/* chegirma-v1: zakazga qo'lda chegirma foizi */
const CG_MAX_COURIER=__MAXC__;
function _cgMax(){try{return isAdmin()?100:CG_MAX_COURIER}catch(e){return CG_MAX_COURIER}}
function _cgPct(){const e=document.getElementById('of-cg');if(!e)return null;
  const v=parseFloat(String(e.value).replace(',','.'));if(!(v>0))return null;return Math.min(v,_cgMax())}
function _cgNote(){const n=document.getElementById('of-cgnote');if(!n)return;const p=_cgPct();
  if(p===null){n.hidden=true;return}
  const s=calcItems().reduce((a,i)=>a+i.sum,0),d=s-applyDisc(s,p);
  n.hidden=false;n.textContent='Chegirma '+p+'%: −'+money(d)}
function _cgInject(){
  const sv=document.getElementById('of-save'),foot=sv&&sv.parentNode;if(!foot||document.getElementById('of-cg'))return;
  let pre='';try{const eo=(typeof F!=='undefined'&&F&&F.id)?S.orders.find(x=>x.id===F.id):null;if(eo&&eo.discM&&eo.disc)pre=String(eo.disc)}catch(e){}
  const row=document.createElement('div');
  row.style.cssText='display:flex;align-items:center;gap:6px;padding:8px 16px;border-top:1px solid var(--line,#e1e8ec);background:var(--card,#fff)';
  const chip='border:1px solid var(--line,#d3dde2);background:transparent;border-radius:10px;padding:8px 9px;font:600 13px system-ui,sans-serif;color:inherit';
  row.innerHTML='<span style="font-weight:600;font-size:14px;white-space:nowrap">Chegirma</span>'+
    '<input id="of-cg" type="number" inputmode="decimal" min="0" max="100" step="any" placeholder="0" value="'+pre+'" '+
    'style="width:62px;border:1px solid var(--line,#d3dde2);border-radius:10px;padding:8px;font-size:16px;text-align:center;background:transparent;color:inherit">'+
    '<span style="font-weight:600">%</span>'+
    [5,10,15,20].map(function(p){return '<button type="button" data-cg="'+p+'" style="'+chip+'">'+p+'</button>'}).join('')+
    '<button type="button" data-cg="0" style="'+chip+';margin-left:auto" aria-label="Chegirmani olib tashlash">×</button>';
  foot.parentNode.insertBefore(row,foot);
  const tot=document.getElementById('of-total'),holder=tot&&tot.parentNode;
  if(holder&&!document.getElementById('of-cgnote')){const n=document.createElement('div');n.className='meta';n.id='of-cgnote';n.hidden=true;holder.appendChild(n)}
  const inp=row.querySelector('#of-cg');
  inp.addEventListener('input',function(){updTotal()});
  inp.addEventListener('change',function(){const v=parseFloat(String(inp.value).replace(',','.'));
    if(v>_cgMax())inp.value=String(_cgMax());updTotal()});
  row.addEventListener('click',function(ev){const b=ev.target.closest&&ev.target.closest('button[data-cg]');if(!b)return;
    const p=Math.min(parseFloat(b.getAttribute('data-cg')),_cgMax());inp.value=p>0?String(p):'';updTotal()});
}
const _cgSS=showSheet;showSheet=function(kind,title,body,foot){const r=_cgSS.apply(this,arguments);
  if(kind==='oform'){try{_cgInject()}catch(e){}}return r};
const _cgUT=updTotal;updTotal=function(){const r=_cgUT.apply(this,arguments);try{_cgNote()}catch(e){}return r};
'''

# (eski matn, yangi matn) - har biri index.html'da aynan 1 marta bo'lishi shart
EDITS = [
    ("function bonPct(){",
     "function bonPct(){const _m=_cgPct();if(_m!==null)return _m;return _bonPct0()}\nfunction _bonPct0(){"),
    ("...(dpc?{disc:dpc,discSum:sum0-total}:{})",
     "...(dpc?{disc:dpc,discSum:sum0-total,...(_cgPct()!==null?{discM:1}:{})}:{})"),
    ("a:'Qaytish bonusi',b:'-'+o.disc+'%'",
     "a:(o.discM?'Chegirma':'Qaytish bonusi'),b:'-'+o.disc+'%'"),
    (">Bonus -${o.disc}%</span>",
     ">${o.discM?'Chegirma':'Bonus'} -${o.disc}%</span>"),
    ("const _ocB=orderCard;",
     "@@BLOCK@@const _ocB=orderCard;"),
]


def main():
    hp = os.path.join(D, 'index.html')
    h = open(hp, encoding='utf-8').read()
    if '/* chegirma-v1' in h:
        sys.exit("Allaqachon o'rnatilgan - hech narsa o'zgarmadi.")
    new_h = h
    for old, new in EDITS:
        n = new_h.count(old)
        if n == 0 and old.startswith('>Bonus'):
            # kutilmagan belgi (probel/minus) bo'lsa - moslashuvchan qidiruv
            import re
            rx = re.compile(r">\s*Bonus\W{0,4}\$\{o\.disc\}\s*%\s*</span>")
            ms = rx.findall(new_h)
            if len(ms) == 1:
                new_h = new_h.replace(ms[0], new)
                continue
            i = new_h.find('Bonus')
            while i != -1 and 'o.disc' not in new_h[i:i+30]:
                i = new_h.find('Bonus', i + 1)
            print('Eslatma: kartadagi "Bonus" yorlig\'i topilmadi, o\'zgartirilmadi:', repr(new_h[max(0,i-20):i+50]) if i != -1 else '-')
            continue
        if n != 1 and not (n == 0 and old.startswith('>Bonus')):
            sys.exit("Mos kelmadi (%r: %d ta) - hech narsa o'zgarmadi." % (old[:40], n))
        if new.startswith('@@BLOCK@@'):
            new = BLOCK.replace('__MAXC__', str(CG_MAX_COURIER)) + new[len('@@BLOCK@@'):]
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
        print("Tayyor: zakaz oynasida 'Chegirma, %' maydoni paydo bo'ldi. CRM sahifasini yangilang.")
    else:
        shutil.copy2(hp + '.bak-' + stamp, hp)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayl qaytarildi.")


main()
