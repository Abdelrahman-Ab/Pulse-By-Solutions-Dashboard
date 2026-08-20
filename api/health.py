from http.server import BaseHTTPRequestHandler
import json
from api.blob_store import blob_ready, current_manifest


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, err = blob_ready()
        manifest = current_manifest() if ok else None
        payload = {
            'ok': True,
            'blobReady': ok,
            'blobError': err,
            'snapshotReady': bool(manifest),
            'snapshotVersion': manifest.get('version', '') if manifest else '',
            'source': 'Dropbox shared links + Vercel Blob',
        }
        b = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)
