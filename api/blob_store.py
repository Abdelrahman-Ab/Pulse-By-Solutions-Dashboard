from __future__ import annotations
import gzip
import json
import uuid
from datetime import datetime, timezone


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


def latest_blob(prefix: str):
    blobs = _list(prefix)
    if not blobs:
        return None

    def uploaded_value(blob):
        value = getattr(blob, 'uploaded_at', None)
        if isinstance(value, datetime):
            return value.timestamp()
        if value:
            try:
                return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
            except Exception:
                pass
        return 0.0

    return max(blobs, key=uploaded_value)


def read_private_blob(url_or_path: str) -> bytes:
    """Read a private Vercel Blob through the authenticated Blob SDK.

    Private Blob reads require ``access='private'``. The SDK then uses
    BLOB_READ_WRITE_TOKEN from the Vercel environment automatically.
    ``get()`` returns a GetBlobResult containing status_code and stream.
    """
    if not url_or_path:
        raise RuntimeError('Stored Blob location is empty.')

    with _client() as client:
        result = client.get(url_or_path, access='private')

    if result is None:
        raise RuntimeError(f'Unable to read stored Blob: {url_or_path}')

    # Current vercel-py API: GetBlobResult(status_code, stream, blob).
    status = getattr(result, 'status_code', getattr(result, 'statusCode', None))
    if status is not None and status != 200:
        raise RuntimeError(f'Unable to read stored Blob {url_or_path}: HTTP {status}')

    stream = getattr(result, 'stream', None)
    if stream is not None:
        if hasattr(stream, 'read'):
            data = stream.read()
        else:
            data = b''.join(stream)
        if isinstance(data, str):
            data = data.encode('utf-8')
        return bytes(data)

    # Compatibility fallbacks for SDK versions that may return raw content.
    if isinstance(result, bytes):
        return result
    if isinstance(result, bytearray):
        return bytes(result)
    if isinstance(result, memoryview):
        return result.tobytes()
    if isinstance(result, str):
        return result.encode('utf-8')
    if hasattr(result, 'read'):
        data = result.read()
        return data.encode('utf-8') if isinstance(data, str) else bytes(data)

    content = getattr(result, 'content', None)
    if isinstance(content, bytes):
        return content

    raise RuntimeError(
        f'Unable to read stored Blob {url_or_path}: unexpected BlobClient.get() '
        f'result type {type(result).__name__}.'
    )


def put_private(pathname: str, data: bytes, content_type: str):
    with _client() as client:
        return client.put(
            pathname,
            data,
            access='private',
            content_type=content_type,
            add_random_suffix=False,
            overwrite=False,
            multipart=(len(data) > 4 * 1024 * 1024),
        )


def delete_blobs(items):
    if not items:
        return
    urls = []
    for x in items:
        urls.append(getattr(x, 'url', None) or getattr(x, 'pathname', None) or str(x))
    urls = [x for x in urls if x]
    if urls:
        with _client() as client:
            client.delete(urls)


def _version_id():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]


def _blob_read_locator(blob):
    # Vercel get() accepts either the Blob URL or pathname. Prefer the returned URL.
    return getattr(blob, 'url', None) or getattr(blob, 'download_url', None) or getattr(blob, 'pathname', None)


def current_manifest():
    b = latest_blob('dashboard/manifests/')
    if not b:
        return None

    locator = _blob_read_locator(b)
    try:
        obj = json.loads(read_private_blob(locator).decode('utf-8'))
    except Exception as e:
        # Do not hide the real Blob read problem as "no snapshot".
        raise RuntimeError(f'Latest dashboard manifest exists but could not be read: {e}') from e

    obj['_manifestPath'] = getattr(b, 'pathname', '')
    obj['_manifestUrl'] = getattr(b, 'url', '')
    return obj


def _cleanup_snapshots(keep_version: str, keep_manifest: str):
    try:
        old_data = [
            b for b in _list('dashboard/snapshots/', 100)
            if f'/{keep_version}/' not in (getattr(b, 'pathname', '') or '')
        ]
        old_manifests = [
            b for b in _list('dashboard/manifests/', 100)
            if (getattr(b, 'pathname', '') or '') != keep_manifest
        ]
        delete_blobs(old_data + old_manifests)
    except Exception:
        # Cleanup must never invalidate a successful committed snapshot.
        pass


