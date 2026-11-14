#!/usr/bin/env python3
"""Toza Gilam CRM serveriga jamoa chatini o'rnatadi (matn va ovozli xabar):
  - GET /api/app/chat?after=ID        yangi xabarlar
  - GET /api/app/chat/voice?id=ID     ovozli xabar fayli
  - PUT /api/app/chat/text            matn yuborish  {"text": "..."}
  - PUT /api/app/chat/voice?dur=N     ovozli xabar yuborish (so'rov tanasi - audio)
  - CRM sahifasida chat tugmasi va oynasi
Ishga tushirish (serverda, root):  python3 install-chat.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski fayllarni qaytaradi.
"""
import os, re, shutil, subprocess, sys, time, py_compile, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))

FUNC = r'''
# ---- ilova: jamoa chati (app-chat) v2 ----
def _chat_db():
    import os, sqlite3
    c = sqlite3.connect(os.path.join(os.environ.get('CRM_DATA', '/var/lib/gilam-crm'), 'crm.db'), timeout=10)
    c.execute('CREATE TABLE IF NOT EXISTS app_chat(id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT, name TEXT, role TEXT,'
              ' t INTEGER, text TEXT, voice INTEGER DEFAULT 0, dur INTEGER DEFAULT 0, mime TEXT, data BLOB)')
    c.execute('CREATE TABLE IF NOT EXISTS app_chat_read(uid TEXT PRIMARY KEY, name TEXT, last INTEGER)')
    return c


def _chat_who(h):
    me, s = h.auth()
    if not me:
        h.send(401, {'error': 'Tizimga kiring.'})
        return None
    s = s or {}
    return str(me), str(s.get('name') or s.get('login') or me), str(s.get('role') or '')


def _chat_list(h, u):
    import urllib.parse
    who = _chat_who(h)
    if not who:
        return
    q = urllib.parse.parse_qs(u.query)
    try:
        after = int(q.get('after', ['0'])[0])
    except Exception:
        after = 0
    try:
        seen = int(q.get('seen', ['0'])[0])
    except Exception:
        seen = 0
    c = _chat_db()
    try:
        if seen > 0:
            # chat oynasi ochiq: shu xodim 'seen' gacha bo'lgan xabarlarni o'qidi
            top = c.execute('SELECT MAX(id) FROM app_chat').fetchone()[0] or 0
            c.execute('INSERT INTO app_chat_read(uid,name,last) VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET'
                      ' name=excluded.name, last=MAX(last, excluded.last)', (who[0], who[1], min(seen, top)))
            c.commit()
        readers = [{'name': r[0], 'last': r[1]} for r in
                   c.execute('SELECT name,last FROM app_chat_read WHERE uid<>? ORDER BY name', (who[0],))]
        cols = 'id,uid,name,role,t,text,voice,dur'
        if after > 0:
            rows = c.execute('SELECT %s FROM app_chat WHERE id>? ORDER BY id LIMIT 300' % cols, (after,)).fetchall()
        else:
            rows = c.execute('SELECT %s FROM (SELECT %s FROM app_chat ORDER BY id DESC LIMIT 150) ORDER BY id' % (cols, cols)).fetchall()
    finally:
        c.close()
    out = [{'id': r[0], 'uid': r[1], 'name': r[2], 'role': r[3], 't': r[4], 'text': r[5] or '', 'voice': bool(r[6]), 'dur': r[7] or 0}
           for r in rows]
    return h.send(200, {'me': who[0], 'list': out, 'readers': readers})


def _chat_voice(h, u):
    import urllib.parse
    if not _chat_who(h):
        return
    try:
        mid = int(urllib.parse.parse_qs(u.query)['id'][0])
    except Exception:
        return h.send(400, {'error': "Xabar ko'rsatilmagan."})
    c = _chat_db()
    try:
        r = c.execute('SELECT mime,data FROM app_chat WHERE id=? AND voice=1', (mid,)).fetchone()
    finally:
        c.close()
    if not r or r[1] is None:
        return h.send(404, {'error': 'Topilmadi.'})
    data = bytes(r[1])
    h.send_response(200)
    h.send_header('Content-Type', r[0] or 'audio/webm')
    h.send_header('Content-Length', str(len(data)))
    h.send_header('Cache-Control', 'private, max-age=86400')
    h.end_headers()
    h.wfile.write(data)


def _app_put(h):
    """PUT so'rovlari: chatga matn yoki ovozli xabar yozish."""
    import json, re, time, urllib.parse
    u = urllib.parse.urlparse(h.path)
    try:
        n = int(h.headers.get('Content-Length') or 0)
    except Exception:
        n = 0
    if n < 0 or n > 4 * 1024 * 1024:
        h.close_connection = True
        return h.send(413, {'error': 'Xabar juda katta.'})
    body = h.rfile.read(n) if n else b''
    if u.path not in ('/api/app/chat/text', '/api/app/chat/voice'):
        return h.send(404, {'error': 'Topilmadi.'})
    who = _chat_who(h)
    if not who:
        return
    uid, name, role = who
    now = int(time.time())
    c = _chat_db()
    try:
        if u.path == '/api/app/chat/text':
            try:
                text = str(json.loads(body.decode('utf-8')).get('text') or '').strip()[:2000]
            except Exception:
                text = ''
            if not text:
                return h.send(400, {'error': "Xabar bo'sh."})
            cur = c.execute('INSERT INTO app_chat(uid,name,role,t,text) VALUES(?,?,?,?,?)', (uid, name, role, now, text))
        else:
            if len(body) < 200:
                return h.send(400, {'error': 'Ovoz yozilmadi.'})
            mime = (h.headers.get('Content-Type') or '').strip()
            if not re.match(r'^audio/[\w.+-]+(;[\w=. "-]+)*$', mime):
                mime = 'audio/webm'
            try:
                dur = max(0, min(600, int(float(urllib.parse.parse_qs(u.query).get('dur', ['0'])[0]))))
            except Exception:
                dur = 0
            cur = c.execute('INSERT INTO app_chat(uid,name,role,t,text,voice,dur,mime,data) VALUES(?,?,?,?,?,1,?,?,?)',
                            (uid, name, role, now, '', dur, mime, body))
            # eski ovozli xabarlar (60 kundan oshgan) joy egallamasligi uchun o'chiriladi
            c.execute('UPDATE app_chat SET data=NULL WHERE voice=1 AND t<? AND data IS NOT NULL', (now - 60 * 86400,))
        c.commit()
        mid = cur.lastrowid
    finally:
        c.close()
    return h.send(200, {'ok': True, 'id': mid})


'''

