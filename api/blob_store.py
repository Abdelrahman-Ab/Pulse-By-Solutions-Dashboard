from __future__ import annotations
import gzip
import json
import uuid
from datetime import datetime, timezone

ROLLBACK_SNAPSHOTS = 3


def _blob_client_class():
    try:
        from vercel.blob import BlobClient
        return BlobClient
    except Exception as e:
        raise RuntimeError(
            'Vercel Blob is not available. Connect the Blob store to this Vercel project '
            'and ensure BLOB_READ_WRITE_TOKEN is available to the deployment.'
        ) from e


def _client():
    return _blob_client_class()()


def blob_ready():
    try:
        with _client() as client:
            client.list_objects(prefix='dashboard-health/', limit=1)
        return True, ''
    except Exception as e:
        return False, str(e)


def _list(prefix: str, limit: int = 100):
    with _client() as client:
        page = client.list_objects(prefix=prefix, limit=limit)
    return list(getattr(page, 'blobs', None) or [])


def _uploaded_value(blob):
    value = getattr(blob, 'uploaded_at', None)
    if isinstance(value, datetime):
        return value.timestamp()
    if value:
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
        except Exception:
            pass
    return 0.0


def _sorted_blobs(prefix: str, limit: int = 100):
    return sorted(_list(prefix, limit), key=_uploaded_value, reverse=True)


def latest_blob(prefix: str):
    blobs = _sorted_blobs(prefix)
    return blobs[0] if blobs else None


def read_private_blob(url_or_path: str) -> bytes:
    if not url_or_path:
        raise RuntimeError('Stored Blob location is empty.')
    with _client() as client:
        result = client.get(url_or_path, access='private')
    if result is None:
        raise RuntimeError(f'Unable to read stored Blob: {url_or_path}')

    status = getattr(result, 'status_code', getattr(result, 'statusCode', None))
    if status is not None and status != 200:
        raise RuntimeError(f'Unable to read stored Blob {url_or_path}: HTTP {status}')

    stream = getattr(result, 'stream', None)
    if stream is not None:
        data = stream.read() if hasattr(stream, 'read') else b''.join(stream)
        if isinstance(data, str):
            data = data.encode('utf-8')
        return bytes(data)
    if isinstance(result, bytes): return result
    if isinstance(result, bytearray): return bytes(result)
    if isinstance(result, memoryview): return result.tobytes()
    if isinstance(result, str): return result.encode('utf-8')
    if hasattr(result, 'read'):
        data = result.read(); return data.encode('utf-8') if isinstance(data, str) else bytes(data)
    content = getattr(result, 'content', None)
    if isinstance(content, bytes): return content
    raise RuntimeError(f'Unexpected BlobClient.get() result type {type(result).__name__}.')


def put_private(pathname: str, data: bytes, content_type: str):
    with _client() as client:
        return client.put(
            pathname, data, access='private', content_type=content_type,
            add_random_suffix=False, overwrite=False,
            multipart=(len(data) > 4 * 1024 * 1024),
        )


def delete_blobs(items):
    urls=[]
    for x in items or []:
        urls.append(getattr(x, 'url', None) or getattr(x, 'pathname', None) or str(x))
    urls=[x for x in urls if x]
    if urls:
        with _client() as client:
            client.delete(urls)


def _version_id():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]


def _blob_read_locator(blob):
    return getattr(blob, 'url', None) or getattr(blob, 'download_url', None) or getattr(blob, 'pathname', None)


def _read_manifest_blob(blob):
    obj=json.loads(read_private_blob(_blob_read_locator(blob)).decode('utf-8'))
    if not obj.get('version'):
        raise RuntimeError('Manifest has no version.')
    if not (obj.get('coreUrl') or obj.get('corePath')) or not (obj.get('poUrl') or obj.get('poPath')):
        raise RuntimeError('Manifest is missing dataset locations.')
    obj['_manifestPath']=getattr(blob,'pathname','')
    obj['_manifestUrl']=getattr(blob,'url','')
    return obj


def manifest_candidates(limit: int = 10):
    """Return readable manifests newest-first; unreadable/corrupt ones are skipped."""
    out=[]
    for blob in _sorted_blobs('dashboard/manifests/', max(limit, ROLLBACK_SNAPSHOTS + 2)):
        try:
            out.append(_read_manifest_blob(blob))
            if len(out) >= limit:
                break
        except Exception:
            continue
    return out


def current_manifest():
    candidates=manifest_candidates(1)
    return candidates[0] if candidates else None


def _validate_gzip_json(data: bytes, scope: str):
    try:
        obj=json.loads(gzip.decompress(data).decode('utf-8'))
    except Exception as e:
        raise RuntimeError(f'{scope} snapshot is corrupt or not valid gzip JSON: {e}') from e
    if scope=='core' and ('opportunities' not in obj or 'orderbook' not in obj or 'targets' not in obj):
        raise RuntimeError('Core snapshot is missing required datasets.')
    if scope=='po' and 'purchaseOrders' not in obj:
        raise RuntimeError('PO snapshot is missing purchaseOrders.')
    return obj


