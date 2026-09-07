from __future__ import annotations
import os, json, math, zipfile, xml.etree.ElementTree as ET, argparse
from collections import defaultdict
from datetime import datetime, date, timedelta

BASE=os.path.dirname(os.path.abspath(__file__))
FILES={}

def configure_files(files):
    global FILES
    FILES=dict(files)

ROADMAP_ORDER=['Early Stage','Prospect','Upside','Committed','Won']

def clean(v, default=''):
    if v is None: return default
    s=str(v).strip()
    return s if s else default

def norm_missing(v, default=''):
    s=clean(v,default)
    return default if s=='252' else s

def num(v):
    if v in (None,''): return 0.0
    try: return float(str(v).replace(',','').strip())
    except Exception: return 0.0

def pct(v):
    n=num(v)
    if n>1: n/=100
    return max(0,min(1,n))

def excel_iso(v):
    if v in (None,''): return ''
    if isinstance(v,(datetime,date)):
        return (v.date() if isinstance(v,datetime) else v).isoformat()
    s=str(v).strip()
    try:
        n=float(s)
        if 20000<n<80000:
            return (datetime(1899,12,30)+timedelta(days=n)).date().isoformat()
    except Exception: pass
    for fmt in ('%Y-%m-%d %H:%M:%S','%Y-%m-%d','%d/%m/%Y','%m/%d/%Y'):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except Exception:pass
    return s[:10]

def year_from_iso(s):
    try:return int(s[:4])
    except:return None

def q_from_iso(s):
    try:return f"Q{((int(s[5:7])-1)//3)+1}"
    except:return ''
def m_from_iso(s):
    try:return datetime(2000,int(s[5:7]),1).strftime('%b')
    except:return ''
def nid(v):return clean(v).upper()

def col_letters(ref):
    return ''.join(ch for ch in (ref or '') if ch.isalpha())


def col_index_to_letters(index):
    """1-based Excel column index -> letters (1=A, 27=AA)."""
    try:
        n=int(index)
    except Exception:
        return ''
    if n < 1:
        return ''
    out=[]
    while n:
        n, rem = divmod(n-1, 26)
        out.append(chr(65+rem))
    return ''.join(reversed(out))


def _cell_column(c, ordinal):
    """
    Return a cell's Excel column.

    Some exports omit the normal cell reference attribute (for example r="H3")
    on every <c> element and even advertise worksheet dimension A1 despite carrying
    hundreds of columns. In that valid-enough export shape, column position is
    represented only by the order of <c> elements in the row. Fall back to that
    ordinal instead of collapsing every cell into an empty column key.
    """
    explicit=col_letters(c.attrib.get('r',''))
    return explicit or col_index_to_letters(ordinal)

def load_shared(z):
    if 'xl/sharedStrings.xml' not in z.namelist(): return []
    out=[]
    with z.open('xl/sharedStrings.xml') as fh:
        for ev,e in ET.iterparse(fh,events=('end',)):
            if e.tag.endswith('}si'):
                out.append(''.join(t.text or '' for t in e.iter() if t.tag.endswith('}t')))
                e.clear()
    return out

def cell_value(c, shared):
    t=c.attrib.get('t')
    v=''
    if t=='inlineStr':
        return ''.join(tn.text or '' for tn in c.iter() if tn.tag.endswith('}t'))
    for ch in c:
        if ch.tag.endswith('}v'):
            v=ch.text or ''; break
    if t=='s':
        try:return shared[int(v)]
        except:return ''
    if t=='b': return 'TRUE' if v=='1' else 'FALSE'
    return v

def _header_norm(v):
    """Normalize exported Excel headers without changing the dashboard's canonical field names."""
    s=clean(v).replace('\xa0',' ')
    return ''.join(ch.lower() for ch in s if ch.isalnum())


def _worksheet_names(z):
    """Return worksheet XML files. Do not assume the data sheet is always sheet1.xml."""
    names=[]
    for name in z.namelist():
        if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
            stem=name.rsplit('/',1)[-1][5:-4]
            try: order=int(stem)
            except Exception: order=999999
            names.append((order,name))
    names.sort()
    return [name for _,name in names]


def _read_row_cells(elem, shared):
    vals={}
    ordinal=0
    for c in elem:
        if c.tag.endswith('}c'):
            ordinal += 1
            vals[_cell_column(c, ordinal)] = cell_value(c,shared)
    return vals


