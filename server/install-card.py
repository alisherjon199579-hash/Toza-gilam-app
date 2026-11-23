#!/usr/bin/env python3
"""Toza Gilam CRM: dostavchik panelida to'lov kartasi (mijoz shu kartaga to'laydi).

CRM sahifasiga "Karta" tugmasi qo'shiladi (chap pastda). Bosilsa karta raqami va
egasining ismi chiqadi, "Nusxalash" tugmasi raqamni nusxalaydi.
Tugma dostavchi va rahbarga ko'rinadi (yuvuvchi va qadoqlovchiga ko'rinmaydi).

Karta ma'lumoti GitHub'da saqlanmaydi: ishga tushirishda beriladi.
Ishga tushirish (serverda, root):
    CARD="0000000000000000" NAME="Ism Familiya" python3 install-card.py
Qayta ishga tushirilsa, karta yangilanadi (eski qism almashtiriladi).
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski faylni qaytaradi.
"""
import json, os, re, shutil, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))

HTML = r'''<style id="appcard-css">
#appcard-btn{position:fixed;left:14px;bottom:calc(14px + env(safe-area-inset-bottom,0px));z-index:9998;display:none;
  align-items:center;gap:6px;border:0;border-radius:24px;padding:12px 16px;background:#0b6b74;color:#fff;
  font:600 15px/1 system-ui,sans-serif;box-shadow:0 6px 18px rgba(0,0,0,.28);cursor:pointer}
#appcard-ov{position:fixed;inset:0;z-index:9999;background:rgba(10,20,25,.55);display:none;align-items:flex-end;justify-content:center}
#appcard-ov.on{display:flex}
#appcard-sh{width:100%;max-width:460px;background:#fff;border-radius:22px 22px 0 0;padding:20px 20px calc(22px + env(safe-area-inset-bottom,0px));
  font-family:system-ui,sans-serif;color:#10222a}
#appcard-sh h3{margin:0 0 4px;font-size:18px}
#appcard-sh p.s{margin:0 0 14px;color:#5c6f77;font-size:14px}
#appcard-box{border-radius:16px;padding:18px;background:linear-gradient(135deg,#0b6b74,#0f8a8f);color:#fff}
#appcard-num{font:700 24px/1.2 ui-monospace,monospace;letter-spacing:1.5px;word-spacing:6px}
#appcard-nm{margin-top:12px;font-size:16px;opacity:.95}
#appcard-cp{width:100%;margin-top:14px;border:0;border-radius:14px;padding:15px;background:#10222a;color:#fff;font:600 16px system-ui,sans-serif;cursor:pointer}
#appcard-cl{width:100%;margin-top:8px;border:0;background:none;padding:12px;color:#5c6f77;font:500 15px system-ui,sans-serif;cursor:pointer}
</style>
<script id="appcard-js" data-v="1">
(function(){
  var CARD=__CARD__,NAME=__NAME__,btn,ov,cp,role=null,asked=false;
  function logged(){try{return typeof S!=='undefined'&&S&&!!S.me}catch(e){return false}}
  function findRole(o){try{if(!o)return null;if(typeof o.role==='string')return o.role;
    var k=['me','user','staff','who'];for(var i=0;i<k.length;i++){var v=o[k[i]];if(v&&typeof v==='object'){var r=findRole(v);if(r)return r}}}catch(e){}return null}
  function fmt(n){return String(n).replace(/\D/g,'').replace(/(\d{4})(?=\d)/g,'$1 ')}
  function copy(t){
    try{if(navigator.clipboard&&navigator.clipboard.writeText)return navigator.clipboard.writeText(t)}catch(e){}
    return new Promise(function(ok,no){try{var a=document.createElement('textarea');a.value=t;a.style.cssText='position:fixed;opacity:0';
      document.body.appendChild(a);a.select();var r=document.execCommand('copy');a.remove();r?ok():no()}catch(e){no(e)}})}
  function build(){
    btn=document.createElement('button');btn.id='appcard-btn';btn.type='button';btn.textContent='💳 Karta';
    ov=document.createElement('div');ov.id='appcard-ov';
    ov.innerHTML='<div id="appcard-sh"><h3>To‘lov kartasi</h3><p class="s">Mijoz shu kartaga to‘lov qiladi</p>'+
      '<div id="appcard-box"><div id="appcard-num"></div><div id="appcard-nm"></div></div>'+
      '<button id="appcard-cp" type="button">Raqamni nusxalash</button><button id="appcard-cl" type="button">Yopish</button></div>';
    document.body.appendChild(btn);document.body.appendChild(ov);
    ov.querySelector('#appcard-num').textContent=fmt(CARD);ov.querySelector('#appcard-nm').textContent=NAME;
    cp=ov.querySelector('#appcard-cp');
    btn.onclick=function(){ov.classList.add('on')};
    ov.querySelector('#appcard-cl').onclick=function(){ov.classList.remove('on')};
    ov.onclick=function(e){if(e.target===ov)ov.classList.remove('on')};
    cp.onclick=function(){copy(String(CARD).replace(/\D/g,'')).then(function(){cp.textContent='Nusxalandi ✓'},
      function(){cp.textContent='Nusxalab bo‘lmadi'});setTimeout(function(){cp.textContent='Raqamni nusxalash'},1800)}}
  function allowed(){return role===null||role==='courier'||role==='admin'}
  function tick(){try{
    if(!btn)build();
    var on=logged();
    if(on&&role===null){role=findRole(S);
      if(role===null&&!asked){asked=true;fetch('/api/me',{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null})
        .then(function(d){role=findRole(d)||role}).catch(function(){})}}
    if(!on)role=null;
    btn.style.display=(on&&allowed())?'flex':'none'}catch(e){}}
  setInterval(tick,1000);
})();
</script>
'''


def main():
    card = re.sub(r'\D', '', os.environ.get('CARD', ''))
    name = ' '.join(os.environ.get('NAME', '').split())
    if len(card) not in (16, 19) or not name:
        sys.exit('Karta raqami (16 xona) va ism kerak. Misol:\n'
                 '  CARD="0000000000000000" NAME="Ism Familiya" python3 install-card.py')
    hp = os.path.join(D, 'index.html')
    h = open(hp, encoding='utf-8').read()
    block = HTML.replace('__CARD__', json.dumps(card)).replace('__NAME__', json.dumps(name, ensure_ascii=False))
    old = re.search(r'<style id="appcard-css">.*?</style>\s*<script id="appcard-js"[^>]*>.*?</script>\n?', h, re.S)
    if old:
        new_h = h[:old.start()] + block + h[old.end():]
        done = "Tayyor: karta yangilandi. CRM sahifasini yangilang."
    else:
        i = h.rfind('</body>')
        if i < 0:
            sys.exit("Mos kelmadi (</body> topilmadi) - hech narsa o'zgarmadi.")
        new_h = h[:i] + block + h[i:]
        done = "Tayyor: dostavchik panelida 'Karta' tugmasi paydo bo'ldi. CRM sahifasini yangilang."

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
        print(done)
    else:
        shutil.copy2(hp + '.bak-' + stamp, hp)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayl qaytarildi.")


main()