def commit_snapshot(core_raw_json: bytes, po_raw_json: bytes, meta: dict | None = None):
    """Write both datasets first and publish the manifest last (atomic pointer)."""
    version = _version_id()
    core_gz = gzip.compress(core_raw_json, compresslevel=6)
    po_gz = gzip.compress(po_raw_json, compresslevel=6)
    core_path = f'dashboard/snapshots/{version}/core.json.gz'
    po_path = f'dashboard/snapshots/{version}/po.json.gz'
    core_blob = None
    po_blob = None
    manifest_blob = None

    try:
        core_blob = put_private(core_path, core_gz, 'application/gzip')
        po_blob = put_private(po_path, po_gz, 'application/gzip')

        manifest = {
            'version': version,
            'generatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            # Keep both paths and URLs for compatibility/diagnostics. Private reads
            # are authenticated by passing access='private' to BlobClient.get().
            'corePath': getattr(core_blob, 'pathname', core_path),
            'poPath': getattr(po_blob, 'pathname', po_path),
            'coreUrl': getattr(core_blob, 'url', None),
            'poUrl': getattr(po_blob, 'url', None),
            'coreGzipBytes': len(core_gz),
            'poGzipBytes': len(po_gz),
            'meta': meta or {},
        }

        manifest_path = f'dashboard/manifests/{version}.json'
        manifest_blob = put_private(
            manifest_path,
            json.dumps(manifest, separators=(',', ':')).encode('utf-8'),
            'application/json',
        )

        # Verify the just-published snapshot before reporting refresh success.
        verify_snapshot(manifest, manifest_blob)

        _cleanup_snapshots(version, getattr(manifest_blob, 'pathname', manifest_path))
        return manifest
    except Exception:
        # Anything without a successfully verified manifest must not become visible.
        try:
            delete_blobs([x for x in (core_blob, po_blob, manifest_blob) if x])
        except Exception:
            pass
        raise


def verify_snapshot(manifest: dict, manifest_blob=None):
    """Read the published objects back from Blob and validate their JSON payloads."""
    try:
        if manifest_blob is not None:
            manifest_locator = _blob_read_locator(manifest_blob)
            published = json.loads(read_private_blob(manifest_locator).decode('utf-8'))
            if published.get('version') != manifest.get('version'):
                raise RuntimeError('Published manifest version does not match the committed snapshot.')

        core_locator = manifest.get('coreUrl') or manifest.get('corePath')
        po_locator = manifest.get('poUrl') or manifest.get('poPath')
        core_obj = json.loads(gzip.decompress(read_private_blob(core_locator)).decode('utf-8'))
        po_obj = json.loads(gzip.decompress(read_private_blob(po_locator)).decode('utf-8'))
        if 'opportunities' not in core_obj or 'orderbook' not in core_obj:
            raise RuntimeError('Core snapshot verification failed: expected datasets are missing.')
        if 'purchaseOrders' not in po_obj:
            raise RuntimeError('PO snapshot verification failed: purchaseOrders is missing.')
        return True
    except Exception as e:
        raise RuntimeError(f'Blob snapshot verification failed: {e}') from e


def get_current_processed(scope: str):
    if scope not in {'core', 'po'}:
        raise RuntimeError('Unknown processed data scope.')

    m = current_manifest()
    if m:
        if scope == 'core':
            locator = m.get('coreUrl') or m.get('corePath')
            pathname = m.get('corePath', '')
        else:
            locator = m.get('poUrl') or m.get('poPath')
            pathname = m.get('poPath', '')
        if not locator:
            raise RuntimeError(f'Current manifest is missing the {scope} Blob location.')
        return read_private_blob(locator), {
            'origin': m.get('meta', {}).get('source', 'dropbox'),
            'version': m.get('version', ''),
            'generatedAt': m.get('generatedAt', ''),
            'pathname': pathname,
        }

    # Seamless migration from the earlier Vercel Import version on the same project.
    legacy = latest_blob(f'processed/{scope}/')
    if legacy:
        locator = _blob_read_locator(legacy)
        return read_private_blob(locator), {
            'origin': 'legacy-blob',
            'version': '',
            'generatedAt': getattr(legacy, 'uploaded_at', None).isoformat() if isinstance(getattr(legacy, 'uploaded_at', None), datetime) else str(getattr(legacy, 'uploaded_at', '') or ''),
            'pathname': getattr(legacy, 'pathname', ''),
        }

    raise RuntimeError(
        'No shared dashboard snapshot exists yet. Press Refresh Data once to load the five Dropbox workbooks.'
    )