def _detect_table(z, shared, wanted_headers, preferred_header_row=None, scan_rows=5000):
    """Find the most likely worksheet/header row by matching normalized known headers."""
    wanted_headers=set(wanted_headers or [])
    norm_to_canonical={}
    for h in wanted_headers:
        n=_header_norm(h)
        # Prefer the human-readable/canonical variant if aliases normalize identically.
        if n not in norm_to_canonical or (' ' in h and ' ' not in norm_to_canonical[n]):
            norm_to_canonical[n]=h

    best=None
    for sheet in _worksheet_names(z):
        with z.open(sheet) as fh:
            for ev,e in ET.iterparse(fh,events=('end',)):
                if not e.tag.endswith('}row'):
                    continue
                r=int(e.attrib.get('r','0'))
                if r>scan_rows:
                    e.clear(); break
                raw=_read_row_cells(e,shared)
                headers=[clean(v) for v in raw.values() if clean(v)]
                norms={_header_norm(v) for v in headers if _header_norm(v)}
                score=sum(1 for n in norms if n in norm_to_canonical)
                # Extra weight for the columns that make an opportunity table recognizable.
                anchors=sum(1 for n in ('roadmap','roadmapstatus','roadmapstage','oppid','opportunityid','potentialcustomer','customer','topic','opportunitytopic','mku','marketunit','d365oppid','d365opportunityid') if n in norms)
                pref=1 if preferred_header_row and r==preferred_header_row else 0
                candidate=(score,anchors,pref,-r,sheet,r,raw)
                if best is None or candidate[:4] > best[:4]:
                    best=candidate
                e.clear()

    if not best or best[0] < 2:
        return None
    _,_,_,_,sheet,row,raw=best
    return sheet,row,raw,norm_to_canonical


def iter_records(path, header_row, wanted_headers=None):
    """
    Read an exported XLSX table robustly.

    Older builds hard-coded xl/worksheets/sheet1.xml and an exact header row. Power BI/
    Excel exports can reorder sheets, insert title rows, or slightly alter header spacing.
    We now auto-detect the worksheet/header while keeping the old header_row as a preference.
    """
    with zipfile.ZipFile(path) as z:
        shared=load_shared(z)
        wanted_headers=set(wanted_headers or []) if wanted_headers is not None else None

        if wanted_headers is None:
            sheet='xl/worksheets/sheet1.xml'
            detected_row=header_row
            header_map_seed=None
            norm_to_canonical={}
        else:
            detected=_detect_table(z,shared,wanted_headers,preferred_header_row=header_row)
            if detected is None:
                return
            sheet,detected_row,header_map_seed,norm_to_canonical=detected

        header_map={}
        wanted_cols=None
        with z.open(sheet) as fh:
            for ev,e in ET.iterparse(fh,events=('end',)):
                if not e.tag.endswith('}row'):
                    continue
                r=int(e.attrib.get('r','0'))
                if r<detected_row:
                    e.clear(); continue
                if r==detected_row:
                    raw=_read_row_cells(e,shared)
                    for col,hraw in raw.items():
                        h=clean(hraw)
                        if wanted_headers is None:
                            header_map[col]=h
                        elif h in wanted_headers:
                            header_map[col]=h
                        else:
                            canonical=norm_to_canonical.get(_header_norm(h))
                            if canonical:
                                header_map[col]=canonical
                    wanted_cols=set(header_map)
                    e.clear(); continue

                vals={}
                ordinal=0
                for c in e:
                    if not c.tag.endswith('}c'):
                        continue
                    ordinal += 1
                    col=_cell_column(c, ordinal)
                    if wanted_cols is not None and col not in wanted_cols:
                        continue
                    key=header_map.get(col)
                    if key:
                        vals[key]=cell_value(c,shared)
                e.clear()
                if vals:
                    yield vals

