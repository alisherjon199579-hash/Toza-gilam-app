#!/usr/bin/env python3
"""Toza Gilam CRM serveriga ilova uchun qo'shimcha o'rnatadi:
  - GET /api/app/loc?lat=..&lng=..   dostavchik ilovasi joylashuv yuboradi
  - GET /api/app/track               rahbar xaritasi uchun ma'lumot
  - Bosh sahifada "Dostavchiklar xaritada" bo'limi
Ishga tushirish (serverda, root):  python3 install-app.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski fayllarni qaytaradi.
"""
import os, re, shutil, subprocess, sys, time, py_compile, urllib.request

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))

FUNC = r'''
# ---- ilova: dostavchik joylashuvi (app-loc) ----
def _app_db():
    import os, sqlite3
    c = sqlite3.connect(os.path.join(os.environ.get('CRM_DATA', '/var/lib/gilam-crm'), 'crm.db'), timeout=10)
    c.execute('CREATE TABLE IF NOT EXISTS app_track(uid TEXT, name TEXT, t INTEGER, lat REAL, lng REAL)')
    c.execute('CREATE INDEX IF NOT EXISTS app_track_ut ON app_track(uid, t)')
    return c


def _app_loc(h, u):
    """Ilova joylashuv yuboradi. Faqat tizimga kirgan dostavchikdan qabul qilinadi."""
    import time, urllib.parse
    me, s = h.auth()
    if not me:
        return h.send(401, {'error': 'Tizimga kiring.'})
    s = s or {}
    if s.get('role') != 'courier':
        return h.send(403, {'error': 'Faqat dostavchik uchun.'})
    q = urllib.parse.parse_qs(u.query)
    try:
        lat, lng = float(q['lat'][0]), float(q['lng'][0])
    except Exception:
        return h.send(400, {'error': "Joylashuv yo'q."})
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return h.send(400, {'error': "Joylashuv noto'g'ri."})
    now, uid = int(time.time()), str(me)
    name = str(s.get('name') or s.get('login') or uid)
    c = _app_db()
    try:
        last = c.execute('SELECT t,lat,lng FROM app_track WHERE uid=? ORDER BY t DESC LIMIT 1', (uid,)).fetchone()
        moved = not last or abs(last[1] - lat) > 0.00015 or abs(last[2] - lng) > 0.00015  # ~15 metr
        if moved or now - last[0] >= 60:
            c.execute('INSERT INTO app_track(uid,name,t,lat,lng) VALUES(?,?,?,?,?)', (uid, name, now, lat, lng))
        if now % 100 == 0:
            c.execute('DELETE FROM app_track WHERE t<?', (now - 3 * 86400,))
        c.commit()
    finally:
        c.close()
    return h.send(200, {'ok': True})


def _app_track(h):
    """Xarita uchun: har bir dostavchikning oxirgi joyi va bugungi yo'li."""
    import time
    me, s = h.auth()
    if not me:
        return h.send(401, {'error': 'Tizimga kiring.'})
    now = int(time.time())
    tz = 5 * 3600  # Toshkent vaqti
    day0 = (now + tz) // 86400 * 86400 - tz
    c = _app_db()
    try:
        rows = c.execute('SELECT uid,name,t,lat,lng FROM app_track WHERE t>=? ORDER BY t', (day0,)).fetchall()
    finally:
        c.close()
    by = {}
    for uid, name, t, lat, lng in rows:
        d = by.setdefault(uid, {'uid': uid, 'name': name, 'pts': []})
        d['name'] = name
        d['pts'].append([lat, lng])
        d['last'] = [t * 1000, lat, lng]
    out = []
    for d in sorted(by.values(), key=lambda x: x['name']):
        d['pts'] = d['pts'][-600:]
        d['live'] = now * 1000 - d['last'][0] < 180000
        out.append(d)
    return h.send(200, {'now': now * 1000, 'list': out})


'''

