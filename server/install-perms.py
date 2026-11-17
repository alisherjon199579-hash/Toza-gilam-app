#!/usr/bin/env python3
"""Toza Gilam CRM: xodimlarga ruxsatlar (galochkalar).
  - Xodimlar bo'limida xodimni bossangiz, "Xodimni tahrirlash" oynasida "Ruxsatlar" ro'yxati chiqadi
  - Rahbar har bir ruxsatni yoqadi yoki o'chiradi, server har so'rovda shuni tekshiradi
  - Galochka bosilmagan xodimda hozirgi tartib o'zgarmaydi (rolga qarab)
  - Dostavchikka "olib ketish" va "yetkazildi" avvaldan ochiq
Ishga tushirish (serverda, root):  python3 install-perms.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski fayllarni qaytaradi.
"""
import os, re, shutil, subprocess, sys, time, py_compile, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))

M_BEGIN = '# ---- ruxsatlar (perms) v1 ----\n'
M_END = '# ---- /ruxsatlar (perms) ----\n'

FUNC = M_BEGIN + r'''
PERM_DEFAULT = {
    'courier': ('order_new', 'order_pickup', 'deliver', 'client_add', 'loc_send'),
    'washer': ('wash_start', 'wash_done'),
    'packer': ('pack',),
}
PERM_TRANS = {('new', 'washing'): 'wash_start', ('washing', 'washed'): 'wash_done',
              ('washed', 'packed'): 'pack', ('packed', 'delivered'): 'deliver'}


def _perm_val(me, role, key):
    """Xodimda shu ruxsat aniq belgilangan bo'lsa - o'sha, aks holda rolning odatiy qiymati."""
    try:
        p = (staff_all().get(me) or {}).get('perms')
    except Exception:
        p = None
    if isinstance(p, dict) and key in p:
        return bool(p[key])
    return key in PERM_DEFAULT.get(role, ())


def _perm_action(me, role, op, path, data, old):
    """Yozuv qaysi ruxsatga to'g'ri kelishini aniqlaydi (None - eski qoida hal qiladi)."""
    coll, _, did = path.partition('/')
    data = data if isinstance(data, dict) else {}
    if coll == 'orders':
        if op == 'set' and old is None:
            return 'order_new'
        if op == 'delete':
            return 'order_delete'
        if op == 'update' and old is not None:
            if old.get('pickup') is True and old.get('status') == 'new' and data.get('status', 'new') == 'new':
                return 'order_pickup'
            if 'status' in data:
                return PERM_TRANS.get((old.get('status'), data['status'])) or 'order_edit'
            if set(data) <= ORDER_KEYS.get(role, set()):
                return None
            return 'order_edit'
        return None
    if coll == 'clients':
        return 'client_add' if op == 'set' else 'client_edit'
    if coll == 'locs' and op == 'set' and did == me:
        return 'loc_send'
    return None


def check_write(me, role, op, path, data, old):
    if role != 'admin':
        act = _perm_action(me, role, op, path, data, old)
        if act:
            if not _perm_val(me, role, act):
                raise Err(403, "Bu amal uchun sizga ruxsat berilmagan. Rahbar ruxsat bersa ishlaydi.")
            if act == 'order_new' and (data or {}).get('status') != 'new':
                raise Err(403, "Ruxsat yo'q.")
            return
    return _check_write_orig(me, role, op, path, data, old)


''' + M_END

J_BEGIN = '/* perms-ui v1 */\n'
J_END = '/* /perms-ui */\n'

