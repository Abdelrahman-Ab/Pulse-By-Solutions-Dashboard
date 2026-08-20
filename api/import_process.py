from http.server import BaseHTTPRequestHandler
import json
import os
import tempfile
from api.blob_store import read_private_blob, delete_blobs, commit_snapshot
from api.dropbox_source import DROPBOX_SOURCES, download_all, validate_xlsx
from api.processor import build_all

DATASETS = set(DROPBOX_SOURCES)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        pathname = ''
        try:
            n = int(self.headers.get('Content-Length', '0') or 0)
            body = json.loads(self.rfile.read(n) or b'{}')
            dataset = body.get('dataset', '')
            if dataset not in DATASETS:
                raise RuntimeError('Unknown dataset.')
            pathname = body.get('pathname', '')
            if not pathname.startswith(f'incoming/{dataset}/'):
                raise RuntimeError('Invalid uploaded file path.')
            raw = read_private_blob(pathname)
            if len(raw) < 1000:
                raise RuntimeError('Uploaded workbook is empty.')

            with tempfile.TemporaryDirectory(prefix='partners-manual-import-') as td:
                override = os.path.join(td, DROPBOX_SOURCES[dataset]['filename'])
                with open(override, 'wb') as f:
                    f.write(raw)
                validate_xlsx(override)
                paths = download_all(td, override_key=dataset, override_path=override)
                core_raw, po_raw, meta = build_all(paths, source=f'manual-import:{dataset}')
                manifest = commit_snapshot(core_raw, po_raw, meta)

            try:
                delete_blobs([pathname])
            except Exception:
                pass
            self._send(200, {
                'ok': True,
                'dataset': dataset,
                'message': 'Imported workbook validated and published successfully.',
                'version': manifest['version'],
                'meta': meta,
            })
        except Exception as e:
            # Keep failed incoming uploads available only temporarily; best effort cleanup.
            try:
                if pathname:
                    delete_blobs([pathname])
            except Exception:
                pass
            self._send(400, {'ok': False, 'error': str(e)})

    def _send(self, status, obj):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)
