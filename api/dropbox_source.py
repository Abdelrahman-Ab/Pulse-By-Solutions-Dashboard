from __future__ import annotations
import os
import time
import urllib.parse
import urllib.request
import zipfile
import shutil

DROPBOX_SOURCES = {
    'opportunities': {
        'name': 'List of Opportunities',
        'filename': 'opportunities.xlsx',
        'url': 'https://www.dropbox.com/scl/fi/s8s12tvndt188lodr1v2h/List-of-Opportunities.xlsx?rlkey=86evubjvzi3sa2fbjl7cksf99&st=vzyp210r&dl=0',
    },
    'orderbook': {
        'name': 'Order Book Values per Market Unit',
        'filename': 'order-book.xlsx',
        'url': 'https://www.dropbox.com/scl/fi/5da78ue54y0dbehu1kqz3/Order-Book-Values-per-Market-Unit.xlsx?rlkey=ekpx59r0faymfegkxr63hsa50&st=xvu9hnuj&dl=0',
    },
    'targets': {
        'name': 'Targets',
        'filename': 'targets.xlsx',
        'url': 'https://www.dropbox.com/scl/fi/341abt352egm67e9xoa76/Targets.xlsx?rlkey=na2hguo7soi2ax9pk03zdhtcx&st=izh21n5f&dl=0',
    },
    'podates': {
        'name': 'Purchase Order Details',
        'filename': 'purchase-order-dates.xlsx',
        'url': 'https://www.dropbox.com/scl/fi/efw87or17hxfmm1jqtbgd/Purchase-Order-Details.xlsx?rlkey=gsbxcgzdhat47rrrsxwh39c0g&st=69wy6dhg&dl=0',
    },
    'strategic': {
        'name': 'Strategic Partners',
        'filename': 'strategic-partners.xlsx',
        'url': 'https://www.dropbox.com/scl/fi/dm864tct06fkv2isdlnrv/Strategic-Partners.xlsx?rlkey=e8tx5m9zrbrc5hunslll5ywzq&st=duw42f4t&dl=0',
    },
}


def direct_candidates(shared_url: str):
    """Yield several Dropbox direct-download variants.

    Dropbox occasionally changes which shared-link form is accepted.  Older builds only
    tried two variants after stripping the ``st`` parameter, which can lead to an HTML
    interstitial instead of the workbook.  Keep the original parameters first, then try
    normalized forms and the direct-content host.
    """
    p = urllib.parse.urlsplit(shared_url)
    original_q = urllib.parse.parse_qs(p.query, keep_blank_values=True)
    seen = set()

    def emit(host, query, mode_key, mode_value):
        q = {k: v[:] for k, v in query.items()}
        q.pop('dl', None); q.pop('raw', None)
        q[mode_key] = [mode_value]
        url = urllib.parse.urlunsplit((p.scheme, host, p.path, urllib.parse.urlencode(q, doseq=True), p.fragment))
        if url not in seen:
            seen.add(url)
            return url
        return None

    # Preserve every parameter from the user-provided shared link first.
    for mode_key in ('dl', 'raw'):
        u = emit(p.netloc, original_q, mode_key, '1')
        if u: yield u

    # Then try without Dropbox's UI/session tracking parameter.
    normalized_q = {k: v[:] for k, v in original_q.items() if k != 'st'}
    for mode_key in ('dl', 'raw'):
        u = emit(p.netloc, normalized_q, mode_key, '1')
        if u: yield u

    # Finally bypass the Dropbox HTML shell entirely.
    direct_host = 'dl.dropboxusercontent.com'
    for q in (original_q, normalized_q):
        u = emit(direct_host, q, 'dl', '1')
        if u: yield u


