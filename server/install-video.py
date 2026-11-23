#!/usr/bin/env python3
"""Video Studio (avtomatik ayol/erkak ovozi) ni serverga o'rnatadi. Mavjud CRM va botlarga tegmaydi.
Ishga tushirish (serverda, root):  python3 install-video.py
Ovozlar: Microsoft edge-tts (uz-UZ-MadinaNeural - ayol, uz-UZ-SardorNeural - erkak; rus tili ham bor). Kalit kerak emas.
"""
import os, secrets, shutil, socket, subprocess, sys, time, urllib.request

D = os.environ.get('GILAM_VIDEO_DIR', '/opt/gilam-video')
PORT = os.environ.get('GILAM_VIDEO_PORT', '8095')
BASE = os.environ.get('GILAM_VIDEO_URL', 'https://raw.githubusercontent.com/alisherjon199579-hash/toza-gilam-app/1a768dc623c34c6df6eba9db467b66869e0ce592/server/')
TEST = bool(os.environ.get('GILAM_VIDEO_TEST'))
SRC = os.environ.get('GILAM_VIDEO_SRC')


def run(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def main():
    if os.geteuid() != 0 and not TEST:
        sys.exit('root sifatida ishga tushiring.')
    os.makedirs(D, exist_ok=True)
    for f in ('gilam-video.py', 'video-index.html'):
        t = os.path.join(D, f)
        try:
            if SRC:
                shutil.copy(os.path.join(SRC, f), t)
            else:
                open(t + '.new', 'wb').write(urllib.request.urlopen(BASE + f, timeout=40).read())
                os.replace(t + '.new', t)
        except Exception as e:
            sys.exit("%s ni yuklab bo'lmadi: %s" % (f, e))
    if not TEST:
        r = run(sys.executable, '-c', 'import edge_tts')
        if r.returncode != 0:
            print('edge-tts o\'rnatilmoqda…')
            r = run('pip3', 'install', '--break-system-packages', '-q', 'edge-tts')
            if r.returncode != 0:
                run('apt-get', 'install', '-y', 'python3-pip')
                r = run('pip3', 'install', '--break-system-packages', '-q', 'edge-tts')
            if r.returncode != 0:
                sys.exit("edge-tts o'rnatilmadi:\n" + r.stderr[-400:])
        print('Ovoz sinovi (ayol va erkak)…')
        for v in ('uz-UZ-MadinaNeural', 'uz-UZ-SardorNeural'):
            fp = '/tmp/_vt_%s.mp3' % v[:11]
            r = run(sys.executable, '-c',
                    'import asyncio,edge_tts;asyncio.run(edge_tts.Communicate("Assalomu alaykum, Toza Gilam.","%s").save("%s"))' % (v, fp), timeout=90)
            if r.returncode != 0 or not os.path.exists(fp) or os.path.getsize(fp) < 1000:
                sys.exit("Ovoz xizmatiga ulanib bo'lmadi (%s). Internetni tekshiring.\n%s" % (v, r.stderr[-300:]))
            os.remove(fp)
        print('Ikkala ovoz ishlayapti.')
    envp = os.path.join(D, '.env')
    tok = ''
    if os.path.exists(envp):
        for l in open(envp):
            if l.startswith('TOKEN='):
                tok = l.strip().split('=', 1)[1]
    tok = tok or secrets.token_hex(8)
    open(envp, 'w').write('TOKEN=%s\nPORT=%s\n' % (tok, PORT))
    os.chmod(envp, 0o600)
    unit = """[Unit]
Description=Toza Gilam Video Studio
After=network-online.target

[Service]
WorkingDirectory=%s
ExecStart=%s %s/gilam-video.py
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
    open('/etc/systemd/system/gilam-video.service', 'w').write(unit)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'gilam-video')
    run('systemctl', 'restart', 'gilam-video')
    if 'active' in run('ufw', 'status').stdout and 'inactive' not in run('ufw', 'status').stdout:
        run('ufw', 'allow', PORT + '/tcp')
    time.sleep(3)
    if run('systemctl', 'is-active', 'gilam-video').stdout.strip() != 'active':
        print(run('journalctl', '-u', 'gilam-video', '-n', '15', '--no-pager').stdout)
        sys.exit('Xizmat ishga tushmadi.')
    print('\nTayyor! Telefon brauzerida oching (manzilni boshqalarga bermang):')
    print('  http://%s:%s/%s/' % (ip or 'SERVER_IP', PORT, tok))
    print("Agar ochilmasa, hosting panelida (firewall) %s portini oching." % PORT)


if __name__ == '__main__':
    main()
