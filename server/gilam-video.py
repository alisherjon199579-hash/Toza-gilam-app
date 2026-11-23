#!/usr/bin/env python3
"""Video Studio serveri: sahifani beradi va matnni ayol/erkak ovozida o'qib (Microsoft edge-tts) audio qaytaradi.
Manzil: http://SERVER:PORT/TOKEN/   (TOKEN .env faylida; boshqalar kira olmaydi)."""
import asyncio, hashlib, hmac, http.server, json, os, socketserver, sys, tempfile, threading, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = {}
p = os.path.join(HERE, '.env')
if os.path.exists(p):
    for l in open(p, encoding='utf-8'):
        if '=' in l:
            k, v = l.rstrip('\n').split('=', 1)
            ENV[k] = v
PORT = int(os.environ.get('VIDEO_PORT') or ENV.get('PORT', '8095'))
TOKEN = os.environ.get('VIDEO_TOKEN') or ENV.get('TOKEN', '')
CACHE = os.path.join(HERE, 'cache')
os.makedirs(CACHE, exist_ok=True)
VOICES = {('uz', 'f'): 'uz-UZ-MadinaNeural', ('uz', 'm'): 'uz-UZ-SardorNeural',
          ('ru', 'f'): 'ru-RU-SvetlanaNeural', ('ru', 'm'): 'ru-RU-DmitryNeural'}
RATES = {'-10%', '+0%', '+10%'}
LOCK = threading.Lock()
HITS = []


async def _synth(text, voice, rate, path):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


def synth(text, voice, rate):
    key = hashlib.sha1(('%s|%s|%s' % (voice, rate, text)).encode('utf-8')).hexdigest()
    fp = os.path.join(CACHE, key + '.mp3')
    if os.path.exists(fp) and os.path.getsize(fp) > 200:
        return open(fp, 'rb').read()
    tmp = fp + '.%d.tmp' % threading.get_ident()
    asyncio.run(_synth(text, voice, rate, tmp))
    if not os.path.exists(tmp) or os.path.getsize(tmp) < 200:
        raise RuntimeError('ovoz bo\'sh chiqdi')
    os.replace(tmp, fp)
    return open(fp, 'rb').read()


def limited():
    now = time.time()
    with LOCK:
        HITS[:] = [t for t in HITS if now - t < 60]
        if len(HITS) >= 60:
            return True
        HITS.append(now)
    return False


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def out(self, code, body, ctype='text/plain; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        parts = [x for x in u.path.split('/') if x != '']
        if not TOKEN or not parts or not hmac.compare_digest(parts[0], TOKEN):
            return self.out(404, 'Topilmadi')
        sub = '/'.join(parts[1:])
        q = urllib.parse.parse_qs(u.query)
        if sub == '':
            if not u.path.endswith('/'):
                self.send_response(301)
                self.send_header('Location', u.path + '/')
                self.end_headers()
                return
            return self.out(200, open(os.path.join(HERE, 'video-index.html'), 'rb').read(), 'text/html; charset=utf-8')
        if sub == 'tts':
            if q.get('ping'):
                return self.out(200, json.dumps({'ok': True}), 'application/json')
            text = (q.get('t', [''])[0]).strip()
            voice = VOICES.get((q.get('l', ['uz'])[0], q.get('v', ['f'])[0]))
            rate = q.get('r', ['+0%'])[0]
            if rate not in RATES:
                rate = '+0%'
            if not text or len(text) > 600 or not voice:
                return self.out(400, 'Noto\'g\'ri so\'rov')
            if limited():
                return self.out(429, 'Ko\'p so\'rov')
            try:
                data = synth(text, voice, rate)
            except Exception as e:
                sys.stderr.write('TTS xato: %r\n' % (e,))
                return self.out(502, 'Ovoz xizmati javob bermadi')
            return self.out(200, data, 'audio/mpeg')
        return self.out(404, 'Topilmadi')


class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    if not TOKEN:
        sys.exit('TOKEN yo\'q (.env)')
    print('Video Studio: port %d' % PORT, flush=True)
    S(('0.0.0.0', PORT), H).serve_forever()
