#!/usr/bin/env python3
"""Toza Gilam: kassa terminalidan chek chiqarish xizmati.

CRM'da dostavchik "Yetkazildi" bosganda zakaz holati 'delivered' bo'ladi. Bu xizmat shuni topadi,
chek matnini tayyorlaydi va terminaldagi "Toza Gilam Chek" dasturiga beradi (u printerda chiqaradi).
CRM fayllariga TEGMAYDI: faqat crm.db'ni o'qiydi (read-only). O'z holatini alohida faylda saqlaydi.
Terminal dasturi shu manzilga murojaat qiladi:  http://SERVER:PORT/next?k=KALIT
"""
import hmac, http.server, json, os, socketserver, sqlite3, threading, time, urllib.parse
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = {}
_p = os.path.join(HERE, '.env')
if os.path.exists(_p):
    for _l in open(_p, encoding='utf-8'):
        if '=' in _l:
            _k, _v = _l.rstrip('\n').split('=', 1)
            ENV[_k] = _v
PORT = int(os.environ.get('CHEK_PORT') or ENV.get('PORT', '8090'))
TOKEN = os.environ.get('CHEK_TOKEN') or ENV.get('TOKEN', '')
CRM_DB = os.environ.get('CRM_DB') or os.path.join(os.environ.get('CRM_DATA', '/var/lib/gilam-crm'), 'crm.db')
ST_DB = os.environ.get('CHEK_STATE') or os.path.join(HERE, 'chek-state.db')
SHOP = os.environ.get('CHEK_SHOP', 'TOZA GILAM')
PHONE = os.environ.get('CHEK_PHONE', '+998 91 921 37 89')
TZ = timezone(timedelta(hours=5))
W = 32
LOCK = threading.Lock()


def st():
    c = sqlite3.connect(ST_DB, timeout=20)
    c.execute('CREATE TABLE IF NOT EXISTS jobs(path TEXT, kind TEXT, lines TEXT, state TEXT, tries INTEGER, at INTEGER, PRIMARY KEY(path,kind))')
    c.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)')
    return c


def money(n):
    try:
        return '{:,}'.format(int(round(float(n)))).replace(',', ' ')
    except Exception:
        return str(n)


def num(v):
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else ('%.2f' % f).rstrip('0').rstrip('.')
    except Exception:
        return str(v)


def deliver_time(o):
    t = 0
    for e in o.get('log') or []:
        if isinstance(e, dict) and e.get('st') == 'delivered':
            try:
                t = max(t, int(e.get('t') or 0))
            except Exception:
                pass
    if t and t < 10 ** 11:
        t *= 1000
    return t


def L(t, s=2, p='left', b=0):
    return {'t': t, 's': s, 'p': p, 'b': b}


def wrap(t, w=W):
    t = str(t)
    return [t[i:i + w] for i in range(0, len(t), w)] or ['']


def build(o, no_label=None):
    ts = deliver_time(o) or int(time.time() * 1000)
    dt = datetime.fromtimestamp(ts / 1000, TZ).strftime('%d.%m.%Y %H:%M')
    lines = [L(SHOP, 3, 'center', 1), L('Gilam yuvish xizmati', 2, 'center'), L('-' * W)]
    lines.append(L('Zakaz #%s' % o.get('no', '?')))
    lines.append(L(dt))
    if o.get('name'):
        for x in wrap('Mijoz: %s' % o['name']):
            lines.append(L(x))
    lines.append(L('-' * W))
    sub = 0
    for it in o.get('items') or []:
        if not isinstance(it, dict):
            continue
        for x in wrap(it.get('name', '?')):
            lines.append(L(x))
        unit = it.get('unit') or ''
        q = it.get('qty') if it.get('qty') not in (None, '', 0) else it.get('count', 1)
        s = it.get('sum', 0) or 0
        sub += s
        row = '%s %s x %s = %s' % (num(q), unit, money(it.get('price', 0)), money(s))
        for x in wrap(row.replace('  ', ' ')):
            lines.append(L('  ' + x if len(x) < W - 2 else x))
    total = o.get('total', sub) or 0
    lines.append(L('-' * W))
    if sub and sub > total:
        if o.get('discM') and o.get('disc'):
            lines.append(L('Chegirma %s%%: -%s' % (num(o['disc']), money(sub - total))))
        else:
            lines.append(L('Chegirma: -%s' % money(sub - total)))
    lines.append(L('JAMI: %s som' % money(total), 3, 'left', 1))
    paid_sum = o.get('paidSum') or 0
    if o.get('paid'):
        lines.append(L("To'landi"))
    elif paid_sum:
        lines.append(L("To'langan: %s" % money(paid_sum)))
        lines.append(L('Qoldi: %s' % money(total - paid_sum)))
    lines.append(L('-' * W))
    lines.append(L('Rahmat! Tel: %s' % PHONE, 2, 'center'))
    lines.append(L('Hisob-kvitansiya (fiskal emas)', 1, 'center'))
    return lines


