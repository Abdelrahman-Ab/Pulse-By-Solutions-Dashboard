from http.server import BaseHTTPRequestHandler
import json
import tempfile
import time
from api.dropbox_source import download_one, DROPBOX_SOURCES
from api.processor import build_all
from api.blob_store import commit_snapshot, current_manifest


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        started=time.time(); stage='start'; progress=[]
        try:
            previous=None
            try:
                previous=current_manifest()
            except Exception as e:
                progress.append({'stage':'baseline:manifest','ok':False,'warning':str(e)})
            previous_meta=(previous or {}).get('meta',{})

            with tempfile.TemporaryDirectory(prefix='partners-dropbox-sync-') as td:
                paths={}
                for key in ('opportunities','orderbook','targets','po','podates'):
                    stage=f'download:{key}'
                    paths[key]=download_one(key,td)
                    progress.append({'stage':stage,'ok':True,'name':DROPBOX_SOURCES[key]['name']})

                stage='process:all-workbooks'
                core_raw,po_raw,meta=build_all(paths,source='dropbox-refresh',previous_meta=previous_meta)
                progress.append({'stage':stage,'ok':True,'meta':{
                    'opportunities':meta.get('opportunities'),
                    'orderBookRows':meta.get('orderBookRows'),
                    'purchaseOrders':meta.get('purchaseOrders'),
                    'd365OppIdPopulated':meta.get('d365OppIdPopulated'),
                }})

                stage='blob:commit-and-verify'
                manifest=commit_snapshot(core_raw,po_raw,meta)
                progress.append({'stage':stage,'ok':True,'version':manifest['version']})

            self._send(200,{
                'ok':True,
                'message':'Dropbox refresh completed and the new shared snapshot was verified.',
                'version':manifest['version'],'meta':meta,'progress':progress,
                'seconds':round(time.time()-started,2),
            })
        except Exception as e:
            actual_stage=getattr(e,'stage',stage)
            progress.append({'stage':actual_stage,'ok':False,'error':str(e)})
            self._send(500,{
                'ok':False,'stage':actual_stage,'error':str(e),
                'message':f'Refresh failed at {actual_stage}: {e}',
                'preservedPreviousSnapshot':True,
                'progress':progress,'seconds':round(time.time()-started,2),
            })

    def _send(self,status,obj):
        b=json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(b)))
        self.end_headers(); self.wfile.write(b)