def load_opportunities():
    W={
'Legal Entity','LegalEntity','MKU','Market Unit','MarketUnit','Potential Customer','PotentialCustomer','Customer','Customer Name','Topic','Opportunity Topic','Project Name','OppID','Opp ID','Opportunity ID','OpportunityID','Opportunity No','Opportunity Number','D365 OppID','D365OpportunityId','D365OpportunityID','D365 Opportunity ID','D365 OPP ID','D365 Opp ID','D365 ID','Owner','Opportunity Owner','Roadmap','Road Map','Roadmap Status','Road Map Status','Roadmap Stage','Road Map Stage','Stage','Opportunity Stage','Channel','Opportunity Channel','Actual OPP Value','Actual OPP Value Margin',
'Full Expect Close Year - Year','Full Expect Close Year - Quarter','Full Expect Close Year - Month','Country','LOBDept','Offering','Sector','SubSector','Leading LoB','STATUS','PROBABILITY','Expected Closing Quarter','Expected Closing Year','CURRENCY','Opportunity Type','BusinessUnit','Probability %','Opp Value SAR','Opp Margin SAR','Expected Closing Date','Expected Close Date','Expected Closure Date','Expected Month','Opportunity Engagement','Opportunity Nature','Account Manager','ACCOUNTMANAGER','PROJECTMANAGER','Sales Manager','Presales Manager/Director','Presales Engineer','Bid Manager','Etimad','Etimad Type','MUST WIN','Mapped Status','OpportunityType'
}
    # Roadmap is a BUSINESS GATE, not an optional attribute. We make finding the
    # column resilient, but we never relax the rule: blank Roadmap => ignore the row.
    roadmap_headers={'Roadmap','Road Map','Roadmap Status','Road Map Status','Roadmap Stage','Road Map Stage'}
    roadmap_norms={_header_norm(x) for x in roadmap_headers}
    with zipfile.ZipFile(FILES['opportunities']) as z:
        shared=load_shared(z)
        detected=_detect_table(z,shared,W,preferred_header_row=3)
        if detected is None:
            raise RuntimeError('Could not identify the List of Opportunities table/header row in any worksheet.')
        _, detected_row, raw_headers, _ = detected
        detected_norms={_header_norm(v) for v in raw_headers.values() if clean(v)}
        if not (detected_norms & roadmap_norms):
            raise RuntimeError(
                f'List of Opportunities header row {detected_row} was found, but no Roadmap column was recognized. '
                'Expected Roadmap/Road Map/Roadmap Status/Roadmap Stage (spacing and line breaks are tolerated). '
                'The previous dashboard snapshot was kept unchanged.'
            )

    out=[]
    for r in iter_records(FILES['opportunities'],3,W):
        oid = clean(r.get('OppID')) or clean(r.get('Opp ID')) or clean(r.get('Opportunity ID')) or clean(r.get('OpportunityID')) or clean(r.get('Opportunity No')) or clean(r.get('Opportunity Number'))
        d365 = clean(r.get('D365 OppID')) or clean(r.get('D365OpportunityId')) or clean(r.get('D365OpportunityID')) or clean(r.get('D365 Opportunity ID')) or clean(r.get('D365 OPP ID')) or clean(r.get('D365 Opp ID')) or clean(r.get('D365 ID'))
        customer = clean(r.get('Potential Customer')) or clean(r.get('PotentialCustomer')) or clean(r.get('Customer')) or clean(r.get('Customer Name'))
        topic = clean(r.get('Topic')) or clean(r.get('Opportunity Topic')) or clean(r.get('Project Name'))
        raw_value = num(r.get('Opp Value SAR')) or num(r.get('Actual OPP Value'))
        roadmap=norm_missing(r.get('Roadmap')) or norm_missing(r.get('Road Map')) or norm_missing(r.get('Roadmap Status')) or norm_missing(r.get('Road Map Status')) or norm_missing(r.get('Roadmap Stage')) or norm_missing(r.get('Road Map Stage'))
        # Original approved business rule: any row whose Roadmap cell is blank/missing is neglected entirely.
        if not roadmap:
            continue
        # Then discard genuinely empty/noise rows even if some stray Roadmap text exists.
        if not (oid or d365 or customer or topic or raw_value):
            continue
        channel=norm_missing(r.get('Channel')) or norm_missing(r.get('Opportunity Channel')) or 'Sales'
        close=excel_iso(r.get('Expected Closing Date') or r.get('Expected Close Date') or r.get('Expected Closure Date'))
        cy=clean(r.get('Full Expect Close Year - Year')) or clean(r.get('Expected Closing Year')) or (str(year_from_iso(close)) if year_from_iso(close) else '')
        try:cy=int(float(cy)) if cy else None
        except:cy=None
        cq=clean(r.get('Full Expect Close Year - Quarter')) or clean(r.get('Expected Closing Quarter')) or q_from_iso(close) or 'Unassigned'
        cm=clean(r.get('Full Expect Close Year - Month')) or clean(r.get('Expected Month')) or m_from_iso(close) or 'Unassigned'
        val=num(r.get('Opp Value SAR')) or num(r.get('Actual OPP Value'))
        mar=num(r.get('Opp Margin SAR')) or num(r.get('Actual OPP Value Margin'))
        p=pct(r.get('Probability %')) or pct(r.get('PROBABILITY'))
        out.append({
'id':oid,'d365Id':d365,'legalEntity':clean(r.get('Legal Entity'),'Unassigned'),'market':clean(r.get('MKU')) or clean(r.get('Market Unit')) or clean(r.get('MarketUnit')) or clean(r.get('Market Unit')) or 'Unassigned','country':clean(r.get('Country'),'Unassigned'),'customer':customer or 'Unassigned','topic':topic,'owner':clean(r.get('Owner')) or clean(r.get('Opportunity Owner')) or 'Unassigned','roadmap':roadmap,'stage':clean(r.get('Stage')) or clean(r.get('Opportunity Stage')) or 'Unassigned','channel':channel,
'actualOppValue':num(r.get('Actual OPP Value')),'actualOppMargin':num(r.get('Actual OPP Value Margin')),
'valueSAR':val,'marginSAR':mar,'weightedValueSAR':val*p,'weightedMarginSAR':mar*p,'probability':p,'closeYear':cy,'closeQuarter':cq,'closeMonth':cm,'closeDate':close,
'status':clean(r.get('STATUS'),'Unassigned'),'mappedStatus':clean(r.get('Mapped Status'),'Unassigned'),'sector':clean(r.get('Sector'),'Unassigned'),'subSector':clean(r.get('SubSector'),'Unassigned'),'lob':clean(r.get('LOBDept'),'Unassigned'),'leadingLob':clean(r.get('Leading LoB'),'Unassigned'),'offering':clean(r.get('Offering'),'Unassigned'),'businessUnit':clean(r.get('BusinessUnit'),'Unassigned'),'opportunityType':clean(r.get('Opportunity Type')) or clean(r.get('OpportunityType')) or 'Unassigned','nature':clean(r.get('Opportunity Nature'),'Unassigned'),'engagement':clean(r.get('Opportunity Engagement'),'Unassigned'),'accountManager':clean(r.get('Account Manager')) or clean(r.get('ACCOUNTMANAGER')) or 'Unassigned','projectManager':clean(r.get('PROJECTMANAGER'),'Unassigned'),'salesManager':clean(r.get('Sales Manager'),'Unassigned'),'presalesManager':clean(r.get('Presales Manager/Director'),'Unassigned'),'presalesEngineer':clean(r.get('Presales Engineer'),'Unassigned'),'bidManager':clean(r.get('Bid Manager'),'Unassigned'),'etimad':clean(r.get('Etimad'),'Unassigned'),'etimadType':clean(r.get('Etimad Type'),'Unassigned'),'mustWin':clean(r.get('MUST WIN'),'Unassigned'),'currency':clean(r.get('CURRENCY'),'Unassigned')
})
    return out

