#!/usr/bin/env python3
"""Toza Gilam CRM: smena avtomatik yopilishi (30 daqiqa faol bo'lmasa).

Nima qiladi:
  - Har bir xodimning oxirgi faolligini (CRM'ga oxirgi so'rovi) app_seen jadvalida saqlaydi.
  - Ochiq smenasi bor xodim 30 daqiqa hech qanday so'rov yubormasa (telefon o'chgan,
    joylashuv o'chiq, ilova yopilgan), smena oxirgi faollik vaqti bilan yopiladi
    va "avtomat" belgisi qo'yiladi.
  - Bir martalik tuzatish: 18 soatdan ortiq ochiq turgan smenalar ish kunining
    oxiri (21:00, Toshkent) bilan yopiladi. Boshqa vaqt kerak bo'lsa:
        FIX_OUT="2026-11-21 18:30" python3 install-smena-auto.py

Ishga tushirish (serverda, root):  python3 install-smena-auto.py
Avval zaxira nusxa oladi. Yangi versiya ishga tushmasa, eski faylni qaytaradi.
"""
import os, re, shutil, sqlite3, subprocess, sys, time, json, py_compile, urllib.request
from datetime import datetime, timedelta, timezone

D = os.environ.get('GILAM_DIR', '/opt/gilam-crm')
DATA = os.environ.get('CRM_DATA', '/var/lib/gilam-crm')
PORT = os.environ.get('GILAM_PORT', '8087')
TEST = bool(os.environ.get('GILAM_TEST'))
TZ = timezone(timedelta(hours=5))  # Toshkent

FUNC = r'''
# ---- smena-auto-v1: 30 daqiqa faol bo'lmagan xodimning smenasi yopiladi ----
SHIFT_IDLE_MIN = 30
_SEEN = {}
_SEEN_ST = {'sweep': 0, 'init': False}


def _seen_init(now):
    DB.execute('CREATE TABLE IF NOT EXISTS app_seen(sid TEXT PRIMARY KEY, t INTEGER)')
    # server qayta yoqilganda ochiq smenalarga 30 daqiqa muhlat beriladi
    for (d,) in DB.execute("SELECT data FROM docs WHERE coll='shift'").fetchall():
        try:
            s = json.loads(d)
        except Exception:
            continue
        if s.get('out') == 0 and s.get('sid'):
            DB.execute('INSERT INTO app_seen(sid,t) VALUES(?,?) ON CONFLICT(sid) DO UPDATE SET t=excluded.t',
                       (s['sid'], now))
    _SEEN_ST['init'] = True


def _shift_idle_sweep(now):
    seen = dict(DB.execute('SELECT sid,t FROM app_seen').fetchall())
    lim = SHIFT_IDLE_MIN * 60 * 1000
    for p, d in DB.execute("SELECT path,data FROM docs WHERE coll='shift'").fetchall():
        try:
            s = json.loads(d)
        except Exception:
            continue
        if s.get('out') != 0:
            continue
        last = max(int(s.get('in') or 0), int(seen.get(s.get('sid'), 0)) * 1000)
        if now * 1000 - last < lim:
            continue
        s['out'] = last
        s['auto'] = 1
        s['idle'] = 1
        put_doc(p, s)


def _seen_touch(sid):
    try:
        now = int(time.time())
        if not _SEEN_ST['init']:
            _seen_init(now)
        if now - _SEEN.get(sid, 0) >= 20:
            _SEEN[sid] = now
            DB.execute('INSERT INTO app_seen(sid,t) VALUES(?,?) ON CONFLICT(sid) DO UPDATE SET t=excluded.t',
                       (sid, now))
        if now - _SEEN_ST['sweep'] >= 60:
            _SEEN_ST['sweep'] = now
            _shift_idle_sweep(now)
        try:
            DB.commit()
        except Exception:
            pass
    except Exception:
        pass


'''