JS = J_BEGIN + r'''const PERM_UI=[
 ['Zakazlar',[
  ['order_new',"Yangi zakaz qo'shish"],
  ['order_pickup',"«Olinishi kerak» zakazni olib ketish"],
  ['wash_start',"Yuvishni boshlash"],
  ['wash_done',"Yuvildi deb belgilash"],
  ['pack',"Qadoqlandi deb belgilash"],
  ['deliver',"Yetkazildi deb belgilash"],
  ['order_edit',"Zakazni to'liq tahrirlash"],
  ['order_delete',"Zakazni o'chirish"]]],
 ['Mijozlar',[
  ['client_add',"Yangi mijoz qo'shish"],
  ['client_edit',"Mijozni tahrirlash va o'chirish"]]],
 ['Joylashuv',[
  ['loc_send',"Joylashuvini yuborish"]]]
];
const PERM_DEF={courier:['order_new','order_pickup','deliver','client_add','loc_send'],washer:['wash_start','wash_done'],packer:['pack']};
function permsBody(role,p){
  if(role==='admin')return '<p class="sub">Rahbarda hamma ruxsat bor.</p>';
  const def=PERM_DEF[role]||[];
  return PERM_UI.map(g=>'<div class="sub" style="margin:14px 0 2px;font-weight:700">'+g[0]+'</div>'+g[1].map(i=>{
    const on=p&&Object.prototype.hasOwnProperty.call(p,i[0])?!!p[i[0]]:def.indexOf(i[0])>=0;
    return '<label style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid rgba(128,128,128,.18)"><input type="checkbox" data-perm="'+i[0]+'"'+(on?' checked':'')+' style="width:22px;height:22px;flex:none"><span>'+i[1]+'</span></label>';
  }).join('')).join('');
}
function permsHtml(x){
  const role=(x&&x.role)||'';
  setTimeout(permsSync,0);
  return '<div id="sf-perms" data-role="'+role+'" style="margin-top:16px"><h3 style="margin:0 0 4px">Ruxsatlar</h3><div id="sf-perms-body">'+permsBody(role||'courier',x&&x.perms)+'</div></div>';
}
function permsSync(){
  const sel=document.getElementById('sf-role'),box=document.getElementById('sf-perms');
  if(!sel||!box||box.dataset.role===sel.value)return;
  box.dataset.role=sel.value;
  document.getElementById('sf-perms-body').innerHTML=permsBody(sel.value,null);
}
document.addEventListener('change',e=>{if(e.target&&e.target.id==='sf-role')permsSync()});
function readPerms(){
  const o={};
  document.querySelectorAll('#sf-perms input[data-perm]').forEach(c=>{o[c.dataset.perm]=c.checked});
  return o;
}
''' + J_END


def main():
    sp, hp = os.path.join(D, 'server.py'), os.path.join(D, 'index.html')
    t = open(sp, encoding='utf-8').read()
    h = open(hp, encoding='utf-8').read()

    # ---- server.py ----
    if M_BEGIN in t:
        a, b = t.index(M_BEGIN), t.index(M_END) + len(M_END)
        new_t = t[:a] + FUNC.lstrip('\n') + t[b:]
    else:
        if t.count('def check_write(me, role, op, path, data, old):') != 1:
            sys.exit("Mos kelmadi (check_write topilmadi) - hech narsa o'zgarmadi.")
        anchors = list(re.finditer(r"^([ \t]*)if u\.path == '/api/me':[ \t]*$", t, re.M))
        if len(anchors) != 1:
            sys.exit("Mos kelmadi (server.py, /api/me: %d ta) - hech narsa o'zgarmadi." % len(anchors))
        classes = [m for m in re.finditer(r'^class \w+.*:[ \t]*\n', t, re.M) if m.start() < anchors[0].start()]
        if not classes:
            sys.exit("Mos kelmadi (class topilmadi) - hech narsa o'zgarmadi.")
        cls = classes[-1]
        t2 = t.replace('def check_write(me, role, op, path, data, old):',
                       'def _check_write_orig(me, role, op, path, data, old):')
        shift = len(t2) - len(t)
        new_t = t2[:cls.start() + shift] + FUNC.lstrip('\n') + t2[cls.start() + shift:]

    # ---- index.html ----
    if J_BEGIN in h:
        a, b = h.index(J_BEGIN), h.index(J_END) + len(J_END)
        new_h = h[:a] + JS + h[b:]
    else:
        err_div = '<div class="err" id="sf-err"></div>'
        data_pat = 'const data={name,role,login,active,passHash:'
        fn_pat = 'async function saveStaff(){'
        for pat in (err_div, data_pat, fn_pat):
            if h.count(pat) != 1:
                sys.exit("Mos kelmadi (index.html: %r %d ta) - hech narsa o'zgarmadi." % (pat, h.count(pat)))
        new_h = h.replace(err_div, '${permsHtml(x)}' + err_div)
        new_h = new_h.replace(data_pat, "const data={name,role,login,active,...(role==='admin'?{}:{perms:readPerms()}),passHash:")
        new_h = new_h.replace(fn_pat, JS + fn_pat)

    chk = '/tmp/chk_server.py'
    open(chk, 'w', encoding='utf-8').write(new_t)
    try:
        py_compile.compile(chk, doraise=True)
    except Exception as e:
        sys.exit("Xato: yangi server.py yaroqsiz (%s) - hech narsa o'zgarmadi." % e)

    stamp = time.strftime('%m%d-%H%M%S')
    for p, new in ((sp, new_t), (hp, new_h)):
        shutil.copy2(p, p + '.bak-' + stamp)
        open(p, 'w', encoding='utf-8').write(new)
    if TEST:
        print('TEST: fayllar yozildi.')
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
        print("Tayyor: ruxsatlar o'rnatildi. CRM sahifasini yangilang: Xodimlar -> xodimni bosing.")
    else:
        for p in (sp, hp):
            shutil.copy2(p + '.bak-' + stamp, p)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayllar qaytarildi.")


main()