def load_orderbook():
    W={"Awarding Year",'Awarding Date','Award Date','Contract Awarding Date','Awarded Date',"'Cards'[New Marketunit]","'Cards'[Updated Legal Entity]",'Vertical','Customer Name','Contract Name','OB SAR','GM SAR','CM SAR','OB_TYPE',"'Cards'[Company]",'CONTRACTID','Contract ID','CUSTOMERNAME','OpportunityID','Opportunity ID','Project ID','PROJECTID','ProjectID','MarketUnit','Market Unit','Country','LOBDept','Offering','Sector','SubSector','Sub Sector','Leading LoB','Transaction Type','Transaction Status','Quarter','STATUS','OWNER','ACCOUNTMANAGER','PROJECTMANAGER','PROJECTSTATUS','Project Status','Project Stage','PROJECTSTAGE','PROJECTFAMILY','Project Family','PROJECTGROUP','Project Group','Roadmap Status','Opportunity Type','OpportunityType','Opportunity Engagement','Opportunity Nature','OpportunityChannel','SellingCategoryName','UpdatedLOB','LoB','Updated Sector','NewSector','New Vertical',"'Cards'[MKU]"}
    out=[]
    for r in iter_records(FILES['orderbook'],3,W):
        cid=clean(r.get('CONTRACTID')) or clean(r.get('Contract ID')); oid=clean(r.get('OpportunityID')) or clean(r.get('Opportunity ID')); ob=num(r.get('OB SAR')); gm=num(r.get('GM SAR')); cm=num(r.get('CM SAR'))
        if not cid and not oid and not ob and not gm and not cm:continue
        award_date=excel_iso(r.get('Awarding Date') or r.get('Award Date') or r.get('Contract Awarding Date') or r.get('Awarded Date'))
        y=clean(r.get('Awarding Year')) or (str(year_from_iso(award_date)) if year_from_iso(award_date) else '')
        try:y=int(float(y)) if y else None
        except:y=None
        aq=q_from_iso(award_date) or clean(r.get('Quarter')) or 'Unassigned'
        am=m_from_iso(award_date) or 'Unassigned'
        project_id=clean(r.get('Project ID')) or clean(r.get('PROJECTID')) or clean(r.get('ProjectID')) or 'Unassigned'
        project_stage=clean(r.get('Project Stage')) or clean(r.get('PROJECTSTAGE')) or clean(r.get('PROJECTSTATUS')) or clean(r.get('Project Status')) or 'Unassigned'
        out.append({'awardingDate':award_date,'awardingYear':y,'awardingQuarter':aq,'awardingMonth':am,'market':clean(r.get("'Cards'[New Marketunit]")) or clean(r.get('MarketUnit')) or clean(r.get('Market Unit')) or clean(r.get("'Cards'[MKU]")) or 'Unassigned','legalEntity':clean(r.get("'Cards'[Updated Legal Entity]")) or clean(r.get("'Cards'[Company]")) or 'Unassigned','vertical':clean(r.get('Vertical')) or clean(r.get('New Vertical')) or 'Unassigned','customer':clean(r.get('Customer Name')) or clean(r.get('CUSTOMERNAME')) or 'Unassigned','contractName':clean(r.get('Contract Name')) or cid or 'Unassigned','contractId':cid or 'Unassigned','obSAR':ob,'gmSAR':gm,'cmSAR':cm,'obType':clean(r.get('OB_TYPE'),'Unassigned'),'company':clean(r.get("'Cards'[Company]"),'Unassigned'),'opportunityId':oid,'projectId':project_id,'country':clean(r.get('Country'),'Unassigned'),'lob':clean(r.get('LOBDept')) or clean(r.get('UpdatedLOB')) or clean(r.get('LoB')) or 'Unassigned','offering':clean(r.get('Offering'),'Unassigned'),'sector':clean(r.get('Sector')) or clean(r.get('Updated Sector')) or clean(r.get('NewSector')) or 'Unassigned','subSector':clean(r.get('SubSector')) or clean(r.get('Sub Sector')) or 'Unassigned','leadingLob':clean(r.get('Leading LoB'),'Unassigned'),'transactionType':clean(r.get('Transaction Type'),'Unassigned'),'transactionStatus':clean(r.get('Transaction Status'),'Unassigned'),'quarter':clean(r.get('Quarter'),'Unassigned'),'status':clean(r.get('STATUS'),'Unassigned'),'owner':clean(r.get('OWNER'),'Unassigned'),'accountManager':clean(r.get('ACCOUNTMANAGER'),'Unassigned'),'projectManager':clean(r.get('PROJECTMANAGER'),'Unassigned'),'projectStatus':project_stage,'projectStage':project_stage,'projectFamily':clean(r.get('PROJECTFAMILY')) or clean(r.get('Project Family')) or 'Unassigned','projectGroup':clean(r.get('PROJECTGROUP')) or clean(r.get('Project Group')) or 'Unassigned','roadmapStatus':clean(r.get('Roadmap Status'),'Unassigned'),'opportunityType':clean(r.get('Opportunity Type')) or clean(r.get('OpportunityType')) or 'Unassigned','engagement':clean(r.get('Opportunity Engagement'),'Unassigned'),'nature':clean(r.get('Opportunity Nature'),'Unassigned'),'channel':clean(r.get('OpportunityChannel'),'Unassigned'),'sellingCategory':clean(r.get('SellingCategoryName'),'Unassigned')})
    return out

