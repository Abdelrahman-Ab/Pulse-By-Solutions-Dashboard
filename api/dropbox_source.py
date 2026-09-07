from __future__ import annotations
import os
import time
import urllib.parse
import urllib.request
import zipfile

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
    'po': {
        'name': 'Purchase Order Summary',
        'filename': 'purchase-orders.xlsx',
        'url': 'https://www.dropbox.com/scl/fi/18gpq1fw960r21pa8ag15/Purchase-Order-Summary.xlsx?rlkey=zavcemqy1qat3biinmsavu74e&st=qqkvdpc1&dl=0',
    },
    'podates': {
        'name': 'Purchase Order Details',
        'filename': 'purchase-order-dates.xlsx',
        'url': 'https://www.dropbox.com/scl/fi/efw87or17hxfmm1jqtbgd/Purchase-Order-Details.xlsx?rlkey=gsbxcgzdhat47rrrsxwh39c0g&st=69wy6dhg&dl=0',
    },
}


def direct_candidates(shared_url: str):
    p = urllib.parse.urlsplit(shared_url)
    q = urllib.parse.parse_qs(p.query, keep_blank_values=True)
    # `st` is a temporary UI/session parameter and is not required for a shared link.
    q.pop('st', None)

    q1 = {k: v[:] for k, v in q.items()}
    q1.pop('raw', None)
    q1['dl'] = ['1']
    yield urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q1, doseq=True), p.fragment))

    q2 = {k: v[:] for k, v in q.items()}
    q2.pop('dl', None)
    q2['raw'] = ['1']
    yield urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q2, doseq=True), p.fragment))


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


def download_one(key: str, directory: str, timeout: int = 150, attempts: int = 3) -> str:
    """Download one workbook defensively.

    Dropbox links can briefly serve stale/partial content while a workbook is being replaced.
    We retry each direct-download form and validate the XLSX package before accepting it.
    """
    info = DROPBOX_SOURCES[key]
    os.makedirs(directory, exist_ok=True)
    dest = os.path.join(directory, info['filename'])
    errors = []

    for attempt in range(1, attempts + 1):
        for candidate_no, url in enumerate(direct_candidates(info['url']), start=1):
            tmp = dest + f'.part.{attempt}.{candidate_no}'
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
                _download(url, tmp, timeout)
                validate_xlsx(tmp)
                os.replace(tmp, dest)
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

    tail = '; '.join(errors[-4:])
    raise RuntimeError(f"{info['name']} could not be downloaded from Dropbox after {attempts} attempts: {tail}")


def download_all(directory: str, override_key: str | None = None, override_path: str | None = None):
    paths = {}
    for key in ('opportunities', 'orderbook', 'targets', 'po', 'podates'):
        if key == override_key and override_path:
            validate_xlsx(override_path)
            paths[key] = override_path
        else:
            paths[key] = download_one(key, directory)
    return paths
