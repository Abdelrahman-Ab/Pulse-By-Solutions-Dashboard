from http.server import BaseHTTPRequestHandler
import json
from api.blob_store import get_current_processed


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data, meta = get_current_processed('po')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('X-Data-Origin', meta.get('origin', ''))
            self.send_header('X-Data-Version', meta.get('version', ''))
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._err(e)

    def _err(self, e):
        b = json.dumps({'ok': False, 'error': str(e)}).encode('utf-8')
        self.send_response(503)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)
