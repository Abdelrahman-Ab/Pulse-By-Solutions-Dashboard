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
    return ''.join(ch for ch in ref if ch.isalpha())

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

def iter_records(path, header_row, wanted_headers=None):
    with zipfile.ZipFile(path) as z:
        shared=load_shared(z)
        header_map={}
        wanted_cols=None
        with z.open('xl/worksheets/sheet1.xml') as fh:
            for ev,e in ET.iterparse(fh,events=('end',)):
                if not e.tag.endswith('}row'): continue
                r=int(e.attrib.get('r','0'))
                if r<header_row:
                    e.clear(); continue
                if r==header_row:
                    for c in e:
                        if c.tag.endswith('}c'):
                            header_map[col_letters(c.attrib.get('r',''))]=clean(cell_value(c,shared))
                    if wanted_headers is None:
                        wanted_cols=set(header_map)
                    else:
                        wanted_cols={col for col,h in header_map.items() if h in wanted_headers}
                    e.clear(); continue
                vals={}
                for c in e:
                    if not c.tag.endswith('}c'):continue
                    col=col_letters(c.attrib.get('r',''))
                    if wanted_cols is None or col in wanted_cols:
                        vals[header_map.get(col,col)]=cell_value(c,shared)
                e.clear()
                yield vals

def load_opportunities():
    W={
'Legal Entity','MKU','Potential Customer','Topic','OppID','D365OpportunityId','Owner','Roadmap','Stage','Channel','Actual OPP Value','Actual OPP Value Margin',
'Full Expect Close Year - Year','Full Expect Close Year - Quarter','Full Expect Close Year - Month','Country','LOBDept','Offering','Sector','SubSector','Leading LoB','STATUS','PROBABILITY','Expected Closing Quarter','Expected Closing Year','CURRENCY','Opportunity Type','BusinessUnit','Probability %','Opp Value SAR','Opp Margin SAR','Expected Closing Date','Expected Month','Opportunity Engagement','Opportunity Nature','Account Manager','ACCOUNTMANAGER','PROJECTMANAGER','Sales Manager','Presales Manager/Director','Presales Engineer','Bid Manager','Etimad','Etimad Type','MUST WIN','Mapped Status','OpportunityType'
}
    out=[]
    for r in iter_records(FILES['opportunities'],3,W):
        roadmap=norm_missing(r.get('Roadmap'))
        if not roadmap:continue
        channel=norm_missing(r.get('Channel'),'Sales') or 'Sales'
        close=excel_iso(r.get('Expected Closing Date'))
        cy=clean(r.get('Full Expect Close Year - Year')) or clean(r.get('Expected Closing Year')) or (str(year_from_iso(close)) if year_from_iso(close) else '')
        try:cy=int(float(cy)) if cy else None
        except:cy=None
        cq=clean(r.get('Full Expect Close Year - Quarter')) or clean(r.get('Expected Closing Quarter')) or q_from_iso(close) or 'Unassigned'
        cm=clean(r.get('Full Expect Close Year - Month')) or clean(r.get('Expected Month')) or m_from_iso(close) or 'Unassigned'
        val=num(r.get('Opp Value SAR')) or num(r.get('Actual OPP Value'))
        mar=num(r.get('Opp Margin SAR')) or num(r.get('Actual OPP Value Margin'))
        p=pct(r.get('Probability %')) or pct(r.get('PROBABILITY'))
        out.append({
'id':clean(r.get('OppID')),'d365Id':clean(r.get('D365OpportunityId')),'legalEntity':clean(r.get('Legal Entity'),'Unassigned'),'market':clean(r.get('MKU'),'Unassigned'),'country':clean(r.get('Country'),'Unassigned'),'customer':clean(r.get('Potential Customer'),'Unassigned'),'topic':clean(r.get('Topic')),'owner':clean(r.get('Owner'),'Unassigned'),'roadmap':roadmap,'stage':clean(r.get('Stage'),'Unassigned'),'channel':channel,
'actualOppValue':num(r.get('Actual OPP Value')),'actualOppMargin':num(r.get('Actual OPP Value Margin')),
'valueSAR':val,'marginSAR':mar,'weightedValueSAR':val*p,'weightedMarginSAR':mar*p,'probability':p,'closeYear':cy,'closeQuarter':cq,'closeMonth':cm,'closeDate':close,
'status':clean(r.get('STATUS'),'Unassigned'),'mappedStatus':clean(r.get('Mapped Status'),'Unassigned'),'sector':clean(r.get('Sector'),'Unassigned'),'subSector':clean(r.get('SubSector'),'Unassigned'),'lob':clean(r.get('LOBDept'),'Unassigned'),'leadingLob':clean(r.get('Leading LoB'),'Unassigned'),'offering':clean(r.get('Offering'),'Unassigned'),'businessUnit':clean(r.get('BusinessUnit'),'Unassigned'),'opportunityType':clean(r.get('Opportunity Type')) or clean(r.get('OpportunityType')) or 'Unassigned','nature':clean(r.get('Opportunity Nature'),'Unassigned'),'engagement':clean(r.get('Opportunity Engagement'),'Unassigned'),'accountManager':clean(r.get('Account Manager')) or clean(r.get('ACCOUNTMANAGER')) or 'Unassigned','projectManager':clean(r.get('PROJECTMANAGER'),'Unassigned'),'salesManager':clean(r.get('Sales Manager'),'Unassigned'),'presalesManager':clean(r.get('Presales Manager/Director'),'Unassigned'),'presalesEngineer':clean(r.get('Presales Engineer'),'Unassigned'),'bidManager':clean(r.get('Bid Manager'),'Unassigned'),'etimad':clean(r.get('Etimad'),'Unassigned'),'etimadType':clean(r.get('Etimad Type'),'Unassigned'),'mustWin':clean(r.get('MUST WIN'),'Unassigned'),'currency':clean(r.get('CURRENCY'),'Unassigned')
})
    return out