def join_awarded(opps,ob):
    by=defaultdict(list)
    for r in ob:
        if r['opportunityId']:by[nid(r['opportunityId'])].append(r)
    ma=pe=0
    for o in opps:
        if o['roadmap'].lower()!='won':o['award']=None;continue
        c=[r for r in by.get(nid(o['id']),[]) if clean(r['roadmapStatus']).lower()=='won']
        ent=o['legalEntity'].lower(); country=o['country'].lower()
        strict=[r for r in c if r['legalEntity'].lower()==ent and r['country'].lower()==country]
        if strict:c=strict
        else:
            eo=[r for r in c if r['legalEntity'].lower()==ent]
            if eo:c=eo
        if not c:
            o['award']={'matched':False,'obSAR':0,'gmSAR':0,'cmSAR':0,'contracts':0,'awardingYears':[]}
            pe+=1
        else:
            years=sorted({r['awardingYear'] for r in c if r.get('awardingYear')})
            o['award']={
                'matched':True,
                'obSAR':sum(r['obSAR'] for r in c),
                'gmSAR':sum(r['gmSAR'] for r in c),
                'cmSAR':sum(r['cmSAR'] for r in c),
                'contracts':len({r['contractId'] for r in c if r['contractId']!='Unassigned'}),
                'awardingYears':years
            }
            ma+=1
    return ma,pe

