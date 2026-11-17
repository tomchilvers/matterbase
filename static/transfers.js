import {escapeHtml as escape,formatPairingCode} from './inventory.mjs';
import {deviceLabel} from './duplicates.mjs';
const $=s=>document.querySelector(s);
let entries=[],busy=false;
async function post(url,body) {
 const response=await fetch(url.replace(/^\//,''),{method:'POST',headers:{'Content-Type':'application/json','X-Matterbase-Request':'1'},body:JSON.stringify(body)});
 const result=await response.json();
 if(!response.ok)throw new Error(result.error || 'Could not import this backup.');
 return result;
}
function updateApplyLabel() {
 const added=entries.filter(e=>e.action==='add').length,overwritten=entries.filter(e=>e.action==='overwrite').length;
 $('#apply-import').textContent=overwritten?`Add ${added} & overwrite ${overwritten} saved device${overwritten===1?'':'s'}`:`Import ${added} device${added===1?'':'s'}`;
 $('#apply-import').disabled=busy || (!added && !overwritten);
}
function clearPreview() {entries=[];$('#import-preview').hidden=true;$('#import-list').replaceChildren();}
function setBusy(value) {
 busy=value;
 for(const input of $('#backup-tools').querySelectorAll('button,input,textarea,select'))input.disabled=value;
 updateApplyLabel();
}
function message(text,error=false) {$('#import-status').textContent=text;$('#import-status').classList.toggle('error',error);}
$('#backup-file').addEventListener('change',async e=>{
 clearPreview();message('');
 const file=e.target.files[0];if(!file)return;
 if(file.size>16*1024*1024){message('Choose a JSON backup smaller than 16 MB.',true);return;}
 try {$('#backup-json').value=await file.text();message('Backup loaded. Preview it before importing.');}
 catch {message('Could not read this file. Try choosing it again.',true);}
});
$('#backup-json').addEventListener('input',()=>{clearPreview();message('');});
$('#preview-import').onclick=async()=>{
 if(busy)return;clearPreview();setBusy(true);message('Checking backup…');
 try {
  let backup;try{backup=JSON.parse($('#backup-json').value);}catch{throw new Error('Choose a Matterbase JSON backup or paste its contents below.');}
  const result=await post('/api/import/preview',{backup});
  entries=result.devices.map(entry=>({...entry,action:entry.original?'skip':'add'}));
  $('#import-list').innerHTML=entries.map(({device,original},i)=>`<article class="import-entry"><h3>${escape(deviceLabel(device))}</h3><p class="hint">${escape([device.brand,device.product].filter(Boolean).join(' '))} · <code>${escape(formatPairingCode(device.manual_code))}</code></p>${original?`<p>Duplicate of <strong>${escape(deviceLabel(original))}</strong></p>`:''}<details><summary>Incoming details</summary><dl><dt>Name / location</dt><dd>${escape(device.name || 'Not set')}</dd><dt>Notes</dt><dd>${escape(device.notes || 'No notes')}</dd><dt>Colour / icon</dt><dd>${escape(device.color || 'None')} / ${escape(device.icon || 'None')}</dd><dt>Date added</dt><dd>${escape(device.created_at || 'Not provided')}</dd><dt>Last updated</dt><dd>${escape(device.updated_at || 'Not provided')}</dd><dt>Original QR</dt><dd>${device.qr_payload?'Included':'Not included'}</dd></dl></details><label>Import choice<select data-import-choice="${i}" aria-label="Import choice for ${escape(deviceLabel(device))}">${original?'<option value="skip">Skip duplicate</option><option value="overwrite">Overwrite original</option>':'<option value="add">Add device</option><option value="skip">Skip device</option>'}</select></label></article>`).join('');
  $('#import-preview').hidden=false;
  const duplicates=entries.filter(e=>e.original).length;
  message(`${entries.length} device${entries.length===1?'':'s'} found; ${duplicates} duplicate${duplicates===1?'':'s'} set to Skip. Nothing has been saved.`);
  $('#apply-import').hidden=!entries.length;
 }catch(error){message(error.message,true);}
 finally{setBusy(false);}
};
$('#import-list').addEventListener('change',e=>{if(e.target.dataset.importChoice!==undefined){entries[Number(e.target.dataset.importChoice)].action=e.target.value;updateApplyLabel();}});
$('#cancel-import').onclick=()=>{clearPreview();message('Import cancelled. Inventory unchanged.');};
$('#apply-import').onclick=async()=>{
 if(busy || !entries.length)return;
 setBusy(true);message('Importing…');
 try {
  const result=await post('/api/import',{devices:entries.map(({device,original,action})=>({device,action,expected_id:original?.id,expected_revision:original?.revision}))});
  clearPreview();$('#backup-json').value='';$('#backup-file').value='';
  message(`Import complete: ${result.created} added, ${result.updated} overwritten, ${result.skipped} skipped.`);
  document.dispatchEvent(new Event('inventory-imported'));
 }catch(error){clearPreview();message(error.message,true);}
 finally{setBusy(false);}
};