def load_orderbook():
    W={"Awarding Year","'Cards'[New Marketunit]","'Cards'[Updated Legal Entity]",'Vertical','Customer Name','Contract Name','OB SAR','GM SAR','CM SAR','OB_TYPE',"'Cards'[Company]",'CONTRACTID','CUSTOMERNAME','OpportunityID','MarketUnit','Country','LOBDept','Offering','Sector','SubSector','Leading LoB','Transaction Type','Transaction Status','Quarter','STATUS','OWNER','ACCOUNTMANAGER','PROJECTMANAGER','PROJECTSTATUS','PROJECTFAMILY','Project Family','PROJECTGROUP','Project Group','Roadmap Status','Opportunity Type','OpportunityType','Opportunity Engagement','Opportunity Nature','OpportunityChannel','SellingCategoryName','UpdatedLOB','LoB','Updated Sector','NewSector','New Vertical',"'Cards'[MKU]"}
    out=[]
    for r in iter_records(FILES['orderbook'],3,W):
        cid=clean(r.get('CONTRACTID')); oid=clean(r.get('OpportunityID')); ob=num(r.get('OB SAR')); gm=num(r.get('GM SAR')); cm=num(r.get('CM SAR'))
        if not cid and not oid and not ob and not gm and not cm:continue
        y=clean(r.get('Awarding Year'))
        try:y=int(float(y)) if y else None
        except:y=None
        out.append({'awardingYear':y,'market':clean(r.get("'Cards'[New Marketunit]")) or clean(r.get('MarketUnit')) or clean(r.get("'Cards'[MKU]")) or 'Unassigned','legalEntity':clean(r.get("'Cards'[Updated Legal Entity]")) or clean(r.get("'Cards'[Company]")) or 'Unassigned','vertical':clean(r.get('Vertical')) or clean(r.get('New Vertical')) or 'Unassigned','customer':clean(r.get('Customer Name')) or clean(r.get('CUSTOMERNAME')) or 'Unassigned','contractName':clean(r.get('Contract Name')) or cid or 'Unassigned','contractId':cid or 'Unassigned','obSAR':ob,'gmSAR':gm,'cmSAR':cm,'obType':clean(r.get('OB_TYPE'),'Unassigned'),'company':clean(r.get("'Cards'[Company]"),'Unassigned'),'opportunityId':oid,'country':clean(r.get('Country'),'Unassigned'),'lob':clean(r.get('LOBDept')) or clean(r.get('UpdatedLOB')) or clean(r.get('LoB')) or 'Unassigned','offering':clean(r.get('Offering'),'Unassigned'),'sector':clean(r.get('Sector')) or clean(r.get('Updated Sector')) or clean(r.get('NewSector')) or 'Unassigned','subSector':clean(r.get('SubSector'),'Unassigned'),'leadingLob':clean(r.get('Leading LoB'),'Unassigned'),'transactionType':clean(r.get('Transaction Type'),'Unassigned'),'transactionStatus':clean(r.get('Transaction Status'),'Unassigned'),'quarter':clean(r.get('Quarter'),'Unassigned'),'status':clean(r.get('STATUS'),'Unassigned'),'owner':clean(r.get('OWNER'),'Unassigned'),'accountManager':clean(r.get('ACCOUNTMANAGER'),'Unassigned'),'projectManager':clean(r.get('PROJECTMANAGER'),'Unassigned'),'projectStatus':clean(r.get('PROJECTSTATUS'),'Unassigned'),'projectFamily':clean(r.get('PROJECTFAMILY')) or clean(r.get('Project Family')) or 'Unassigned','projectGroup':clean(r.get('PROJECTGROUP')) or clean(r.get('Project Group')) or 'Unassigned','roadmapStatus':clean(r.get('Roadmap Status'),'Unassigned'),'opportunityType':clean(r.get('Opportunity Type')) or clean(r.get('OpportunityType')) or 'Unassigned','engagement':clean(r.get('Opportunity Engagement'),'Unassigned'),'nature':clean(r.get('Opportunity Nature'),'Unassigned'),'channel':clean(r.get('OpportunityChannel'),'Unassigned'),'sellingCategory':clean(r.get('SellingCategoryName'),'Unassigned')})
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
    rows=list(iter_records(FILES['targets'],1,{'OB Target (SAR)','OB Gross Margin Target (SAR)'}))
    # target workbook's market is column A with blank header, so parse raw sheet directly instead.
    with zipfile.ZipFile(FILES['targets']) as z:
        sh=load_shared(z); arr=[]
        with z.open('xl/worksheets/sheet1.xml') as fh:
            for ev,e in ET.iterparse(fh,events=('end',)):
                if e.tag.endswith('}row'):
                    r=int(e.attrib.get('r','0'))
                    if 2<=r<=4:
                        vals={}
                        for c in e:
                            if c.tag.endswith('}c'):vals[col_letters(c.attrib.get('r',''))]=cell_value(c,sh)
                        arr.append((clean(vals.get('A')),num(vals.get('B')),num(vals.get('C'))))
                    e.clear()
    out={m:{'obTarget':ob,'gmTarget':gm} for m,ob,gm in arr}
    out['Total']={'obTarget':sum(v['obTarget'] for v in out.values()),'gmTarget':sum(v['gmTarget'] for v in out.values())}
    return out