def _cleanup_snapshots():
    """Keep a tiny rollback window instead of deleting the only fallback immediately.

    Keeping 3 verified versions also makes simultaneous Refresh clicks safe: one refresh
    cannot delete the snapshot another refresh has just published.
    """
    try:
        manifest_blobs=_sorted_blobs('dashboard/manifests/',100)
        keep_manifest_blobs=manifest_blobs[:ROLLBACK_SNAPSHOTS]
        keep_paths={getattr(b,'pathname','') for b in keep_manifest_blobs}
        keep_versions=set()
        for b in keep_manifest_blobs:
            try:
                keep_versions.add(_read_manifest_blob(b).get('version'))
            except Exception:
                # Preserve an unreadable recent manifest until it naturally falls out of the window.
                p=getattr(b,'pathname','')
                if p.endswith('.json'):
                    keep_versions.add(p.rsplit('/',1)[-1][:-5])

        old_manifests=[b for b in manifest_blobs if getattr(b,'pathname','') not in keep_paths]
        old_data=[]
        for b in _list('dashboard/snapshots/',100):
            path=getattr(b,'pathname','') or ''
            if not any(f'/{v}/' in path for v in keep_versions if v):
                old_data.append(b)
        delete_blobs(old_data + old_manifests)
    except Exception:
        # Cleanup is best-effort. Serving the dashboard is more important than saving a few MB.
        pass


def commit_snapshot(core_raw_json: bytes, po_raw_json: bytes, meta: dict | None = None):
    """Atomic publish: data first, manifest last, full readback verification before success."""
    version=_version_id()
    core_gz=gzip.compress(core_raw_json,compresslevel=6)
    po_gz=gzip.compress(po_raw_json,compresslevel=6)
    core_path=f'dashboard/snapshots/{version}/core.json.gz'
    po_path=f'dashboard/snapshots/{version}/po.json.gz'
    core_blob=po_blob=manifest_blob=None
    try:
        core_blob=put_private(core_path,core_gz,'application/gzip')
        po_blob=put_private(po_path,po_gz,'application/gzip')
        manifest={
            'version':version,
            'generatedAt':datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'corePath':getattr(core_blob,'pathname',core_path),
            'poPath':getattr(po_blob,'pathname',po_path),
            'coreUrl':getattr(core_blob,'url',None),
            'poUrl':getattr(po_blob,'url',None),
            'coreGzipBytes':len(core_gz),'poGzipBytes':len(po_gz),'meta':meta or {},
        }
        manifest_path=f'dashboard/manifests/{version}.json'
        manifest_blob=put_private(manifest_path,json.dumps(manifest,separators=(',',':')).encode(),'application/json')
        verify_snapshot(manifest,manifest_blob)
        _cleanup_snapshots()
        return manifest
    except Exception:
        try: delete_blobs([x for x in (core_blob,po_blob,manifest_blob) if x])
        except Exception: pass
        raise


def verify_snapshot(manifest: dict, manifest_blob=None):
    try:
        if manifest_blob is not None:
            published=json.loads(read_private_blob(_blob_read_locator(manifest_blob)).decode('utf-8'))
            if published.get('version') != manifest.get('version'):
                raise RuntimeError('Published manifest version does not match committed snapshot.')
        core=read_private_blob(manifest.get('coreUrl') or manifest.get('corePath'))
        po=read_private_blob(manifest.get('poUrl') or manifest.get('poPath'))
        _validate_gzip_json(core,'core')
        _validate_gzip_json(po,'po')
        return True
    except Exception as e:
        raise RuntimeError(f'Blob snapshot verification failed: {e}') from e


def get_current_processed(scope: str):
    if scope not in {'core','po'}:
        raise RuntimeError('Unknown processed data scope.')

    # Self-healing read: if the newest manifest/blob is damaged or temporarily unreadable,
    # automatically serve the previous verified snapshot instead of taking the dashboard down.
    errors=[]
    for m in manifest_candidates(ROLLBACK_SNAPSHOTS):
        try:
            if scope=='core':
                locator=m.get('coreUrl') or m.get('corePath'); pathname=m.get('corePath','')
            else:
                locator=m.get('poUrl') or m.get('poPath'); pathname=m.get('poPath','')
            data=read_private_blob(locator)
            _validate_gzip_json(data,scope)
            return data, {
                'origin':m.get('meta',{}).get('source','dropbox'),
                'version':m.get('version',''),
                'generatedAt':m.get('generatedAt',''),
                'pathname':pathname,
            }
        except Exception as e:
            errors.append(f"{m.get('version','?')}: {e}")
            continue

    legacy=latest_blob(f'processed/{scope}/')
    if legacy:
        locator=_blob_read_locator(legacy)
        data=read_private_blob(locator)
        return data, {
            'origin':'legacy-blob','version':'',
            'generatedAt':getattr(legacy,'uploaded_at',None).isoformat() if isinstance(getattr(legacy,'uploaded_at',None),datetime) else str(getattr(legacy,'uploaded_at','') or ''),
            'pathname':getattr(legacy,'pathname',''),
        }

    suffix=(' Recent snapshot errors: '+' | '.join(errors)) if errors else ''
    raise RuntimeError('No readable shared dashboard snapshot exists yet. Press Refresh Data once.'+suffix)
