#!/usr/bin/env python3
"""Toza Gilam AI ni serverga o'rnatadi (alohida xizmat: gilam-ai). Mavjud CRM va botga tegmaydi.
Ishga tushirish (serverda, root):  python3 install-ai.py
Kerak: 1) BotFather'dan YANGI bot tokeni  2) console.anthropic.com dan API kalit  3) sizning Telegram ID.
Qayta ishga tushirsangiz, eski qiymatlar saqlanadi (Enter bossangiz yetadi).
"""
import getpass, glob, json, os, py_compile, re, shutil, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_AI_DIR', '/opt/gilam-ai')
BASE = os.environ.get('GILAM_AI_URL', 'https://raw.githubusercontent.com/alisherjon199579-hash/toza-gilam-app/2fd187a1ca3feb4cbf8bbc189d31a335bd55ff5e/server/')
TEST = bool(os.environ.get('GILAM_AI_TEST'))
SRC = os.environ.get('GILAM_AI_SRC')          # mahalliy fayl (sinov uchun)

KB = """BIZNES: Toza Gilam - gilam yuvish xizmati.
MANZIL: Gijduvon tumani, Sarvarida.
ISH VAQTI: 08:00-21:00.
TELEFON: +998 91 921 37 89
INSTAGRAM: instagram.com/gilam_yuvish_korxonasii
YETKAZIB BERISH: bepul (olib ketamiz va olib kelamiz).
MUDDAT: buyurtma 6-7 kunda tayyor bo'ladi.
NARXLAR (so'm):
- Gilam: 1 m2 = 12 000
- Adyol: 60 000
- Ko'rpa: 70 000
- Ko'rpacha: 2 m - 40 000; 2,5 m - 45 000; 3 m - 50 000
- Yostiq: 30 000
CHEGIRMA: har bir buyurtmaga alohida foiz bilan beriladi (rahbar belgilaydi).
TO'LOV: naqd yoki karta orqali, yetkazib berilganda.
"""


def run(*a, **k):
    return subprocess.run(a, capture_output=True, text=True, **k)


def old_env():
    e = {}
    p = os.path.join(D, '.env')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            if '=' in l:
                k, v = l.rstrip('\n').split('=', 1)
                e[k] = v
    return e


def ask(label, key, env, secret=False):
    cur = env.get(key, '')
    shown = ('...' + cur[-4:]) if (cur and secret) else cur
    prompt = '%s%s: ' % (label, ' [%s]' % shown if cur else '')
    v = (getpass.getpass(prompt) if secret else input(prompt)).strip()
    return v or cur


def get(url, data=None, headers=None):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers or {}), timeout=30).read())


def main():
    if os.geteuid() != 0 and not TEST:
        sys.exit('root sifatida ishga tushiring.')
    os.makedirs(D, exist_ok=True)
    tgt = os.path.join(D, 'gilam-ai.py')
    if SRC:
        shutil.copy(SRC, tgt)
    else:
        try:
            open(tgt + '.new', 'wb').write(urllib.request.urlopen(BASE + 'gilam-ai.py', timeout=30).read())
            os.replace(tgt + '.new', tgt)
        except Exception as e:
            sys.exit("gilam-ai.py ni yuklab bo'lmadi: %s" % e)
    try:
        py_compile.compile(tgt, doraise=True)
    except Exception as e:
        sys.exit('Fayl yaroqsiz: %s' % e)
    env = old_env()
    print("\nToza Gilam AI sozlamalari (eski qiymat bo'lsa, Enter bossangiz saqlanadi)\n")
    env['BOT_TOKEN'] = ask('1) Yangi bot tokeni (BotFather)', 'BOT_TOKEN', env)
    env['ANTHROPIC_API_KEY'] = ask('2) Anthropic API kalit (sk-ant-...)', 'ANTHROPIC_API_KEY', env, True)
    env['ADMIN_ID'] = ask("3) Sizning Telegram ID (bilmasangiz bo'sh qoldiring)", 'ADMIN_ID', env)
    dbs = glob.glob('/var/lib/gilam-crm/crm.db') + glob.glob('/var/lib/*/crm.db')
    env.setdefault('CRM_DB', dbs[0] if dbs else '/var/lib/gilam-crm/crm.db')
    env['CRM_DB'] = ask('4) Toza Gilam CRM bazasi fayli', 'CRM_DB', env)
    env.setdefault('REPORT_AT', '21:30')
    if not os.path.exists(env['CRM_DB']):
        print("Ogohlantirish: %s topilmadi - CRM savol-javobi ishlamaydi (qolganlari ishlaydi)." % env['CRM_DB'])
    if not TEST:
        try:
            me = get('https://api.telegram.org/bot%s/getMe' % env['BOT_TOKEN'])
            print('Bot topildi: @%s' % me['result']['username'])
        except Exception:
            sys.exit("Bot tokeni noto'g'ri. Hech narsa o'zgarmadi.")
        try:
            get('https://api.anthropic.com/v1/messages', json.dumps({'model': 'claude-sonnet-5-5', 'max_tokens': 5,
                'messages': [{'role': 'user', 'content': 'salom'}]}).encode(),
                {'x-api-key': env['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
            print('AI kalit ishlayapti.')
        except Exception as e:
            sys.exit("AI kalit ishlamadi (%s). Kalit va hisobdagi mablag'ni tekshiring. Hech narsa o'zgarmadi." % e)
    p = os.path.join(D, '.env')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(''.join('%s=%s\n' % kv for kv in env.items()))
    os.chmod(p, 0o600)
    kp = os.path.join(D, 'bilim.txt')
    if not os.path.exists(kp):
        open(kp, 'w', encoding='utf-8').write(KB)
    unit = """[Unit]
Description=Toza Gilam AI bot
After=network-online.target

[Service]
WorkingDirectory=%s
ExecStart=/usr/bin/python3 %s
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
""" % (D, tgt)
    if TEST:
        print('TEST: o\'rnatish tugadi (systemd o\'tkazib yuborildi).')
        return
    open('/etc/systemd/system/gilam-ai.service', 'w').write(unit)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'gilam-ai')
    run('systemctl', 'restart', 'gilam-ai')
    time.sleep(4)
    st = run('systemctl', 'is-active', 'gilam-ai').stdout.strip()
    if st != 'active':
        print(run('journalctl', '-u', 'gilam-ai', '-n', '15', '--no-pager').stdout)
        sys.exit('Xizmat ishga tushmadi (yuqoridagi xatoga qarang).')
    print("\nTayyor! Telegram'da yangi botingizga /start yozing.")
    if not env.get('ADMIN_ID'):
        print("ADMIN_ID bo'sh: botga /id yozing, chiqqan raqamni %s/.env faylidagi ADMIN_ID= ga yozib, 'systemctl restart gilam-ai' qiling." % D)
    print("Bilim bazasi (narx va qoidalar): %s/bilim.txt - o'zgartirib 'systemctl restart gilam-ai' qiling." % D)


if __name__ == '__main__':
    main()