HTML = r'''<script id="applive-js">
/* Rahbar bosh sahifasida: dostavchiklar xaritada (ilova yuborgan joylashuv) */
(function(){
  var wrap,map,data,layers=[],fitted=false,lastFetch=0,queue=null;
  function loadLeaflet(cb){
    if(window.L)return cb();
    if(queue){queue.push(cb);return}
    queue=[cb];
    var c=document.createElement('link');c.rel='stylesheet';c.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(c);
    var s=document.createElement('script');s.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    s.onload=function(){var q=queue;queue=null;q.forEach(function(f){f()})};
    s.onerror=function(){queue=null};
    document.head.appendChild(s)}
  function build(){
    wrap=document.createElement('div');
    wrap.style.cssText='background:#fff;color:#111827;border-radius:14px;padding:12px;margin:0 0 14px;box-shadow:0 1px 4px rgba(0,0,0,.12)';
    wrap.innerHTML='<div style="font-weight:700;margin-bottom:8px">Dostavchiklar xaritada</div>'
      +'<div id="applivemap" style="height:300px;border-radius:10px;overflow:hidden;background:#e5e7eb"></div>'
      +'<div id="applivelist" style="margin-top:8px;font-size:14px;line-height:1.6"></div>'}
  function ago(ms){var m=Math.round(ms/60000);return m<1?'hozirgina':m<60?m+' daqiqa oldin':Math.round(m/60)+' soat oldin'}
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function draw(){
    if(!data||!wrap)return;
    var all=[],html='',colors=['#2563eb','#dc2626','#16a34a','#d97706','#7c3aed'];
    if(map){layers.forEach(function(l){map.removeLayer(l)});layers=[]}
    data.list.forEach(function(c,i){
      var col=colors[i%colors.length];
      html+='<div><span style="color:'+col+'">&#9679;</span> <b>'+esc(c.name)+'</b> &mdash; '+(c.live?'jonli':'oxirgi marta '+ago(data.now-c.last[0]))+'</div>';
      if(map){
        if(c.pts.length>1)layers.push(L.polyline(c.pts,{color:col,weight:4,opacity:.7}).addTo(map));
        layers.push(L.circleMarker([c.last[1],c.last[2]],{radius:9,color:'#fff',weight:2,fillColor:col,fillOpacity:c.live?1:.5}).addTo(map)
          .bindTooltip(esc(c.name),{permanent:true,direction:'top',offset:[0,-8]}))}
      all.push([c.last[1],c.last[2]])});
    wrap.querySelector('#applivelist').innerHTML=html||"Bugun hali hech bir dostavchik ilovani ochmagan.";
    if(map&&all.length&&!fitted){fitted=true;if(all.length>1)map.fitBounds(all,{padding:[40,40],maxZoom:16});else map.setView(all[0],15)}}
  function tick(){try{
    var b=document.getElementById('body');
    if(!(typeof S!=='undefined'&&S.me&&typeof isAdmin==='function'&&isAdmin()&&S.tab==='dash'&&b))return;
    if(!wrap)build();
    if(wrap.parentNode!==b){b.insertBefore(wrap,b.firstChild);if(map)setTimeout(function(){map.invalidateSize()},60)}
    if(!map)loadLeaflet(function(){if(map)return;
      map=L.map(wrap.querySelector('#applivemap')).setView([40.10,64.68],12);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap'}).addTo(map);draw()});
    if(Date.now()-lastFetch>15000){lastFetch=Date.now();
      fetch('/api/app/track',{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(d){if(d){data=d;draw()}}).catch(function(){})}
  }catch(e){}}
  setInterval(tick,1000);
})();
</script>
'''


def main():
    sp, hp = os.path.join(D, 'server.py'), os.path.join(D, 'index.html')
    t = open(sp, encoding='utf-8').read()
    h = open(hp, encoding='utf-8').read()
    if '/api/app/loc' in t or 'applive-js' in h:
        sys.exit("Allaqachon o'rnatilgan - hech narsa o'zgarmadi.")
    anchors = list(re.finditer(r"^([ \t]*)if u\.path == '/api/me':[ \t]*$", t, re.M))
    if len(anchors) != 1:
        sys.exit("Mos kelmadi (server.py, /api/me: %d ta) - hech narsa o'zgarmadi." % len(anchors))
    a = anchors[0]
    classes = [m for m in re.finditer(r'^class \w+.*:[ \t]*$', t, re.M) if m.start() < a.start()]
    i = h.rfind('</body>')
    if not classes or i < 0:
        sys.exit("Mos kelmadi (class yoki </body> topilmadi) - hech narsa o'zgarmadi.")
    ind = a.group(1)
    route = ("%sif u.path == '/api/app/loc':\n%s    return _app_loc(self, u)\n"
             "%sif u.path == '/api/app/track':\n%s    return _app_track(self)\n") % (ind, ind, ind, ind)
    c = classes[-1].start()
    new_t = t[:c] + FUNC.lstrip('\n') + t[c:a.start()] + route + t[a.start():]
    new_h = h[:i] + HTML + h[i:]

    chk = '/tmp/chk_server.py'
    open(chk, 'w', encoding='utf-8').write(new_t)
    try:
        py_compile.compile(chk, doraise=True)
    except Exception as e:
        sys.exit("Xato: yangi server.py yaroqsiz (%s) - hech narsa o'zgarmadi." % e)

    stamp = time.strftime('%m%d-%H%M')
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
        print("Tayyor: ilova uchun qism o'rnatildi. CRM sahifasini yangilang.")
    else:
        for p in (sp, hp):
            shutil.copy2(p + '.bak-' + stamp, p)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayllar qaytarildi.")


main()