def crm():
    c = sqlite3.connect('file:%s?mode=ro' % CRM_DB, uri=True, timeout=10)
    return c


def scan():
    s = st()
    base = s.execute("SELECT v FROM meta WHERE k='baseline'").fetchone()
    c = crm()
    rows = c.execute("SELECT path,data FROM docs WHERE coll='orders'").fetchall()
    c.close()
    now = int(time.time())
    if not base:
        # birinchi ishga tushishda eski yetkazilganlar uchun chek chiqmasin
        for p, d in rows:
            try:
                o = json.loads(d)
            except Exception:
                continue
            if o.get('status') == 'delivered':
                s.execute("INSERT OR IGNORE INTO jobs VALUES(?,?,?,?,?,?)", (p, 'auto', '[]', 'old', 0, now))
        s.execute("INSERT OR REPLACE INTO meta VALUES('baseline',?)", (str(now),))
        s.commit()
        s.close()
        return
    for p, d in rows:
        try:
            o = json.loads(d)
        except Exception:
            continue
        if o.get('status') != 'delivered':
            continue
        if s.execute("SELECT 1 FROM jobs WHERE path=? AND kind='auto'", (p,)).fetchone():
            continue
        s.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?)", (p, 'auto', json.dumps(build(o), ensure_ascii=False), 'pending', 0, now))
    s.commit()
    s.close()


def scanner():
    while True:
        try:
            with LOCK:
                scan()
        except Exception as e:
            print('scan xato:', e, flush=True)
        time.sleep(3)


def reprint(no):
    c = crm()
    for p, d in c.execute("SELECT path,data FROM docs WHERE coll='orders'"):
        try:
            o = json.loads(d)
        except Exception:
            continue
        if str(o.get('no')) == str(no):
            c.close()
            s = st()
            s.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?,?)",
                      (p, 'again', json.dumps(build(o), ensure_ascii=False), 'pending', 0, int(time.time())))
            s.commit()
            s.close()
            return True
    c.close()
    return False


def next_job():
    s = st()
    now = int(time.time())
    r = s.execute("SELECT path,kind,lines FROM jobs WHERE (state='pending') OR (state='sent' AND at<? AND tries<3) ORDER BY at LIMIT 1", (now - 60,)).fetchone()
    if not r:
        s.close()
        return None
    s.execute("UPDATE jobs SET state='sent', tries=tries+1, at=? WHERE path=? AND kind=?", (now, r[0], r[1]))
    s.commit()
    s.close()
    return {'id': r[0] + '|' + r[1], 'lines': json.loads(r[2])}


def finish(jid, ok, err=''):
    p, _, k = jid.rpartition('|')
    s = st()
    if ok:
        s.execute("UPDATE jobs SET state='done' WHERE path=? AND kind=?", (p, k))
    else:
        s.execute("UPDATE jobs SET state=CASE WHEN tries>=3 THEN 'failed' ELSE 'pending' END, at=? WHERE path=? AND kind=?", (int(time.time()) + 20, p, k))
        print('chek xatosi %s: %s' % (jid, err), flush=True)
    s.commit()
    s.close()


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body=b'', ctype='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if not TOKEN or not hmac.compare_digest(q.get('k', ''), TOKEN):
            return self.send(403, b'{}')
        try:
            if u.path == '/next':
                j = next_job()
                return self.send(200, json.dumps(j, ensure_ascii=False).encode('utf-8')) if j else self.send(204)
            if u.path == '/ok':
                finish(q.get('id', ''), True)
                return self.send(200, b'{}')
            if u.path == '/fail':
                finish(q.get('id', ''), False, q.get('e', ''))
                return self.send(200, b'{}')
            if u.path == '/chek':
                ok = reprint(q.get('no', ''))
                return self.send(200 if ok else 404, ('Navbatga qo\'yildi' if ok else 'Zakaz topilmadi').encode('utf-8'), 'text/plain; charset=utf-8')
            if u.path == '/ping':
                return self.send(200, b'{"ok":1}')
        except Exception as e:
            print('so\'rov xatosi:', e, flush=True)
            return self.send(500, b'{}')
        self.send(404, b'{}')


class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    threading.Thread(target=scanner, daemon=True).start()
    print('gilam-chek ishga tushdi, port %d' % PORT, flush=True)
    S(('0.0.0.0', PORT), H).serve_forever()
