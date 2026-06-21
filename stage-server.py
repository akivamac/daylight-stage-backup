#!/data/data/com.termux/files/usr/bin/env python3
"""
Stage backup server (multi-project).

Run in Termux:
    python stage-server.py

Open in Brave:
    http://localhost:8765/         (legacy single-project page)
    http://localhost:8765/2        (multi-project page, serves stage2.html)

Storage:
    ~/stage-backups/
        latest.json                          (legacy single)
        snap-YYYYMMDD-HHMMSS.json            (legacy snapshots)
        projects/<project>/latest.json
        projects/<project>/snap-YYYYMMDD-HHMMSS.json
"""
import http.server, json, os, re, time, urllib.parse
from datetime import datetime

PORT = 8765
HOME = os.path.expanduser('~')
BACKUP_DIR = os.path.join(HOME, 'stage-backups')
PROJECTS_DIR = os.path.join(BACKUP_DIR, 'projects')
LATEST = os.path.join(BACKUP_DIR, 'latest.json')
KEEP_HISTORY = 20
SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9 _\-\.]+$')
HERE = os.path.dirname(os.path.abspath(__file__))

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(PROJECTS_DIR, exist_ok=True)

PMS_DIR = os.path.join(BACKUP_DIR, 'pms')
os.makedirs(PMS_DIR, exist_ok=True)


def pms_file(name):
    return os.path.join(PMS_DIR, name + '.json')


def list_pms():
    if not os.path.isdir(PMS_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(PMS_DIR)):
        if not fn.endswith('.json'):
            continue
        full = os.path.join(PMS_DIR, fn)
        out.append({
            'name': fn[:-5],
            'updated': os.path.getmtime(full) if os.path.exists(full) else None,
        })
    return out


def safe_project(name):
    name = (name or '').strip()
    if not name or not SAFE_NAME_RE.match(name) or len(name) > 64:
        return None
    return name


def project_dir(name):
    return os.path.join(PROJECTS_DIR, name)


def list_projects():
    if not os.path.isdir(PROJECTS_DIR):
        return []
    out = []
    for n in sorted(os.listdir(PROJECTS_DIR)):
        d = project_dir(n)
        if not os.path.isdir(d):
            continue
        latest = os.path.join(d, 'latest.json')
        out.append({
            'name': n,
            'updated': os.path.getmtime(latest) if os.path.exists(latest) else None,
        })
    return out


