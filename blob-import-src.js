import { upload } from '@vercel/blob/client';

function modal(){ return document.getElementById('manualImportModal'); }
function rowFor(key){ return document.querySelector(`.manual-import-row[data-dataset="${key}"]`); }

function setRowStatus(row, text, mode=''){
  const el=row?.querySelector('.manual-import-status');
  if(!el) return;
  el.className=`manual-import-status${mode?` ${mode}`:''}`;
  el.textContent=text||'';
}

async function importDataset(row){
  const dataset=row.dataset.dataset;
  const input=row.querySelector('input[type=file]');
  const button=row.querySelector('.manual-import-go');
  const file=input?.files?.[0];
  if(!file){ setRowStatus(row,'Choose an .xlsx workbook first.','error'); return; }
  if(!/\.xlsx$/i.test(file.name)){ setRowStatus(row,'Only .xlsx workbooks are accepted.','error'); return; }

  button.disabled=true;
  try{
    setRowStatus(row,'Uploading to shared Blob storage…','loading');
    const safe=file.name.replace(/[^A-Za-z0-9._-]+/g,'_');
    const blob=await upload(`incoming/${dataset}/${Date.now()}-${safe}`,file,{
      access:'private',
      handleUploadUrl:'/api/blob_upload',
      clientPayload:JSON.stringify({dataset}),
      multipart:true,
      onUploadProgress:p=>setRowStatus(row,`Uploading ${Math.round(p.percentage||0)}%…`,'loading'),
    });

    setRowStatus(row,'Validating, processing and publishing…','loading');
    const res=await fetch('/api/import_process',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({dataset,pathname:blob.pathname,fileName:file.name}),
    });
    const msg=await res.json();
    if(!res.ok||!msg.ok) throw new Error(msg.error||'Import failed.');

    input.value='';
    setRowStatus(row,'Imported successfully.','ok');
    if(window.dashboardReloadImportedScope) await window.dashboardReloadImportedScope();
  }catch(e){
    console.error(e);
    setRowStatus(row,e.message||String(e),'error');
  }finally{
    button.disabled=false;
  }
}

function bind(){
  const m=modal();
  document.getElementById('importDataBtn')?.addEventListener('click',()=>m?.classList.add('show'));
  document.getElementById('manualImportClose')?.addEventListener('click',()=>m?.classList.remove('show'));
  m?.addEventListener('click',e=>{if(e.target===m)m.classList.remove('show');});
  document.querySelectorAll('.manual-import-row').forEach(row=>{
    row.querySelector('.manual-import-go')?.addEventListener('click',()=>importDataset(row));
  });
}

if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',bind); else bind();