def load_targets():
    """Load market targets without assuming sheet1 or fixed row numbers.

    Preferred mode detects the target headers anywhere in the first 100 rows. A fallback
    scans every worksheet for rows containing Egypt/KSA/GM and two numeric values.
    """
    aliases={
        'Market': {'Market','Market Unit','MarketUnit','MKU','Market Unit Name'},
        'OB Target (SAR)': {'OB Target (SAR)','OB Target SAR','OB Target','Order Book Target (SAR)','Order Book Target'},
        'OB Gross Margin Target (SAR)': {'OB Gross Margin Target (SAR)','OB Gross Margin Target SAR','OBM Target (SAR)','OBM Target','GM Target (SAR)','Gross Margin Target (SAR)'},
    }
    wanted=set().union(*aliases.values())
    canonical_by_norm={_header_norm(a):canon for canon,vals in aliases.items() for a in vals}
    out={}

    # First try a normal header-driven table on any worksheet/header row.
    for r in iter_records(FILES['targets'],1,wanted):
        normrow={canonical_by_norm.get(_header_norm(k),k):v for k,v in r.items()}
        market=clean(normrow.get('Market'))
        mk=_canonical_target_market(market)
        if not mk:
            continue
        ob=num(normrow.get('OB Target (SAR)'))
        gm=num(normrow.get('OB Gross Margin Target (SAR)'))
        if ob or gm:
            out[mk]={'obTarget':ob,'gmTarget':gm}

    # Power BI target exports sometimes leave the market header blank. Scan all sheets
    # for recognizable market labels and take the next two numeric cells in that row.
    if not {'Egypt','KSA','GM'}.issubset(out):
        with zipfile.ZipFile(FILES['targets']) as z:
            sh=load_shared(z)
            for sheet in _worksheet_names(z):
                with z.open(sheet) as fh:
                    for ev,e in ET.iterparse(fh,events=('end',)):
                        if not e.tag.endswith('}row'):
                            continue
                        vals=_read_row_cells(e,sh)
                        ordered=[]
                        for col,v in vals.items():
                            ordered.append((col,clean(v)))
                        for i,(col,v) in enumerate(ordered):
                            mk=_canonical_target_market(v)
                            if not mk:
                                continue
                            nums=[]
                            for _,vv in ordered[i+1:]:
                                if clean(vv):
                                    try:
                                        float(str(vv).replace(',','').strip())
                                        nums.append(num(vv))
                                    except Exception:
                                        pass
                                if len(nums)>=2:
                                    break
                            if len(nums)>=2:
                                out[mk]={'obTarget':nums[0],'gmTarget':nums[1]}
                        e.clear()

    missing=[m for m in ('Egypt','KSA','GM') if m not in out]
    if missing:
        raise RuntimeError('Target workbook could not identify target rows for: '+', '.join(missing))
    out['Total']={'obTarget':sum(out[m]['obTarget'] for m in ('Egypt','KSA','GM')),
                  'gmTarget':sum(out[m]['gmTarget'] for m in ('Egypt','KSA','GM'))}
    return out


