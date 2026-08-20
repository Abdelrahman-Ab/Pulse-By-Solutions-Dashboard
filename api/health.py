from http.server import BaseHTTPRequestHandler
import json
from api.cloud_common import SOURCES
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=json.dumps({'ok':True,'mode':'vercel-cloud','sources':[v[0] for v in SOURCES.values()]}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
