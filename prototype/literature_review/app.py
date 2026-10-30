"""Local-only HTTP application. Run: python app.py"""
import base64
import copy
import io
import json
import os
import re
import secrets
import threading
import urllib.parse
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pymupdf
from core import apply_edits, demo_pdf, paper_record, workbook

ROOT = Path(__file__).resolve().parent
RUNS = OrderedDict()
LOCK = threading.Lock()
TOKEN = secrets.token_urlsafe(32)


def retain(papers):
    run_id = secrets.token_urlsafe(24)
    with LOCK:
        RUNS[run_id] = papers
        while len(RUNS) > 5: RUNS.popitem(last=False)
    return run_id


def public_papers(papers):
    return [{k: v for k, v in p.items() if k not in ['pdf', 'raw_output']} for p in papers]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Never log uploaded names, text, credentials or source URLs.

    def send(self, data, content_type='application/json', status=200, filename=None):
        if not isinstance(data, bytes): data = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        if filename: self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def get_run(self, run_id):
        with LOCK:
            if run_id not in RUNS: raise ValueError('Run expired or server restarted. Extract again.')
            return RUNS[run_id]

    def allowed_host(self):
        return self.headers.get('Host', '') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

    def do_GET(self):
        if not self.allowed_host():
            self.send({'error': 'Local host only.'}, status=403)
            return
        try:
            url = urllib.parse.urlparse(self.path)
            if url.path == '/':
                html = (ROOT / 'ui.html').read_text().replace('__CSRF_TOKEN__', TOKEN)
                self.send(html.encode(), 'text/html; charset=utf-8')
            elif url.path == '/api/config':
                self.send({'configured': bool(os.environ.get('OPENAI_API_KEY')), 'model': os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini')})
            elif url.path == '/api/page':
                query = urllib.parse.parse_qs(url.query)
                papers = self.get_run(query.get('run', [''])[0])
                paper = next((p for p in papers if p['paper_id'] == query.get('paper', [''])[0]), None)
                if paper is None: raise ValueError('Unknown paper.')
                page = int(query.get('page', ['1'])[0])
                if not 1 <= page <= len(paper['pages']): raise ValueError('Page is out of range.')
                with pymupdf.open(stream=paper['pdf'], filetype='pdf') as doc:
                    target = doc[page-1]
                    scale = min(1.15, 1600 / max(target.rect.width, target.rect.height, 1))
                    self.send(target.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes('png'), 'image/png')
            else:
                self.send({'error': 'Not found'}, status=404)
        except (ValueError, KeyError, TypeError) as exc:
            self.send({'error': str(exc)}, status=400)
        except Exception:
            self.send({'error': 'Unable to display this page.'}, status=500)

    def do_POST(self):
        if not self.allowed_host():
            self.send({'error': 'Local host only.'}, status=403)
            return
        if not secrets.compare_digest(self.headers.get('X-App-Token', ''), TOKEN):
            self.send({'error': 'Invalid session token. Reload the page.'}, status=403)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 105 * 1024 * 1024: raise ValueError('Request size must be below 105 MB.')
            payload = json.loads(self.rfile.read(size))
            path = urllib.parse.urlparse(self.path).path
            if path == '/api/demo':
                papers = [paper_record('synthetic-demo.pdf', demo_pdf(), demo=True)]
                run = retain(papers)
                self.send({'run': run, 'papers': public_papers(papers), 'errors': []})
            elif path == '/api/extract':
                files = payload.get('files', [])
                if not isinstance(files, list) or not 1 <= len(files) <= 5:
                    raise ValueError('Choose 1–5 PDFs.')
                model = payload.get('model', os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'))
                if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', model):
                    raise ValueError('Invalid model identifier.')
                papers, errors, seen = [], [], set()
                for item in files:
                    name = str(item.get('name', 'paper.pdf')).replace('\\', '/').rsplit('/', 1)[-1][:180]
                    try:
                        data = base64.b64decode(item.get('data', ''), validate=True)
                        import hashlib
                        digest = hashlib.sha256(data).hexdigest()
                        if digest in seen: raise ValueError('Duplicate PDF skipped.')
                        seen.add(digest)
                        papers.append(paper_record(name, data, model=model))
                    except (ValueError, TypeError) as exc:
                        errors.append({'name': name, 'error': str(exc)})
                run = retain(papers) if papers else None
                self.send({'run': run, 'papers': public_papers(papers), 'errors': errors})
            elif path in ['/api/export', '/api/audit']:
                papers = self.get_run(payload.get('run', ''))
                rows, audit = apply_edits(papers, payload.get('rows', []))
                if path == '/api/export':
                    self.send(workbook(papers, rows, audit), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename='rwe-evidence.xlsx')
                else:
                    raw = [{k: v for k, v in p.items() if k != 'pdf'} for p in papers]
                    self.send({'papers': raw, 'reviewed_rows': rows, 'edits': audit}, filename='rwe-audit.json')
            else:
                self.send({'error': 'Not found'}, status=404)
        except (ValueError, KeyError, TypeError) as exc:
            self.send({'error': str(exc)}, status=400)
        except Exception:
            self.send({'error': 'Processing failed. No partial export was accepted. Check the local server.'}, status=500)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8501'))
    print(f'W09 Literature Evidence Desk: http://127.0.0.1:{port}', flush=True)
    print('Local prototype; runs are held in memory. Export before restarting. Ctrl+C to stop.', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