def _canonical_target_market(v):
    n=_header_norm(v)
    if n in {'egypt','eg'}: return 'Egypt'
    if n in {'ksa','saudiarabia','saudi','kingdomofsaudiarabia'}: return 'KSA'
    if n in {'gm','growingmarkets','growingmarket'}: return 'GM'
    return ''

def load_po_dates():
    """Load PO line dates/analytics with header detection plus a legacy-column fallback."""
    aliases={
        'Accounting Date': {'Accounting Date','AccountingDate','PO Date','Purchase Order Date','Date'},
        'Purchase Order': {'Purchase Order','PurchaseOrder','PO','PO Number','Purchase Order Number','vue_PO[Purchase Order]'},
        'Item': {'Item','Item Name','ItemName','Description','Line Description'},
        'Product': {'Product','Product Name','ProductName','Category','Product Category'},
        'Quantity': {'Quantity','Qty','QTY','Ordered Quantity'},
        'Net SAR': {'Net SAR','Net Amount SAR','NET Line Amount SAR','[NET_Line_Amount_SAR_Measure]'},
        'Gross SAR': {'Gross SAR','Gross Amount SAR','Gross Line Amount SAR','[Gross_Line_Amount_SAR_Measure]'},
    }
    wanted=set().union(*aliases.values())
    canonical_by_norm={_header_norm(a):canon for canon,vals in aliases.items() for a in vals}
    date_map={}
    products=defaultdict(lambda:{'netSAR':0.0,'grossSAR':0.0,'qty':0.0,'lines':0})
    items=defaultdict(lambda:{'netSAR':0.0,'grossSAR':0.0,'qty':0.0,'lines':0})
    recognized=0

    try:
        for r in iter_records(FILES['podates'],1,wanted):
            row={canonical_by_norm.get(_header_norm(k),k):v for k,v in r.items()}
            po=clean(row.get('Purchase Order')); d=excel_iso(row.get('Accounting Date'))
            if not po:
                continue
            recognized+=1
            if d and po not in date_map: date_map[po]=d
            prod=clean(row.get('Product'),'Unassigned'); item=clean(row.get('Item'),'Unassigned')
            ns=num(row.get('Net SAR')); gs=num(row.get('Gross SAR')); q=num(row.get('Quantity'))
            pp=products[prod]; pp['netSAR']+=ns; pp['grossSAR']+=gs; pp['qty']+=q; pp['lines']+=1
            it=items[item]; it['netSAR']+=ns; it['grossSAR']+=gs; it['qty']+=q; it['lines']+=1
    except Exception:
        recognized=0

    # Legacy export fallback: identify the worksheet where the historical I/J columns
    # actually contain date + PO values. This removes the old sheet1-only assumption.
    if recognized == 0 or not date_map:
        date_map={}; products=defaultdict(lambda:{'netSAR':0.0,'grossSAR':0.0,'qty':0.0,'lines':0}); items=defaultdict(lambda:{'netSAR':0.0,'grossSAR':0.0,'qty':0.0,'lines':0})
        with zipfile.ZipFile(FILES['podates']) as z:
            sh=load_shared(z)
            best_sheet=None; best_score=-1
            for sheet in _worksheet_names(z):
                score=0; seen=0
                with z.open(sheet) as fh:
                    for ev,e in ET.iterparse(fh,events=('end',)):
                        if not e.tag.endswith('}row'): continue
                        rr=int(e.attrib.get('r','0'))
                        if rr<=1: e.clear(); continue
                        vals=_read_row_cells(e,sh)
                        if clean(vals.get('J')): score+=2
                        if excel_iso(vals.get('I')): score+=1
                        seen+=1; e.clear()
                        if seen>=40: break
                if score>best_score: best_score=score; best_sheet=sheet
            if not best_sheet or best_score<=0:
                raise RuntimeError('Purchase Order Details table could not be identified in any worksheet.')
            with z.open(best_sheet) as fh:
                for ev,e in ET.iterparse(fh,events=('end',)):
                    if not e.tag.endswith('}row'): continue
                    rr=int(e.attrib.get('r','0'))
                    if rr<=1: e.clear(); continue
                    vals={}
                    for c in e:
                        if not c.tag.endswith('}c'): continue
                        col=col_letters(c.attrib.get('r',''))
                        if col in {'I','J','L','M','O','Q','T'}: vals[col]=cell_value(c,sh)
                    po=clean(vals.get('J')); d=excel_iso(vals.get('I'))
                    if po and d and po not in date_map: date_map[po]=d
                    prod=clean(vals.get('M'),'Unassigned'); item=clean(vals.get('L'),'Unassigned'); ns=num(vals.get('Q')); gs=num(vals.get('T')); q=num(vals.get('O'))
                    pp=products[prod];pp['netSAR']+=ns;pp['grossSAR']+=gs;pp['qty']+=q;pp['lines']+=1
                    it=items[item];it['netSAR']+=ns;it['grossSAR']+=gs;it['qty']+=q;it['lines']+=1
                    e.clear()

    pro=[{'name':k,**v} for k,v in products.items() if k!='Unassigned'];pro.sort(key=lambda x:abs(x['netSAR']),reverse=True)
    it=[{'name':k,**v} for k,v in items.items() if k!='Unassigned'];it.sort(key=lambda x:abs(x['netSAR']),reverse=True)
    return date_map,pro[:100],it[:100]

