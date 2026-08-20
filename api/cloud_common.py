from __future__ import annotations
import base64, concurrent.futures, gzip, io, json, os, re, tempfile, time, urllib.parse, urllib.request, zipfile
from datetime import datetime
from . import data_engine

SOURCES = {
    'opportunities': ('List of Opportunities', 'https://1drv.ms/x/c/8897dd600ebadf94/IQBh5NSG435GTY0WQUB_jh7UAQXcOodre3cQO6jkE6LfWXk?e=PXg2WU'),
    'orderbook': ('Order Book Values per Market Unit', 'https://1drv.ms/x/c/8897dd600ebadf94/IQA7mynPPLy5Qb0vN9Xrfe1WAWwTAzmucemaO6Lsa07_GNc?e=btbFwj'),
    'targets': ('Targets', 'https://1drv.ms/x/c/8897dd600ebadf94/IQCbQMNOuWt3S7n7WJaNoYoUAfza6fiRRyV2kvwCCRi-FbA?e=lsAZ1h'),
    'po': ('Purchase Order Summary', 'https://1drv.ms/x/c/8897dd600ebadf94/IQCnFKkQwELKTLvMrf-UhzfPAbD8vA7Ay3-P1Zh4Y5XK40o?e=G9bEkX'),
    'podates': ('Purchase Order Details', 'https://1drv.ms/x/c/8897dd600ebadf94/IQCJ8McZmwFqR6CfMQpBFckLAdSSJmGbV17nY0Dawl8URV8?e=2HfODp'),
}

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36'
_MEM = {}
TTL = 55

def _share_api_url(url: str) -> str:
    token = base64.urlsafe_b64encode(url.encode()).decode().rstrip('=')
    return f'https://api.onedrive.com/v1.0/shares/u!{token}/root/content'

def _download_candidates(url: str):
    p = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    q = [(k,v) for k,v in q if k.lower() != 'download']
    q.insert(0, ('download','1'))
    dl = urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,urllib.parse.urlencode(q),p.fragment))
    return [dl, url, _share_api_url(url)]

def _is_xlsx(data: bytes) -> bool:
    if not data.startswith(b'PK'):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=set(z.namelist())
            return '[Content_Types].xml' in names and any(n.startswith('xl/workbook') for n in names)
    except Exception:
        return False

def _extract_download_url(html: bytes):
    text=html.decode('utf-8','ignore')
    patterns=[
        r'"(?:@content\.downloadUrl|downloadUrl)"\s*:\s*"([^"]+)"',
        r'"downloadUrl"\s*:\s*"([^"]+)"',
        r'downloadUrl\\u0022\\s*:\\s*\\u0022([^\\]+)'
    ]
    for pat in patterns:
        m=re.search(pat,text,re.I)
        if m:
            u=m.group(1).replace('\\u0026','&').replace('\\/','/')
            return bytes(u,'utf-8').decode('unicode_escape')
    return None

def _http_get(url: str, timeout=45):
    req=urllib.request.Request(url, headers={'User-Agent':UA,'Accept':'*/*','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl(), dict(r.headers)

def download_excel(key: str, directory: str):
    name,url=SOURCES[key]
    errors=[]
    for candidate in _download_candidates(url):
        try:
            data,final,headers=_http_get(candidate)
            if _is_xlsx(data):
                path=os.path.join(directory, f'{key}.xlsx')
                with open(path,'wb') as f:f.write(data)
                return path, {'name':name,'bytes':len(data),'url':final}
            if data[:200].lower().find(b'<html')>=0 or b'text/html' in str(headers.get('Content-Type','')).encode().lower():
                extracted=_extract_download_url(data)
                if extracted:
                    try:
                        data2,final2,_=_http_get(extracted)
                        if _is_xlsx(data2):
                            path=os.path.join(directory, f'{key}.xlsx')
                            with open(path,'wb') as f:f.write(data2)
                            return path, {'name':name,'bytes':len(data2),'url':final2}
                    except Exception as e:
                        errors.append(f'extracted download URL failed: {e}')
            errors.append(f'{candidate[:70]}... returned {len(data)} bytes, not an XLSX')
        except Exception as e:
            errors.append(f'{candidate[:70]}... -> {type(e).__name__}: {e}')
    raise RuntimeError(f'{name} could not be downloaded as Excel. ' + ' | '.join(errors[-4:]))

def _download_group(keys, directory):
    result={}
    workers=min(4,len(keys))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        fut={ex.submit(download_excel,k,directory):k for k in keys}
        for f in concurrent.futures.as_completed(fut):
            k=fut[f]; result[k]=f.result()
    return result

def build_core(force=False):
    now=time.time()
    if not force and 'core' in _MEM and now-_MEM['core'][0] < TTL:
        return _MEM['core'][1]
    started=time.time()
    with tempfile.TemporaryDirectory(prefix='partners-core-') as td:
        got=_download_group(['opportunities','orderbook','targets'],td)
        paths={k:v[0] for k,v in got.items()}
        data_engine.configure_files(paths)
        opp=data_engine.load_opportunities()
        ob=data_engine.load_orderbook()
        matched,pending=data_engine.join_awarded(opp,ob)
        targets=data_engine.load_targets()
        meta={
            'generatedAt':datetime.now().isoformat(timespec='seconds'),
            'opportunities':len(opp),
            'won':sum(1 for o in opp if str(o.get('roadmap','')).lower()=='won'),
            'wonMatched':matched,'wonPending':pending,
            'orderBookRows':len(ob),'purchaseOrders':0,
            'purchaseOrderDateMatches':0,'purchaseOrderDateLookupSize':0,
            'roadmapOrder':data_engine.ROADMAP_ORDER,
            'cloud':True,'buildSeconds':round(time.time()-started,2),
            'sources':{k:{'name':got[k][1]['name'],'bytes':got[k][1]['bytes']} for k in got}
        }
        obj={'meta':meta,'targets':targets,'opportunities':opp,'orderbook':ob}
    raw=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    gz=gzip.compress(raw,compresslevel=6)
    _MEM['core']=(time.time(),(gz,len(raw),len(gz),obj['meta']))
    return _MEM['core'][1]

def build_purchase_orders(force=False):
    now=time.time()
    if not force and 'po' in _MEM and now-_MEM['po'][0] < TTL:
        return _MEM['po'][1]
    started=time.time()
    with tempfile.TemporaryDirectory(prefix='partners-po-') as td:
        got=_download_group(['po','podates'],td)
        paths={k:v[0] for k,v in got.items()}
        data_engine.configure_files(paths)
        date_map,products,items=data_engine.load_po_dates()
        po,matches=data_engine.load_po(date_map)
        meta={
            'generatedAt':datetime.now().isoformat(timespec='seconds'),
            'purchaseOrders':len(po),'purchaseOrderDateMatches':matches,
            'purchaseOrderDateLookupSize':len(date_map),
            'cloud':True,'buildSeconds':round(time.time()-started,2),
            'sources':{k:{'name':got[k][1]['name'],'bytes':got[k][1]['bytes']} for k in got}
        }
        obj={'meta':meta,'purchaseOrders':po,'products':products,'items':items}
    raw=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    gz=gzip.compress(raw,compresslevel=6)
    _MEM['po']=(time.time(),(gz,len(raw),len(gz),obj['meta']))
    return _MEM['po'][1]