class Handler(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code); self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        if not os.path.exists(path):
            self.send_response(404); self._cors(); self.end_headers()
            self.wfile.write(f'{path} not found'.encode()); return
        with open(path, 'rb') as f: data = f.read()
        self.send_response(200); self._cors()
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        path = self.path.split('?', 1)[0]

        if path == '/' or path == '/stage.html':
            return self._send_file(os.path.join(HERE, 'stage.html'), 'text/html; charset=utf-8')
        if path == '/2' or path == '/stage2.html':
            return self._send_file(os.path.join(HERE, 'stage2.html'), 'text/html; charset=utf-8')

        if path == '/ping':
            self.send_response(200); self._cors()
            self.send_header('Content-Type', 'text/plain'); self.end_headers()
            self.wfile.write(b'ok'); return

        if path == '/latest':
            if os.path.exists(LATEST):
                return self._send_file(LATEST, 'application/json')
            self.send_response(204); self._cors(); self.end_headers(); return

        if path == '/projects':
            return self._json(200, {'projects': list_projects()})

        if path == '/pms':
            return self._json(200, {'pms': list_pms()})

        m = re.match(r'^/pms/([^/]+)$', path)
        if m:
            name = safe_project(urllib.parse.unquote(m.group(1)))
            if not name: return self._json(400, {'error': 'bad pms name'})
            f = pms_file(name)
            if not os.path.exists(f):
                self.send_response(204); self._cors(); self.end_headers(); return
            return self._send_file(f, 'application/json')

        m = re.match(r'^/project/([^/]+)/load$', path)
        if m:
            name = safe_project(urllib.parse.unquote(m.group(1)))
            if not name: return self._json(400, {'error': 'bad project name'})
            f = os.path.join(project_dir(name), 'latest.json')
            if not os.path.exists(f):
                self.send_response(204); self._cors(); self.end_headers(); return
            return self._send_file(f, 'application/json')

        self.send_response(404); self._cors(); self.end_headers()

    def do_POST(self):
        path = self.path.split('?', 1)[0]
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b''

        if path == '/save':
            try: json.loads(body)
            except Exception as e:
                return self._json(400, {'error': f'bad json: {e}'})
            with open(LATEST, 'wb') as f: f.write(body)
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            with open(os.path.join(BACKUP_DIR, f'snap-{ts}.json'), 'wb') as f: f.write(body)
            self._prune(BACKUP_DIR, 'snap-')
            return self._json(200, {'ok': True})

        if path == '/project/new':
            try: req = json.loads(body or b'{}')
            except: req = {}
            name = safe_project(req.get('name'))
            if not name:
                return self._json(400, {'error': 'name required (letters/numbers/space/_-., max 64)'})
            d = project_dir(name)
            if os.path.exists(d):
                return self._json(409, {'error': 'project already exists'})
            os.makedirs(d, exist_ok=True)
            empty = json.dumps({'_kind': 'stage-project', '_version': 1,
                                'savedAt': datetime.now().isoformat(),
                                'workspace': {}}).encode()
            with open(os.path.join(d, 'latest.json'), 'wb') as f: f.write(empty)
            return self._json(200, {'ok': True, 'project': name})

        if path == '/project/delete':
            try: req = json.loads(body or b'{}')
            except: req = {}
            name = safe_project(req.get('name'))
            if not name: return self._json(400, {'error': 'bad name'})
            d = project_dir(name)
            if not os.path.exists(d): return self._json(404, {'error': 'not found'})
            trash = os.path.join(BACKUP_DIR, 'trash')
            os.makedirs(trash, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            os.rename(d, os.path.join(trash, f'{name}-{stamp}'))
            return self._json(200, {'ok': True})

        m = re.match(r'^/project/([^/]+)/save$', path)
        if m:
            name = safe_project(urllib.parse.unquote(m.group(1)))
            if not name: return self._json(400, {'error': 'bad project name'})
            try: json.loads(body)
            except Exception as e:
                return self._json(400, {'error': f'bad json: {e}'})
            d = project_dir(name)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'latest.json'), 'wb') as f: f.write(body)
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            with open(os.path.join(d, f'snap-{ts}.json'), 'wb') as f: f.write(body)
            self._prune(d, 'snap-')
            return self._json(200, {'ok': True, 'project': name})

        m = re.match(r'^/pms/([^/]+)/save$', path)
        if m:
            name = safe_project(urllib.parse.unquote(m.group(1)))
            if not name: return self._json(400, {'error': 'bad pms name'})
            try: json.loads(body)
            except Exception as e:
                return self._json(400, {'error': f'bad json: {e}'})
            with open(pms_file(name), 'wb') as f: f.write(body)
            return self._json(200, {'ok': True, 'pms': name})

        if path == '/pms/new':
            try: req = json.loads(body or b'{}')
            except: req = {}
            name = safe_project(req.get('name'))
            if not name:
                return self._json(400, {'error': 'name required'})
            f = pms_file(name)
            if os.path.exists(f):
                return self._json(409, {'error': 'pms already exists'})
            empty = json.dumps({'name': name, 'workspace': {}, 'ops': []}).encode()
            with open(f, 'wb') as fh: fh.write(empty)
            return self._json(200, {'ok': True, 'pms': name})

        if path == '/pms/delete':
            try: req = json.loads(body or b'{}')
            except: req = {}
            name = safe_project(req.get('name'))
            if not name: return self._json(400, {'error': 'bad name'})
            f = pms_file(name)
            if not os.path.exists(f): return self._json(404, {'error': 'not found'})
            trash = os.path.join(BACKUP_DIR, 'trash')
            os.makedirs(trash, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            os.rename(f, os.path.join(trash, f'pms-{name}-{stamp}.json'))
            return self._json(200, {'ok': True})

        self.send_response(404); self._cors(); self.end_headers()

    def _prune(self, d, prefix):
        snaps = sorted(p for p in os.listdir(d) if p.startswith(prefix))
        for old in snaps[:-KEEP_HISTORY]:
            try: os.remove(os.path.join(d, old))
            except: pass

    def log_message(self, fmt, *args):
        print(f'[{time.strftime("%H:%M:%S")}] {fmt % args}')


if __name__ == '__main__':
    print('Stage backup server (multi-project)')
    print(f'  Storing in: {BACKUP_DIR}')
    print(f'  Listening:  http://localhost:{PORT}')
    print(f'  Pages:      /  (legacy single)   /2  (multi-project)')
    print(f'  Ctrl+C to stop')
    http.server.HTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