def load_po(dm):
    W={'vue_PO[Vendor Account]','vue_PO[Vendor Name]','vue_PO[Partner]','vue_PO[Partner Name]','LocalDateTable_c6df8034-a093-4bd1-ab8d-0ac4e2afb046[Year]','LocalDateTable_c6df8034-a093-4bd1-ab8d-0ac4e2afb046[Quarter]','vue_PO[New Marketunit]','vue_PO[Country]','vue_PO[New Vertical Name]','vue_PO[Contract Name]','vue_PO[Contract ID]','vue_PO[Project ID]','vue_PO[Customer Name]','vue_PO[Project Manager]','vue_ProjectsData[Contract Currency]','vue_PO[Purchase Order]','vue_PO[Submitting User]','vue_PO[Currency]','[NET_Line_Amount_Measure]','[NET_Line_Amount_SAR_Measure]','[Gross_Line_Amount_Measure]','[Gross_Line_Amount_SAR_Measure]'}
    out=[];matches=0
    for r in iter_records(FILES['po'],1,W):
        po=clean(r.get('vue_PO[Purchase Order]'))
        if not po:continue
        d=dm.get(po,'')
        if d:matches+=1
        y=year_from_iso(d) if d else None
        if y is None:
            try:y=int(float(clean(r.get('LocalDateTable_c6df8034-a093-4bd1-ab8d-0ac4e2afb046[Year]'))))
            except:y=None
        q=q_from_iso(d) if d else clean(r.get('LocalDateTable_c6df8034-a093-4bd1-ab8d-0ac4e2afb046[Quarter]')) or 'Unassigned'
        m=m_from_iso(d) if d else 'Unassigned'
        out.append({'purchaseOrder':po,'accountingDate':d,'year':y,'quarter':q,'month':m,'vendorAccount':clean(r.get('vue_PO[Vendor Account]'),'Unassigned'),'vendor':clean(r.get('vue_PO[Vendor Name]'),'Unassigned'),'partner':clean(r.get('vue_PO[Partner]'),'Unassigned'),'partnerName':clean(r.get('vue_PO[Partner Name]'),'Unassigned'),'market':clean(r.get('vue_PO[New Marketunit]'),'Unassigned'),'country':clean(r.get('vue_PO[Country]'),'Unassigned'),'vertical':clean(r.get('vue_PO[New Vertical Name]'),'Unassigned'),'contractName':clean(r.get('vue_PO[Contract Name]'),'Unassigned'),'contractId':clean(r.get('vue_PO[Contract ID]'),'Unassigned'),'projectId':clean(r.get('vue_PO[Project ID]'),'Unassigned'),'customer':clean(r.get('vue_PO[Customer Name]'),'Unassigned'),'projectManager':clean(r.get('vue_PO[Project Manager]'),'Unassigned'),'contractCurrency':clean(r.get('vue_ProjectsData[Contract Currency]'),'Unassigned'),'submittingUser':clean(r.get('vue_PO[Submitting User]'),'Unassigned'),'currency':clean(r.get('vue_PO[Currency]'),'Unassigned'),'netAmount':num(r.get('[NET_Line_Amount_Measure]')),'netSAR':num(r.get('[NET_Line_Amount_SAR_Measure]')),'grossAmount':num(r.get('[Gross_Line_Amount_Measure]')),'grossSAR':num(r.get('[Gross_Line_Amount_SAR_Measure]'))})
    return out,matches


