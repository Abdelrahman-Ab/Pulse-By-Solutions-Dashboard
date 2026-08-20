from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, tempfile
from api.cloud_common import SOURCES, download_excel

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q=parse_qs(urlparse(self.path).query)
        key=q.get('source',[''])[0]
        if key not in SOURCES:
            body=json.dumps({'ok':False,'error':'Use ?source=opportunities, orderbook, targets, po, or podates','available':list(SOURCES)}).encode()
            self.send_response(400);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        try:
            with tempfile.TemporaryDirectory(prefix='source-check-') as td:
                _,meta=download_excel(key,td)
            body=json.dumps({'ok':True,'source':key,'name':SOURCES[key][0],'bytes':meta['bytes'],'megabytes':round(meta['bytes']/1024/1024,2)}).encode()
            self.send_response(200)
        except Exception as e:
            body=json.dumps({'ok':False,'source':key,'name':SOURCES[key][0],'error':str(e)}).encode();self.send_response(502)
        self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
