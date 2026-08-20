from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from api.cloud_common import build_core

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            q=parse_qs(urlparse(self.path).query)
            force=q.get('refresh',['0'])[0] in ('1','true','yes')
            gz,raw_len,gz_len,meta=build_core(force=force)
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Encoding','gzip')
            self.send_header('Content-Length',str(len(gz)))
            self.send_header('X-Raw-Bytes',str(raw_len))
            self.send_header('X-Gzip-Bytes',str(gz_len))
            self.send_header('X-Build-Seconds',str(meta.get('buildSeconds','')))
            if force:
                self.send_header('Cache-Control','no-store')
            else:
                self.send_header('Cache-Control','public, s-maxage=60, stale-while-revalidate=300')
            self.end_headers(); self.wfile.write(gz)
        except Exception as e:
            body=json.dumps({'ok':False,'error':str(e)}).encode()
            self.send_response(502);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