HTML = r'''<style id="appchat-css">
#appchat-btn{position:fixed;z-index:8;right:max(16px,env(safe-area-inset-right,0px));bottom:calc(138px + env(safe-area-inset-bottom,0px));width:54px;height:54px;border-radius:50%;border:0;background:var(--accent,#0a6f79);color:var(--accent-ink,#fff);box-shadow:var(--shadow,0 4px 14px rgba(0,0,0,.2));display:flex;align-items:center;justify-content:center;padding:0}
#appchat-btn svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
#appchat-badge{position:absolute;top:-4px;right:-4px;min-width:22px;height:22px;border-radius:11px;background:#d92d20;color:#fff;font:700 12px/22px system-ui,sans-serif;text-align:center;padding:0 6px;font-style:normal}
#appchat-panel{position:fixed;inset:0;z-index:40;background:var(--bg,#f1f5f6);color:var(--ink,#10252b);display:flex;flex-direction:column;padding-top:env(safe-area-inset-top,0px)}
#appchat-panel[hidden],#appchat-btn[hidden],#appchat-badge[hidden],#appchat-tip[hidden]{display:none!important}
#appchat-head{display:flex;align-items:center;gap:10px;padding:12px 16px;background:var(--surface,#fff);border-bottom:1px solid var(--line,#d5dfe2)}
#appchat-head b{flex:1;font-size:18px}
#appchat-head button{border:0;background:var(--sunk,#e6edef);color:inherit;border-radius:999px;width:38px;height:38px;font-size:18px;line-height:1}
#appchat-list{flex:1;overflow-y:auto;padding:14px 12px;display:flex;flex-direction:column;gap:8px}
#appchat-list .day{align-self:center;font-size:12px;color:var(--muted,#587078);background:var(--sunk,#e6edef);border-radius:999px;padding:3px 10px}
#appchat-list .acm{max-width:82%;align-self:flex-start;background:var(--surface,#fff);border:1px solid var(--line,#d5dfe2);border-radius:16px 16px 16px 4px;padding:8px 12px;overflow-wrap:anywhere;white-space:pre-wrap}
#appchat-list .acm.me{align-self:flex-end;background:var(--accent-soft,#d9eef0);border-color:transparent;border-radius:16px 16px 4px 16px}
#appchat-list .acm small{display:block;font-size:12px;font-weight:700;color:var(--accent,#0a6f79);margin-bottom:2px;white-space:normal}
#appchat-list .acm time{display:block;font-size:11px;color:var(--muted,#587078);text-align:right;margin-top:3px}
#appchat-list .acm time b{font-weight:700;font-size:15px;margin-left:5px;letter-spacing:-2px;padding-right:2px}
#appchat-list .acm time b.read{color:#1a8fe3}
#appchat-tip{position:absolute;left:50%;transform:translateX(-50%);bottom:86px;z-index:2;max-width:86%;background:var(--ink,#10252b);color:var(--bg,#fff);border-radius:12px;padding:9px 14px;font-weight:600;font-size:14px;text-align:center}
#appchat-list .acm .voice{display:flex;align-items:center;gap:10px;border:0;background:none;color:inherit;font:inherit;font-weight:600;padding:4px 0;min-width:150px}
#appchat-list .acm .voice i{width:38px;height:38px;border-radius:50%;background:var(--accent,#0a6f79);color:var(--accent-ink,#fff);display:flex;align-items:center;justify-content:center;font-style:normal;font-size:15px;flex:none}
#appchat-empty{margin:auto;color:var(--muted,#587078);text-align:center;padding:0 24px}
#appchat-foot{display:flex;align-items:flex-end;gap:8px;padding:10px 12px;padding-bottom:calc(10px + env(safe-area-inset-bottom,0px));background:var(--surface,#fff);border-top:1px solid var(--line,#d5dfe2)}
#appchat-foot textarea{flex:1;min-height:44px;max-height:120px;resize:none;border-radius:22px;padding:10px 14px}
#appchat-foot button{flex:none;width:46px;height:46px;border-radius:50%;border:0;background:var(--accent,#0a6f79);color:var(--accent-ink,#fff);font-size:19px;line-height:1;display:flex;align-items:center;justify-content:center;padding:0}
#appchat-foot button svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
#appchat-foot #appchat-cancel{background:var(--sunk,#e6edef);color:inherit}
#appchat-foot.rec #appchat-mic{background:#d92d20;color:#fff}
#appchat-rec{flex:1;font-weight:700;color:#d92d20;align-self:center;padding-left:6px}
#appchat-foot:not(.rec) #appchat-rec,#appchat-foot:not(.rec) #appchat-cancel,#appchat-foot.rec textarea,#appchat-foot.rec #appchat-send{display:none}
@media(min-width:900px){#appchat-panel>*{width:100%;max-width:760px;margin-left:auto;margin-right:auto}#appchat-btn{bottom:96px;right:28px}}
</style>
<script id="appchat-js" data-v="2">
/* Jamoa chati: rahbar va xodimlar o'rtasida matn va ovozli xabarlar */
(function(){
  var open=false,lastId=0,meId=null,busy=false,lastPoll=0,first=true,lastDay='';
  var readers=[],mineEls=[],tipEl=null,tipTimer=null;
  var btn,badge,panel,list,foot,input,recLabel,rec=null,chunks=[],recStart=0,recTimer=null,recCancel=false,playing=null;
  function ls(k,v){try{if(v===undefined)return +localStorage.getItem(k)||0;localStorage.setItem(k,String(v))}catch(e){return 0}}
  function logged(){try{return typeof S!=='undefined'&&S&&!!S.me}catch(e){return false}}
  function p2(n){return n<10?'0'+n:''+n}
  function clock(t){var d=new Date(t*1000);return p2(d.getHours())+':'+p2(d.getMinutes())}
  function day(t){var d=new Date(t*1000);return p2(d.getDate())+'.'+p2(d.getMonth()+1)+'.'+d.getFullYear()}
  function mmss(s){s=Math.max(0,Math.round(s));return Math.floor(s/60)+':'+p2(s%60)}
  function el(tag,cls,text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
  function build(){
    btn=el('button');btn.id='appchat-btn';btn.type='button';btn.setAttribute('aria-label','Chat');
    btn.innerHTML='<svg viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12.500h5"/></svg><i id="appchat-badge" hidden></i>';
    btn.hidden=true;btn.onclick=show;document.body.appendChild(btn);badge=btn.querySelector('#appchat-badge');
    panel=el('div');panel.id='appchat-panel';panel.hidden=true;
    panel.innerHTML='<div id="appchat-head"><b>Jamoa chati</b><button type="button" id="appchat-x" aria-label="Yopish">&#10005;</button></div>'
      +'<div id="appchat-list"></div>'
      +'<div id="appchat-foot"><textarea id="appchat-in" rows="1" placeholder="Xabar yozing"></textarea><span id="appchat-rec"></span>'
      +'<button type="button" id="appchat-cancel" aria-label="Bekor qilish">&#10005;</button>'
      +'<button type="button" id="appchat-mic" aria-label="Ovozli xabar"><svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.500 11a6.500 6.500 0 0013 0M12 17.500V21"/></svg></button>'
      +'<button type="button" id="appchat-send" aria-label="Yuborish"><svg viewBox="0 0 24 24"><path d="M4 12l16-7-6 16-3-6z"/></svg></button></div>';
    document.body.appendChild(panel);
    list=panel.querySelector('#appchat-list');foot=panel.querySelector('#appchat-foot');input=panel.querySelector('#appchat-in');recLabel=panel.querySelector('#appchat-rec');
    panel.querySelector('#appchat-x').onclick=function(){if(history.state&&history.state.appchat)history.back();else hide()};
    panel.querySelector('#appchat-send').onclick=sendText;
    panel.querySelector('#appchat-mic').onclick=function(){if(rec)stopRec(false);else startRec()};
    panel.querySelector('#appchat-cancel').onclick=function(){stopRec(true)};
    input.addEventListener('input',function(){input.style.height='auto';input.style.height=Math.min(120,input.scrollHeight)+'px'});
    window.addEventListener('popstate',function(){if(open)hide()});
  }
  function show(){open=true;panel.hidden=false;try{history.pushState({appchat:1},'')}catch(e){}
    ls('appchat_seen',lastId);setBadge(0);list.scrollTop=list.scrollHeight;poll()}
  function hide(){open=false;panel.hidden=true;if(rec)stopRec(true)}
  function setBadge(n){badge.hidden=!n;badge.textContent=n>99?'99+':String(n)}
  function add(m){
    var e=list.querySelector('#appchat-empty');if(e)e.remove();
    var d=day(m.t);if(d!==lastDay){lastDay=d;list.appendChild(el('div','day',d))}
    var mine=String(m.uid)===String(meId),b=el('div','acm'+(mine?' me':''));
    if(!mine)b.appendChild(el('small','',m.name));
    if(m.voice){var v=el('button','voice');v.type='button';var ic=el('i','','▶');v.appendChild(ic);
      v.appendChild(el('span','','Ovozli xabar'+(m.dur?' · '+mmss(m.dur):'')));
      v.onclick=function(){play(m.id,ic)};b.appendChild(v)}
    else b.appendChild(document.createTextNode(m.text));
    var tm=el('time','',clock(m.t));b.appendChild(tm);
    if(mine){var tk=el('b','','\u2713');tm.appendChild(tk);mineEls.push({id:m.id,tk:tk});
      b.onclick=function(ev){if(ev.target.closest&&ev.target.closest('.voice'))return;
        var who=readers.filter(function(r){return r.last>=m.id}).map(function(r){return r.name});
        tip(who.length?"O'qidi: "+who.join(', '):'Yuborildi. Hali hech kim o\'qimagan')}}
    list.appendChild(b)}
  function ticks(){mineEls.forEach(function(x){var rd=readers.some(function(r){return r.last>=x.id});
    x.tk.textContent=rd?'\u2713\u2713':'\u2713';x.tk.className=rd?'read':''})}
  function play(id,ic){
    if(playing){try{playing.a.pause()}catch(e){}playing.ic.textContent='▶';var same=playing.id===id;playing=null;if(same)return}
    ic.textContent='…';
    fetch('/api/app/chat/voice?id='+id,{credentials:'same-origin'}).then(function(r){if(!r.ok)throw 0;return r.blob()}).then(function(bl){
      var a=new Audio(URL.createObjectURL(bl));playing={a:a,ic:ic,id:id};ic.textContent='⏸';
      a.onended=a.onerror=function(){ic.textContent='▶';if(playing&&playing.id===id)playing=null};
      return a.play()}).catch(function(){ic.textContent='▶';playing=null;tip("Ovozli xabarni ochib bo'lmadi")})}
  function tip(t){if(!tipEl){tipEl=el('div');tipEl.id='appchat-tip';panel.appendChild(tipEl)}
    tipEl.textContent=t;tipEl.hidden=false;clearTimeout(tipTimer);tipTimer=setTimeout(function(){tipEl.hidden=true},2600)}
  function note(fresh){try{
    if(!('Notification' in window)||Notification.permission!=='granted')return;
    var m=fresh[fresh.length-1],body=m.voice?'🎤 Ovozli xabar':m.text;
    new Notification(fresh.length>1?'Chat: '+fresh.length+' ta yangi xabar':'Chat: '+m.name,{body:fresh.length>1?m.name+': '+body:body,tag:'chat'})}catch(e){}}
  function poll(){
    if(busy||!logged())return;busy=true;lastPoll=Date.now();
    fetch('/api/app/chat?after='+lastId+(open&&lastId?'&seen='+lastId:''),{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(d){
      busy=false;if(!d)return;meId=d.me;
      var atEnd=list.scrollHeight-list.scrollTop-list.clientHeight<80;
      d.list.forEach(function(m){if(m.id>lastId){add(m);lastId=m.id}});
      readers=d.readers||[];ticks();
      if(first){first=false;if(!list.children.length){var e=el('div','',"Hali xabar yo'q. Birinchi bo'lib yozing.");e.id='appchat-empty';list.appendChild(e)}
        if(!ls('appchat_seen')&&!ls('appchat_told')){ls('appchat_seen',lastId);ls('appchat_told',lastId)}}
      var others=d.list.filter(function(m){return String(m.uid)!==String(meId)});
      var fresh=others.filter(function(m){return m.id>ls('appchat_told')});
      if(lastId>ls('appchat_told'))ls('appchat_told',lastId);
      if(open){ls('appchat_seen',lastId);if(d.list.length&&atEnd)list.scrollTop=list.scrollHeight}
      else{if(fresh.length)note(fresh);
        if(d.list.length){var seen=ls('appchat_seen'),n=0,bs=list.querySelectorAll('.acm:not(.me)');
          n=others.filter(function(m){return m.id>seen}).length+(+badge.textContent||0)*(badge.hidden?0:1);setBadge(n)}}
    }).catch(function(){busy=false})}
  function sendText(){
    var t=input.value.trim();if(!t)return;input.value='';input.style.height='auto';
    fetch('/api/app/chat/text',{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})})
      .then(function(r){if(!r.ok)throw 0;poll()}).catch(function(){input.value=t;tip('Yuborilmadi. Internetni tekshiring')})}
  function startRec(){
    if(!navigator.mediaDevices||!window.MediaRecorder){tip("Bu qurilmada ovoz yozib bo'lmaydi");return}
    navigator.mediaDevices.getUserMedia({audio:true}).then(function(stream){
      var opt={};['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'].some(function(t){if(MediaRecorder.isTypeSupported&&MediaRecorder.isTypeSupported(t)){opt.mimeType=t;return true}});
      opt.audioBitsPerSecond=24000;
      rec=new MediaRecorder(stream,opt);chunks=[];recCancel=false;recStart=Date.now();
      rec.ondataavailable=function(e){if(e.data&&e.data.size)chunks.push(e.data)};
      rec.onstop=function(){stream.getTracks().forEach(function(t){t.stop()});clearInterval(recTimer);foot.classList.remove('rec');
        var dur=(Date.now()-recStart)/1000,type=(rec.mimeType||opt.mimeType||'audio/webm').split(';')[0];rec=null;
        if(recCancel||dur<1||!chunks.length)return;
        var blob=new Blob(chunks,{type:type});
        fetch('/api/app/chat/voice?dur='+Math.round(dur),{method:'PUT',credentials:'same-origin',headers:{'Content-Type':type},body:blob})
          .then(function(r){if(!r.ok)throw 0;poll()}).catch(function(){tip('Ovozli xabar yuborilmadi')})};
      rec.start();foot.classList.add('rec');recLabel.textContent='● 0:00';
      recTimer=setInterval(function(){var s=(Date.now()-recStart)/1000;recLabel.textContent='● '+mmss(s);if(s>=180)stopRec(false)},500);
    }).catch(function(){tip('Mikrofonga ruxsat berilmadi')})}
  function stopRec(cancel){recCancel=cancel;try{if(rec&&rec.state!=='inactive')rec.stop()}catch(e){}}
  function tick(){try{
    if(!btn)build();
    var on=logged();btn.hidden=!on;if(!on){if(open)hide();return}
    if(Date.now()-lastPoll>(open?4000:12000))poll()}catch(e){}}
  setInterval(tick,1000);
})();
</script>
'''


