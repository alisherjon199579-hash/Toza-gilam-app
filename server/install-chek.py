#!/usr/bin/env python3
"""Kassa terminalidan chek chiqarish xizmatini serverga o'rnatadi. CRM va botlarga tegmaydi.
Ishga tushirish (serverda, root):  python3 install-chek.py
Oxirida terminal dasturiga kiritiladigan server manzili va kalit chiqadi.
"""
import os, secrets, shutil, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_CHEK_DIR', '/opt/gilam-chek')
PORT = os.environ.get('GILAM_CHEK_PORT', '8090')
BASE = os.environ.get('GILAM_CHEK_URL', 'https://raw.githubusercontent.com/alisherjon199579-hash/toza-gilam-app/ef2ff998ddbe159283d2ca87f3320e6adc31e1e8/server/')
TEST = bool(os.environ.get('GILAM_CHEK_TEST'))
SRC = os.environ.get('GILAM_CHEK_SRC')


def run(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def main():
    if os.geteuid() != 0 and not TEST:
        sys.exit('root sifatida ishga tushiring.')
    if not TEST and not os.path.exists('/var/lib/gilam-crm/crm.db'):
        sys.exit("CRM bazasi topilmadi (/var/lib/gilam-crm/crm.db).")
    os.makedirs(D, exist_ok=True)
    t = os.path.join(D, 'gilam-chek.py')
    try:
        if SRC:
            shutil.copy(os.path.join(SRC, 'gilam-chek.py'), t)
        else:
            open(t + '.new', 'wb').write(urllib.request.urlopen(BASE + 'gilam-chek.py', timeout=40).read())
            os.replace(t + '.new', t)
    except Exception as e:
        sys.exit("Faylni yuklab bo'lmadi: %s" % e)
    envp = os.path.join(D, '.env')
    tok = ''
    if os.path.exists(envp):
        for l in open(envp):
            if l.startswith('TOKEN='):
                tok = l.strip().split('=', 1)[1]
    tok = tok or secrets.token_hex(6)
    open(envp, 'w').write('TOKEN=%s\nPORT=%s\n' % (tok, PORT))
    os.chmod(envp, 0o600)
    unit = """[Unit]
Description=Toza Gilam chek xizmati
After=network-online.target

[Service]
WorkingDirectory=%s
ExecStart=%s %s/gilam-chek.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
""" % (D, sys.executable, D)
    ip = ''
    try:
        ip = run('hostname', '-I').stdout.split()[0]
    except Exception:
        pass
    if TEST:
        print('TEST tugadi. TOKEN=%s' % tok)
        return
    open('/etc/systemd/system/gilam-chek.service', 'w').write(unit)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'gilam-chek')
    run('systemctl', 'restart', 'gilam-chek')
    fw = run('ufw', 'status').stdout
    if 'active' in fw and 'inactive' not in fw:
        run('ufw', 'allow', PORT + '/tcp')
    time.sleep(3)
    if run('systemctl', 'is-active', 'gilam-chek').stdout.strip() != 'active':
        print(run('journalctl', '-u', 'gilam-chek', '-n', '15', '--no-pager').stdout)
        sys.exit('Xizmat ishga tushmadi.')
    try:
        ok = urllib.request.urlopen('http://127.0.0.1:%s/ping?k=%s' % (PORT, tok), timeout=5).status == 200
    except Exception:
        ok = False
    print('\nTayyor!' if ok else '\nOgohlantirish: xizmat javob bermadi.')
    print('Terminaldagi "Toza Gilam Chek" dasturiga kiriting:')
    print('  Server manzili:  http://%s:%s' % (ip or 'SERVER_IP', PORT))
    print('  Kalit:           %s' % tok)
    print("Agar terminal ulana olmasa, hosting panelida (firewall) %s portini oching." % PORT)


if __name__ == '__main__':
    main()