def patch_source(t):
    if '# ---- smena-auto-v1' in t:
        sys.exit("Allaqachon o'rnatilgan - hech narsa o'zgarmadi.")
    if not re.search(r'^def put_doc\(path, data\):', t, re.M):
        sys.exit("Mos kelmadi (put_doc topilmadi) - hech narsa o'zgarmadi.")
    m = re.search(r'(def auth\(self\):.*?\n)([ \t]+)return r\[0\], s\n', t, re.S)
    if not m or t.count('def auth(self):') != 1:
        sys.exit("Mos kelmadi (auth topilmadi) - hech narsa o'zgarmadi.")
    cls = re.search(r'^class \w+.*:[ \t]*\n', t, re.M)
    if not cls or cls.start() > m.start():
        sys.exit("Mos kelmadi (class topilmadi) - hech narsa o'zgarmadi.")
    ind = m.group(2)
    t = t[:m.start(2)] + ind + '_seen_touch(r[0])\n' + t[m.start(2):]
    return t[:cls.start()] + FUNC.lstrip('\n') + t[cls.start():]


def fix_stuck(db_path):
    """18 soatdan ortiq ochiq turgan smenalarni yopadi. Yopilganlar ro'yxatini qaytaradi."""
    out_env = os.environ.get('FIX_OUT')
    forced = None
    if out_env:
        forced = int(datetime.strptime(out_env, '%Y-%m-%d %H:%M').replace(tzinfo=TZ).timestamp() * 1000)
    c = sqlite3.connect(db_path, timeout=20)
    c.isolation_level = None
    done = []
    now = int(time.time() * 1000)
    c.execute('BEGIN IMMEDIATE')
    try:
        ver = int(c.execute("SELECT v FROM meta WHERE k='ver'").fetchone()[0])
        for p, d in c.execute("SELECT path,data FROM docs WHERE coll='shift'").fetchall():
            s = json.loads(d)
            if s.get('out') != 0 or now - int(s.get('in') or 0) < 18 * 3600 * 1000:
                continue
            t_in = int(s['in'])
            if forced:
                out = forced
            else:
                dt = datetime.fromtimestamp(t_in / 1000, TZ)
                out = int(dt.replace(hour=21, minute=0, second=0, microsecond=0).timestamp() * 1000)
            out = max(out, t_in + 60000)
            s['out'] = out
            s['auto'] = 1
            s['fix'] = 1
            ver += 1
            c.execute('UPDATE docs SET data=?, ver=? WHERE path=?',
                      (json.dumps(s, ensure_ascii=False, separators=(',', ':')), ver, p))
            c.execute('DELETE FROM tomb WHERE path=?', (p,))
            done.append((s.get('name', '?'), datetime.fromtimestamp(t_in / 1000, TZ).strftime('%d.%m %H:%M'),
                         datetime.fromtimestamp(out / 1000, TZ).strftime('%d.%m %H:%M')))
        c.execute("UPDATE meta SET v=? WHERE k='ver'", (str(ver),))
        c.execute('COMMIT')
    except Exception:
        c.execute('ROLLBACK')
        raise
    finally:
        c.close()
    return done


def main():
    sp = os.path.join(D, 'server.py')
    t = open(sp, encoding='utf-8').read()
    new_t = patch_source(t)
    chk = '/tmp/chk_server.py'
    open(chk, 'w', encoding='utf-8').write(new_t)
    try:
        py_compile.compile(chk, doraise=True)
    except Exception as e:
        sys.exit("Xato: yangi server.py yaroqsiz (%s) - hech narsa o'zgarmadi." % e)

    stamp = time.strftime('%m%d-%H%M%S')
    shutil.copy2(sp, sp + '.bak-' + stamp)
    db = os.path.join(DATA, 'crm.db')
    if os.path.exists(db) and not TEST:
        src = sqlite3.connect(db)
        dst = sqlite3.connect(db + '.bak-' + stamp)
        src.backup(dst)
        dst.close()
        src.close()
    open(sp, 'w', encoding='utf-8').write(new_t)

    if not TEST:
        subprocess.run(['systemctl', 'stop', 'gilam-crm'])
    fixed = []
    try:
        if os.path.exists(db):
            fixed = fix_stuck(db)
    except Exception as e:
        print("Ogohlantirish: eski smenalarni tuzatib bo'lmadi (%s)." % e)
    if TEST:
        print('TEST: fayl yozildi. Tuzatilgan smenalar:', fixed)
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
        for name, a, b in fixed:
            print('Tuzatildi: %s - keldi %s, ketdi %s' % (name, a, b))
        print("Tayyor: 30 daqiqa faol bo'lmagan xodimning smenasi o'zi yopiladi. CRM sahifasini yangilang.")
    else:
        shutil.copy2(sp + '.bak-' + stamp, sp)
        healthy()
        print("Xato: yangi versiya ishga tushmadi, eski fayl qaytarildi.")


main()