def main():
    sp, hp = os.path.join(D, 'server.py'), os.path.join(D, 'index.html')
    t = open(sp, encoding='utf-8').read()
    h = open(hp, encoding='utf-8').read()
    upgrade = '/api/app/chat' in t or 'appchat-js' in h
    if upgrade:
        if '(app-chat) v2 ----' in t and 'id="appchat-js" data-v="2"' in h:
            sys.exit("Allaqachon oxirgi versiya o'rnatilgan - hech narsa o'zgarmadi.")
    anchors = list(re.finditer(r"^([ \t]*)if u\.path == '/api/me':[ \t]*$", t, re.M))
    if len(anchors) != 1:
        sys.exit("Mos kelmadi (server.py, /api/me: %d ta) - hech narsa o'zgarmadi." % len(anchors))
    a = anchors[0]
    classes = [m for m in re.finditer(r'^class \w+.*:[ \t]*\n', t, re.M) if m.start() < a.start()]
    i = h.rfind('</body>')
    if not classes or i < 0:
        sys.exit("Mos kelmadi (class yoki </body> topilmadi) - hech narsa o'zgarmadi.")
    cls = classes[-1]
    if upgrade:
        # avval o'rnatilgan chat: funksiyalar va sahifadagi qism yangisiga almashtiriladi
        m0 = re.search(r'^# ---- ilova: jamoa chati \(app-chat\).*\n', t, re.M)
        old = re.search(r'<style id="appchat-css">.*?</style>\s*<script id="appchat-js"[^>]*>.*?</script>\n?', h, re.S)
        if not m0 or m0.start() > cls.start() or not old or 'def _app_put' not in t[m0.start():cls.start()] \
                or re.search(r'^class ', t[m0.start():cls.start()], re.M):
            sys.exit("Mos kelmadi (eski chat qismi topilmadi) - hech narsa o'zgarmadi.")
        new_t = t[:m0.start()] + FUNC.lstrip('\n') + t[cls.start():]
        new_h = h[:old.start()] + HTML + h[old.end():]
        return apply(sp, hp, new_t, new_h, "Tayyor: jamoa chati yangilandi. CRM sahifasini yangilang.")
    if re.search(r'^\s*def do_PUT\(', t, re.M):
        sys.exit("Mos kelmadi (do_PUT allaqachon bor) - hech narsa o'zgarmadi.")
    body = re.match(r'(?:[ \t]*\n)*([ \t]+)\S', t[cls.end():])
    if not body:
        sys.exit("Mos kelmadi (class ichi topilmadi) - hech narsa o'zgarmadi.")
    bi = body.group(1)
    method = "%sdef do_PUT(self):\n%s%sreturn _app_put(self)\n\n" % (bi, bi, bi)
    ind = a.group(1)
    route = ("%sif u.path == '/api/app/chat':\n%s    return _chat_list(self, u)\n"
             "%sif u.path == '/api/app/chat/voice':\n%s    return _chat_voice(self, u)\n") % (ind, ind, ind, ind)
    new_t = (t[:cls.start()] + FUNC.lstrip('\n') + t[cls.start():cls.end()] + method
             + t[cls.end():a.start()] + route + t[a.start():])
    new_h = h[:i] + HTML + h[i:]
    return apply(sp, hp, new_t, new_h, "Tayyor: jamoa chati o'rnatildi. CRM sahifasini yangilang.")


def apply(sp, hp, new_t, new_h, done):
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
        print(done)
    else:
        for p in (sp, hp):
            shutil.copy2(p + '.bak-' + stamp, p)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayllar qaytarildi.")


main()