def load_po_dates():
    # Directly stream the line-level file and keep only the date lookup + aggregate product/item analytics.
    with zipfile.ZipFile(FILES['podates']) as z:
        sh=load_shared(z); date_map={}; products=defaultdict(lambda:{'netSAR':0.0,'grossSAR':0.0,'qty':0.0,'lines':0}); items=defaultdict(lambda:{'netSAR':0.0,'grossSAR':0.0,'qty':0.0,'lines':0})
        with z.open('xl/worksheets/sheet1.xml') as fh:
            for ev,e in ET.iterparse(fh,events=('end',)):
                if not e.tag.endswith('}row'):continue
                rr=int(e.attrib.get('r','0'))
                if rr<=1:e.clear();continue
                vals={}
                for c in e:
                    if not c.tag.endswith('}c'):continue
                    col=col_letters(c.attrib.get('r',''))
                    if col in {'I','J','L','M','O','Q','T'}:vals[col]=cell_value(c,sh)
                po=clean(vals.get('J')); d=excel_iso(vals.get('I'))
                if po and d and po not in date_map:date_map[po]=d
                prod=clean(vals.get('M'),'Unassigned'); item=clean(vals.get('L'),'Unassigned'); ns=num(vals.get('Q')); gs=num(vals.get('T')); q=num(vals.get('O'))
                p=products[prod];p['netSAR']+=ns;p['grossSAR']+=gs;p['qty']+=q;p['lines']+=1
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