def validate_xlsx(path: str):
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        raise RuntimeError('Downloaded file is empty or too small to be an Excel workbook.')
    if not zipfile.is_zipfile(path):
        with open(path, 'rb') as f:
            head = f.read(240).lstrip().lower()
        if head.startswith(b'<!doctype') or head.startswith(b'<html'):
            raise RuntimeError('Dropbox returned an HTML page instead of the Excel workbook.')
        raise RuntimeError('Downloaded content is not a valid XLSX workbook.')
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if '[Content_Types].xml' not in names or 'xl/workbook.xml' not in names:
            raise RuntimeError('Downloaded ZIP is not a valid Excel XLSX workbook.')
        worksheets = [n for n in names if n.startswith('xl/worksheets/') and n.endswith('.xml')]
        if not worksheets:
            raise RuntimeError('Excel workbook contains no worksheets.')
        # Opening the central XML files catches a surprisingly common class of half-synced/corrupt files.
        try:
            z.read('xl/workbook.xml')
            z.read(worksheets[0])
        except Exception as e:
            raise RuntimeError(f'Excel workbook ZIP is corrupt or incomplete: {e}') from e


def _download(url: str, tmp: str, timeout: int):
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; Partners-Alliances-Dashboard/1.0)',
            'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,*/*',
            'Cache-Control': 'no-cache, no-store, max-age=0',
            'Pragma': 'no-cache',
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, 'wb') as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def download_one(key: str, directory: str, timeout: int = 150, attempts: int = 3, fallback_directory: str | None = None) -> str:
    """Download one workbook defensively, with an optional last-good local fallback.

    A source is only accepted after validating the XLSX package.  When a local dashboard
    has already downloaded a valid workbook once, that last-good raw source can be used if
    Dropbox temporarily serves an HTML interstitial.
    """
    info = DROPBOX_SOURCES[key]
    os.makedirs(directory, exist_ok=True)
    dest = os.path.join(directory, info['filename'])
    fallback = os.path.join(fallback_directory, info['filename']) if fallback_directory else None
    errors = []

    candidates = list(direct_candidates(info['url']))
    for attempt in range(1, attempts + 1):
        for candidate_no, url in enumerate(candidates, start=1):
            tmp = dest + f'.part.{attempt}.{candidate_no}'
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
                _download(url, tmp, timeout)
                validate_xlsx(tmp)
                os.replace(tmp, dest)
                if fallback:
                    os.makedirs(fallback_directory, exist_ok=True)
                    cache_tmp = fallback + '.tmp'
                    shutil.copy2(dest, cache_tmp)
                    os.replace(cache_tmp, fallback)
                return dest
            except Exception as e:
                errors.append(f'attempt {attempt}/candidate {candidate_no}: {e}')
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except OSError:
                    pass
        if attempt < attempts:
            time.sleep(min(2 ** (attempt - 1), 4))

    # Local-only resilience: retain the last successful workbook when Dropbox is transiently unavailable.
    if fallback and os.path.exists(fallback):
        try:
            validate_xlsx(fallback)
            shutil.copy2(fallback, dest)
            return dest
        except Exception as e:
            errors.append(f'last-good local fallback: {e}')

    tail = '; '.join(errors[-6:])
    raise RuntimeError(f"{info['name']} could not be downloaded from Dropbox after {attempts} attempts: {tail}")


def download_all(directory: str, override_key: str | None = None, override_path: str | None = None, fallback_directory: str | None = None):
    paths = {}

    # Purchase Order Summary was retired. Purchase Order Details is now the single
    # PO source and also supplies the vendor/partner relationship data used by Order Book.
    required = ('opportunities', 'orderbook', 'targets', 'podates')
    for key in required:
        if key == override_key and override_path:
            validate_xlsx(override_path)
            paths[key] = override_path
        else:
            paths[key] = download_one(key, directory, fallback_directory=fallback_directory)

    # Strategic Partners enhances Partners Performance. Keep it non-blocking so a
    # temporary Dropbox issue cannot take down the whole dashboard.
    key = 'strategic'
    if key == override_key and override_path:
        validate_xlsx(override_path)
        paths[key] = override_path
    else:
        try:
            paths[key] = download_one(key, directory, fallback_directory=fallback_directory)
        except Exception:
            pass
    return paths

