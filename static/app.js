import {request,pairingQrUrl,exportBackup} from './platform.mjs';
import {codeKey,deviceLabel,collectScan,chooseOverwrite,excludeScanCode,reconcileSaveConflicts} from './duplicates.mjs';
import {escapeHtml as escape,formatPairingCode as display,resolveInventorySelection,toggleInventorySelection,inventoryRow,inventoryDetails} from './inventory.mjs';

const $ = (s) => document.querySelector(s);
const state = { devices: [], pending: [], duplicates: [], excludedCodes: new Set(), stream: null, loop: null, scanning: false, saving: false, generation: 0, mode: 'camera', edit: null, editDirty: false, editSaving: false, selectedId: null, detailOpen: false, qrVisible: false, batchEdited: new Set() };
const icons = {
  device: '<svg class="icon" viewBox="0 0 24 24"><rect x="5" y="3" width="14" height="18" rx="3"/><path d="M9 8h6m-6 4h6m-6 4h2"/></svg>',
  bulb: '<svg class="icon" viewBox="0 0 24 24"><path d="M9 18h6m-5 3h4M8 14a6 6 0 1 1 8 0c-1 .8-1 2-1 2H9s0-1.2-1-2z"/></svg>',
  switch: '<svg class="icon" viewBox="0 0 24 24"><rect x="6" y="2" width="12" height="20" rx="6"/><circle cx="12" cy="7" r="1.5"/><circle cx="12" cy="17" r="1"/></svg>',
  plug: '<svg class="icon" viewBox="0 0 24 24"><path d="M9 2v5m6-5v5M7 7h10v5a5 5 0 0 1-10 0zm5 10v5"/></svg>',
  sensor: '<svg class="icon" viewBox="0 0 24 24"><rect x="7" y="3" width="10" height="18" rx="3"/><circle cx="12" cy="9" r="2"/><path d="M11 17h2"/></svg>',
  copy: '<svg class="icon" viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M15 8V3H3v12h5"/></svg>',
};
const iconNames = {'':'No icon',bulb:'Bulb',switch:'Switch / remote',plug:'Plug',sensor:'Sensor'};
function colourName(value) {
  if (!/^#[0-9a-f]{6}$/i.test(value || '')) return 'No colour';
  const [r,g,b] = [1,3,5].map(i => parseInt(value.slice(i,i+2),16));
  const max = Math.max(r,g,b), min = Math.min(r,g,b), delta = max-min;
  if (delta < 12) return max > 225 ? 'White' : max < 65 ? 'Black' : 'Grey';
  let hue = 60*(max===r ? ((g-b)/delta)%6 : max===g ? (b-r)/delta+2 : (r-g)/delta+4);
  if (hue < 0) hue += 360;
  if (hue > 20 && hue < 70 && max > 170 && min > 140 && delta/max < .35) return 'Cream';
  return hue < 12 || hue >= 345 ? 'Red' : hue < 45 ? 'Orange' : hue < 70 ? 'Yellow' : hue < 155 ? 'Green' : hue < 195 ? 'Teal' : hue < 255 ? 'Blue' : hue < 290 ? 'Purple' : 'Pink';
}
function colourDot(value) {
  return /^#[0-9a-f]{6}$/i.test(value || '') ? `<svg class="colour-dot" viewBox="0 0 24 24" role="img" aria-label="${colourName(value)} label"><circle cx="12" cy="12" r="10" fill="${value}"/></svg>` : '';
}
function appearanceControls(device,index) {
  const context = index === 'edit' ? 'edit' : `code-${index}`;
  return `<div class="appearance-fields" data-appearance="${index}"><fieldset><legend>Label colour</legend><div class="colour-controls"><input type="color" value="${device.color || '#6a9a8b'}" data-colour-picker="${index}" aria-label="Choose label colour for ${context}"><span class="colour-name">${colourName(device.color)}</span><button type="button" class="quiet clear-colour" data-clear-colour="${index}">None</button></div></fieldset><label>Device icon<select data-icon-picker="${index}" aria-label="Device icon for ${context}">${Object.entries(iconNames).map(([value,name]) => `<option value="${value}" ${device.icon===value?'selected':''}>${name}</option>`).join('')}</select></label><div class="marker-preview" aria-label="Selected label marker">${colourDot(device.color)}${icons[device.icon] || icons.device}</div></div>${device.appearance_source ? '<p class="hint marker-hint">Marker suggested from label. Check the colour and icon before saving.</p>' : ''}`;
}
let toastTimer;
function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').hidden = true, 3200); }
async function api(url, options = {}) {
  if(options.method && !['GET','HEAD'].includes(options.method.toUpperCase())) {
    const headers=new Headers(options.headers);headers.set('X-Matterbase-Request','1');options={...options,headers};
  }
  const response = await request(url, options);
  if (response.status === 204) return null;
  let body;
  try { body = await response.json(); } catch { throw new Error('The server returned an unexpected response. Please try again.'); }
  if (!response.ok) {
    const error = new Error(body.error || 'Something went wrong. Please try again.');
    error.status=response.status;error.conflicts=body.conflicts;throw error;
  }
  return body;
}
function jsonOptions(method, body) { return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}; }
async function loadDevices() {
  try { state.devices = await api('/api/devices'); $('#library-status').textContent = ''; renderLibrary(); updateKnownNames(); }
  catch (error) { $('#library-status').textContent = `Could not load devices: ${error.message} Refresh to try again.`; $('#empty').hidden = true; }
}
const inventoryDesktop=window.matchMedia('(min-width: 960px)');
function matchingDevices() {
  const query=$('#search').value.trim().toLowerCase(),digits=query.replace(/[\s-]/g,'');
  return state.devices.filter(d=>[d.brand,d.product,d.name,d.notes,d.manual_code,d.qr_payload,colourName(d.color),iconNames[d.icon]].join(' ').toLowerCase().includes(query) || (digits && d.manual_code.includes(digits)));
}
function marker(device) {return (icons[device.icon] || icons.device)+colourDot(device.color);}
function renderLibrary() {
  const matches=matchingDevices(),desktop=inventoryDesktop.matches;
  Object.assign(state,resolveInventorySelection(matches,state,desktop));
  const host=$('#device-detail-host'),panel=$('#device-detail-panel');
  const focused=panel.contains(document.activeElement)?document.activeElement:null;
  const scroll=panel.scrollTop;
  // Move the one detail panel out before rebuilding mobile rows. The edit form
  // remains the same DOM node, preserving input values and unsaved drafts.
  if(panel.parentElement!==host)host.append(panel);
  $('#empty').hidden=state.devices.length>0;
  $('#no-results').hidden=!state.devices.length || matches.length>0;

  $('#inventory-layout').hidden=!matches.length;
  $('#search').disabled=!!state.edit;
  $('#device-list').innerHTML=matches.map(d=>inventoryRow(d,{
    selected:d.id===state.selectedId,expanded:d.id===state.selectedId && state.detailOpen,desktop,marker:marker(d)
  })).join('');
  const device=matches.find(d=>d.id===state.selectedId);
  panel.hidden=!device || !state.detailOpen;
  $('#device-details-content').hidden=!!state.edit;
  $('#edit-form').hidden=!state.edit;
  $('#device-details-content').innerHTML=device && state.detailOpen ? inventoryDetails(device,{
    marker:marker(device),colour:colourName(device.color),icon:iconNames[device.icon],qrVisible:state.qrVisible,qrUrl:state.qrVisible?pairingQrUrl(device):undefined,homeAssistantHelp:document.body.dataset.homeAssistantHelp==='true'
  }):'';
  if(device && state.detailOpen) {
    panel.setAttribute('aria-labelledby',`device-trigger-${device.id}`);
    if(!desktop)document.getElementById(`device-row-${device.id}`).append(panel);
  }
  panel.scrollTop=scroll;
  if(state.edit && focused?.isConnected)focused.focus({preventScroll:true});
}
function canLeaveEdit() {
  if(state.editSaving){toast('Saving changes…');return false;}
  if(state.editDirty && !confirm('Discard unsaved changes to this device?'))return false;
  state.edit=null;state.editDirty=false;return true;
}
function selectDevice(id,keyboard=false) {
  if(state.edit && !canLeaveEdit())return;
  Object.assign(state,toggleInventorySelection(state,id,inventoryDesktop.matches));
  renderLibrary();
  const trigger=document.getElementById(`device-trigger-${id}`);
  trigger?.focus({preventScroll:!keyboard});
  if(!inventoryDesktop.matches)trigger?.scrollIntoView({block:'nearest'});
}
function cancelEdit() {
  if(state.editSaving)return;
  state.edit=null;state.editDirty=false;renderLibrary();
  $('#device-details-content [data-edit]')?.focus({preventScroll:true});
}
inventoryDesktop.addEventListener('change',()=>renderLibrary());
function showLibrary() {
  if(state.edit && !canLeaveEdit())return;
  if ((state.pending.length || state.duplicates.length) && !confirm('Discard these unsaved codes and duplicate choices?')) return;
  stopCamera(); state.generation++; state.pending = []; state.duplicates=[];state.excludedCodes.clear();resetForm();
  $('#add-view').hidden = true; $('#library').hidden = false;
  $('#nav-devices').classList.add('active'); $('#nav-add').classList.remove('active');
  document.title = 'Matterbase · Your devices';
  renderLibrary();window.scrollTo(0, 0);
}
function resetForm() {
  $('#brand').value = ''; $('#product').value = ''; $('#manual-code').value = ''; $('#photo').value = '';
  $('#preview').hidden = true; $('#preview').removeAttribute('src'); $('#text-review').hidden = true;
  $('#identity-suggestions').hidden = true; state.batchEdited.clear(); clearCaptureFeedback();
  status(''); renderPending();
}
function showAdd(mode = 'camera') {
  if(state.edit && !canLeaveEdit())return;
  $('#library').hidden = true; $('#add-view').hidden = false;
  $('#nav-devices').classList.remove('active'); $('#nav-add').classList.add('active');
  document.title = 'Matterbase · Add devices'; setMode(mode); window.scrollTo(0, 0);
}
function setMode(mode) {
  stopCamera(); state.mode = mode;
  document.querySelectorAll('[data-mode]').forEach(b => { b.classList.toggle('active', b.dataset.mode === mode); b.setAttribute('aria-pressed', String(b.dataset.mode === mode)); });
  for (const panel of ['camera', 'photo', 'manual']) $(`#${panel}-panel`).hidden = panel !== mode;
  if (mode === 'manual') $('#manual-code').focus();
}
function status(message, error = false) { $('#scan-status').textContent = message; $('#scan-status').classList.toggle('error', error); }
function duplicateStatus() {
  return state.duplicates.length===1 ? `This is a duplicate of “${deviceLabel(state.duplicates[0].original)}”. Choose Exclude or Overwrite below.` : `${state.duplicates.length} saved duplicates need a choice below.`;
}
function refreshSaveButton() {
  const count=state.pending.length, updates=state.pending.filter(d=>d.overwrite_id).length;
  $('#save').disabled=!count || !!state.duplicates.length || state.saving || state.scanning;
  $('#save').textContent=state.saving ? 'Saving…' : state.duplicates.length ? `Resolve ${state.duplicates.length} duplicate${state.duplicates.length===1?'':'s'} to continue` : updates ?
    (count===updates ? `Overwrite ${updates} saved device${updates===1?'':'s'}` : `Save ${count-updates} new & overwrite ${updates}`) : count ? `Save ${count} device${count===1?'':'s'}` : 'Save devices';
}
function overwriteNotice(device) {
  return device.overwrite_id ? `<div class="overwrite-notice"><strong>Will overwrite “${escape(device.original_label)}”</strong><p>Review the details, then save to update the original record.</p></div>` : '';
}
function renderDuplicates() {
  $('#duplicates-review').hidden=!state.duplicates.length;
  $('#exclude-all-duplicates').hidden=state.duplicates.length<2;
  $('#duplicate-list').innerHTML=state.duplicates.map(d=>{
    const scanned=[d.scan.brand,d.scan.product].filter(Boolean).join(' ');
    return `<article class="duplicate-card"><h3>This is a duplicate of “${escape(deviceLabel(d.original))}”.</h3><p class="pairing-code">${escape(display(d.original.manual_code))}</p>${scanned?`<p>Scanned details: ${escape(scanned)}</p>`:''}<div class="duplicate-actions"><button class="secondary" data-exclude="${escape(d.key)}">Exclude from this scan</button><button class="primary" data-overwrite="${escape(d.key)}">Overwrite original</button></div><p class="hint">Nothing changes until you save. The original name/location, notes, and QR are kept for review.</p></article>`;
  }).join('');
}
function renderPending() {
  const active = document.activeElement;
  const focus = $('#review-list').contains(active) && active.dataset.field ? {
    index:active.dataset.index,field:active.dataset.field,start:active.selectionStart,end:active.selectionEnd
  } : null;
  $('#code-count').textContent = state.pending.length ? `(${state.pending.length})` : '';
  $('#review-hint').hidden = state.pending.length + state.duplicates.length > 0;
  refreshSaveButton();renderDuplicates();
  $('#review-list').innerHTML = state.pending.map((d, i) => `<div class="review-item">${overwriteNotice(d)}<div class="code-row"><input ${d.overwrite_id ? 'readonly' : ''} aria-label="Pairing code ${i+1}" value="${escape(display(d.manual_code))}" data-field="manual_code" data-index="${i}" spellcheck="false"><button class="quiet" data-remove="${i}" aria-label="Exclude code ${i+1} from this scan">×</button></div>${appearanceControls(d,i)}<div class="fields"><label>Brand<input list="known-brands" data-field="brand" data-index="${i}" value="${escape(d.brand)}" placeholder="Use batch brand" maxlength="120"></label><label>Product<input list="known-products" data-field="product" data-index="${i}" value="${escape(d.product)}" placeholder="Use batch product" maxlength="160"></label></div>${d.identity_source ? `<p class="hint">${d.identity_source==='saved'?'Details reused from your saved devices.':'Name suggested from nearby label text.'} Edit anything below or above.</p>` : ''}<label class="item-name">Device name / location<input data-field="name" data-index="${i}" value="${escape(d.name)}" placeholder="e.g. Hallway lamp" maxlength="160"></label><p class="hint">${d.source === 'qr' ? 'QR decoded · original payload retained' : d.source === 'text' ? 'Read from text · check against the label' : 'Manually entered · checked when saved'}</p></div>`).join('');
  $('#capture-count').textContent = [state.pending.length?`${state.pending.length} to save`:'',state.duplicates.length?`${state.duplicates.length} duplicate${state.duplicates.length===1?'':'s'}`:''].filter(Boolean).join(' · ');
  $('#capture-count').hidden = !state.pending.length && !state.duplicates.length;
  if (focus) {
    const input = $(`#review-list [data-index="${focus.index}"][data-field="${focus.field}"]`);
    input?.focus();
    if (input && focus.start != null) input.setSelectionRange(focus.start,focus.end);
  }
}
function collect(codes) {
  const result=collectScan(state,codes,{brand:$('#brand').value,product:$('#product').value});
  if(result.changed)renderPending();return result;
}

let captureTimer;
function clearCaptureFeedback() {
  clearTimeout(captureTimer); $('.camera-wrap').classList.remove('capture-flash');
  $('#capture-feedback').hidden = true;
}
function flashCapture(count) {
  if (!count || state.mode !== 'camera') return;
  clearCaptureFeedback();
  $('#capture-feedback').textContent = `${count} new code${count===1?'':'s'} captured`;
  $('#capture-feedback').hidden = false;
  void $('.camera-wrap').offsetWidth;
  $('.camera-wrap').classList.add('capture-flash');
  captureTimer = setTimeout(clearCaptureFeedback,1400);
}
function updateKnownNames() {
  for (const field of ['brand','product']) {
    const values = [...new Set(state.devices.map(d => d[field]).filter(Boolean))].sort();
    $(`#known-${field==='brand'?'brands':'products'}`).innerHTML = values.map(value => `<option value="${escape(value)}"></option>`).join('');
  }
}
function applyIdentity(result) {
  const identity = result.identity || {};
  for (const field of ['brand','product']) {
    if (identity[field] && !$(`#${field}`).value && !state.batchEdited.has(field)) $(`#${field}`).value = identity[field];
  }
  const brands = identity.brands || [], products = identity.products || [];
  if (brands.length || products.length) {
    $('#identity-suggestions').hidden = false;
    $('#identity-hint').textContent = products.length > 1 ? 'Different names found. Matched names are filled per label below; tap a suggestion to fill remaining blanks.' : 'Label details filled where recognised. Tap a suggestion to fill remaining blanks, or edit any field.';
    $('#brand-suggestions').innerHTML = brands.map(value => `<button class="suggestion" data-identity-field="brand" data-identity-value="${escape(value)}">Brand: ${escape(value)}</button>`).join('');
    $('#product-suggestions').innerHTML = products.map(value => `<button class="suggestion" data-identity-field="product" data-identity-value="${escape(value)}">${escape(value)}</button>`).join('');
  }
  if (!brands.length && !products.length && result.codes?.length) {
    $('#brand-suggestions').replaceChildren();$('#product-suggestions').replaceChildren();
    $('#identity-hint').textContent=state.mode==='camera' ? 'Code captured. Keep the whole leaflet, including the product heading and brand, in view. Tap Capture text & codes to try again.' : 'Code captured. No readable name or brand found. Try a sharper photo of the whole leaflet, or enter the details below.';
    $('#identity-suggestions').hidden=false;
  }
  if (result.text) {$('#text-review').hidden=false;$('#ocr-text').textContent=result.text;}
}
async function readLabel(blob,withText) {
  const form = new FormData(); form.append('image',blob,'label.jpg'); form.append('text',String(withText));
  return api('/api/scan',{method:'POST',body:form});
}
async function scan(blob, withText = true) {
  if (state.scanning) return;
  state.scanning = true; const generation = state.generation;
  $('#photo').disabled = true; $('#capture').disabled = true;
  status(withText ? 'Reading QR codes and label text…' : 'Looking for Matter QR codes…');
  try {
    let result = await readLabel(blob,withText);
    if (generation !== state.generation) return;
    let {added,duplicates,foundDuplicates,excluded} = collect(result.codes);
    flashCapture(added);
    if (!withText && (added || foundDuplicates)) {
      status(`${added ? `Captured ${added} new code${added===1?'':'s'}.` : duplicateStatus()} Reading label details…`);
      try {
        // Let autofocus settle after first QR detection; use a fresh frame for
        // text instead of the initial (often moving) QR capture.
        if(state.stream)await new Promise(resolve=>setTimeout(resolve,650));
        if(generation !== state.generation)return;
        const labelFrame=state.stream ? await frame() : null;
        result = await readLabel(labelFrame || blob,true);
        if (generation !== state.generation) return;
        const extra = collect(result.codes);
        if (extra.added) flashCapture(extra.added);
        added += extra.added;
        foundDuplicates += extra.foundDuplicates;
      } catch(error) {
        status(`Codes captured. Name recognition failed: ${error.message} Enter details below.`,true);
        return;
      }
    }
    applyIdentity(result);
    const message = state.duplicates.length ? `${added?`${added} new code${added===1?'':'s'} added. `:''}${duplicateStatus()}` : (added || foundDuplicates) && !state.pending.length ? 'These codes are excluded from this scan.' : added ? `Added ${added} code${added === 1 ? '' : 's'} to review. Recognised details are filled below.` : foundDuplicates ? 'Duplicate choice recorded. Review the details before saving.' : duplicates ? 'These codes are already in this scan.' : excluded ? 'These codes are excluded from this scan.' : withText ? 'No valid Matter codes found. Try a closer, sharper photo or enter the printed code.' : 'Looking for Matter QR codes…';
    status([message,result.ignored ? 'Non-Matter or unreadable QR payloads skipped.' : '',result.notice].filter(Boolean).join(' '));
  } catch(error) { if (generation === state.generation) { status(error.message,true); if (!withText) stopCamera(); } }
  finally { state.scanning = false; $('#photo').disabled = false; $('#capture').disabled = false; refreshSaveButton(); }
}
function stopCamera() {
  clearTimeout(state.loop); state.loop = null;
  state.stream?.getTracks().forEach(track => track.stop()); state.stream = null;
  $('#video').srcObject = null; $('#start-camera').hidden = false; $('#camera-controls').hidden = true;
}
async function frame() {
  const video = $('#video');
  if (!video.videoWidth) return null;
  const canvas = document.createElement('canvas');
  const factor = Math.min(1, 2400/video.videoWidth);
  canvas.width = video.videoWidth*factor; canvas.height = video.videoHeight*factor;
  canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
  return new Promise(resolve => canvas.toBlob(resolve,'image/jpeg',.93));
}
async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) { status('Live camera needs HTTPS or localhost. Use Photo to take or upload a picture, or enter a code manually.',true); return; }
  const generation = state.generation;
  $('#start-camera').disabled = true;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:2560},height:{ideal:1920}},audio:false});
    if (generation !== state.generation || state.mode !== 'camera' || $('#add-view').hidden) {stream.getTracks().forEach(t => t.stop()); return;}
    state.stream = stream; $('#video').srcObject = stream; await $('#video').play();
    $('#start-camera').hidden = true; $('#camera-controls').hidden = false;
    const tick = async () => {
      if (!state.stream) return;
      if (!state.scanning) {const blob = await frame(); if (blob) await scan(blob,false);}
      if (state.stream) state.loop = setTimeout(tick,1300);
    };
    tick();
  } catch(error) { stopCamera(); status('Could not open the camera. Allow camera access, or use Photo or Manual.',true); }
  finally { $('#start-camera').disabled = false; }
}
async function manualCode() {
  const value = $('#manual-code').value.trim();
  if (!value) {status('Enter a pairing code first.',true);return;}
  // Validate with the same server parser used for storage, without creating a record.
  try {
    const code = await api('/api/validate',jsonOptions('POST',{code:value}));
    const result = collect([{...code,source:'manual'}]);
    status(state.duplicates.length ? duplicateStatus() : result.added ? 'Code added to review.' : result.excluded ? 'That code is excluded from this scan.' : 'That code is already in this scan.');
    if (result.added || result.foundDuplicates) $('#manual-code').value = '';
  } catch(error) {status(error.message,true);}
}
async function save() {
  if(state.duplicates.length){status('Choose Exclude or Overwrite for each saved duplicate.');return;}
  if (!state.pending.length || state.saving || state.scanning) { if (state.scanning) status('Wait for the scan to finish before saving.'); return; }
  stopCamera(); state.saving = true; renderPending();
  try {
    const devices = state.pending.map(d => ({manual_code:d.manual_code,qr_payload:d.qr_payload || '',name:d.name || '',notes:d.notes || '',color:d.color || '',icon:d.icon || '',
      ...(d.overwrite_id ? {overwrite_id:d.overwrite_id,expected_revision:d.expected_revision} : {}),
      brand:d.brandEdited ? d.brand.trim() : d.brand.trim() || $('#brand').value.trim(),
      product:d.productEdited ? d.product.trim() : d.product.trim() || $('#product').value.trim()}));
    const result=await api('/api/devices',jsonOptions('POST',{devices}));
    const count = devices.length; state.pending = []; showLibrary(); await loadDevices();
    toast(result.updated ? `${result.created?`Saved ${result.created} new; updated`:'Updated'} ${result.updated} device${result.updated===1?'':'s'}.` : `Saved ${count} device${count===1?'':'s'}`);
  } catch(error) {
    if(error.status===409){await loadDevices();if(error.conflicts)reconcileSaveConflicts(state,error.conflicts);}
    status(error.message,true);
  }
  finally {state.saving = false; renderPending();}
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast('Pairing code copied'); }
  catch { prompt('Copy this pairing code:',text); }
}
function editDevice(id) {
  if(state.edit?.id===id)return;
  if(state.edit && !canLeaveEdit())return;
  const device=state.devices.find(d=>d.id===id);if(!device)return;
  state.selectedId=id;state.detailOpen=true;state.qrVisible=false;
  state.edit={...device};state.editDirty=false;renderLibrary();
  for(const field of ['brand','product','name','notes'])$('#edit-form').elements[field].value=device[field];
  $('#edit-code').textContent=display(device.manual_code);$('#edit-error').textContent='';
  $('#edit-appearance').innerHTML=appearanceControls(state.edit,'edit');
  $('#device-detail-panel').scrollTop=0;
  $('#edit-form').elements.name.focus({preventScroll:true});
}
document.addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  if (b.dataset.add) showAdd(b.dataset.add);
  if (b.dataset.mode) setMode(b.dataset.mode);
  if (b.dataset.remove !== undefined) {
    const entry=state.pending[Number(b.dataset.remove)];excludeScanCode(state,codeKey(entry.manual_code));renderPending();
    status(entry.overwrite_id ? 'Excluded from this scan. The saved device is unchanged.' : 'Code excluded from this scan.');
  }
  if (b.dataset.exclude) {excludeScanCode(state,b.dataset.exclude);renderPending();status('Excluded from this scan. The saved device is unchanged.');}
  if (b.dataset.overwrite) {chooseOverwrite(state,b.dataset.overwrite);renderPending();status('Review the details, then save to overwrite the original.');}
  if (b.dataset.copy) copy(state.devices.find(d => d.id === Number(b.dataset.copy)).manual_code);
  if (b.dataset.edit) editDevice(Number(b.dataset.edit));
  if (b.dataset.selectDevice) selectDevice(Number(b.dataset.selectDevice));
  if (b.dataset.toggleQr) {state.qrVisible=!state.qrVisible;renderLibrary();$('#device-details-content [data-toggle-qr]')?.focus({preventScroll:true});}
  if (b.dataset.identityField) {
    const field = b.dataset.identityField, value = b.dataset.identityValue;
    $(`#${field}`).value = value; state.batchEdited.add(field);
    for (const device of state.pending) if (!device[field] && !device[`${field}Edited`]) {device[field]=value;device[`${field}Edited`]=true;}
    renderPending();
  }
  if (b.dataset.clearColour !== undefined) updateAppearance(b.dataset.clearColour,'color','');
});
function updateAppearance(index,field,value) {
  const device = index === 'edit' ? state.edit : state.pending[Number(index)];
  device[field] = value; device[`${field}Edited`] = true;
  if(index==='edit')state.editDirty=true;
  const controls = document.querySelector(`[data-appearance="${index}"]`);
  controls.querySelector('.colour-name').textContent = colourName(device.color);
  controls.querySelector('.marker-preview').innerHTML = colourDot(device.color)+(icons[device.icon] || icons.device);
}
document.addEventListener('input',e => {
  if (e.target.dataset.colourPicker !== undefined) updateAppearance(e.target.dataset.colourPicker,'color',e.target.value);
});
document.addEventListener('change',e => {
  if (e.target.dataset.iconPicker !== undefined) updateAppearance(e.target.dataset.iconPicker,'icon',e.target.value);
});
$('#review-list').addEventListener('input',e => { const {index,field} = e.target.dataset; if (index === undefined) return; state.pending[index][field] = e.target.value; state.pending[index][`${field}Edited`] = true; if (field === 'manual_code') {state.pending[index].qr_payload = ''; state.pending[index].source = 'manual';} });
for (const field of ['brand','product']) $(`#${field}`).addEventListener('input',() => {
  state.batchEdited.add(field);
  for (const device of state.pending) if (!device[`${field}Edited`]) device[field] = $(`#${field}`).value;
  renderPending();
});
$('#review-list').addEventListener('focusin',() => {if (state.stream) stopCamera();});
$('#photo').addEventListener('change',async e => {
  const file = e.target.files[0]; if (!file) return;
  if (file.size > 16*1024*1024) {status('Choose an image smaller than 16 MB.',true);return;}
  const preview = $('#preview'); const url = URL.createObjectURL(file); preview.onload = () => URL.revokeObjectURL(url); preview.src = url; preview.hidden = false;
  await scan(file); e.target.value = '';
});
$('#search').addEventListener('input',renderLibrary);
$('#nav-devices').onclick = showLibrary; $('#nav-add').onclick = () => showAdd(); $('#cancel').onclick = showLibrary;
$('#manual-extra').onclick = () => setMode('manual'); $('#add-code').onclick = manualCode;
$('#exclude-all-duplicates').onclick = () => {for(const d of [...state.duplicates])excludeScanCode(state,d.key);renderPending();status('Saved duplicates excluded from this scan. Originals are unchanged.');};
$('#manual-code').addEventListener('keydown',e => {if (e.key === 'Enter') manualCode();});
$('#save').onclick = save; $('#start-camera').onclick = startCamera; $('#stop-camera').onclick = stopCamera;
$('#capture').onclick = async () => {if (state.scanning) return; const blob = await frame(); if (blob) {stopCamera(); await scan(blob,true);}};
$('#export').onclick = async () => {try{await exportBackup();}catch(error){toast(error.message);}};
$('#open-backups').onclick=()=>{
  if(state.edit && !canLeaveEdit())return;
  renderLibrary();const panel=$('#backup-tools');panel.hidden=!panel.hidden;
  $('#open-backups').setAttribute('aria-expanded',String(!panel.hidden));
};
document.addEventListener('inventory-imported',loadDevices);
$('#close-edit').onclick=cancelEdit;
$('#edit-form').addEventListener('input',()=>{state.editDirty=true;});
$('#edit-form').addEventListener('change',()=>{state.editDirty=true;});
function setEditBusy(busy) {
  state.editSaving=busy;
  for(const button of $('#edit-form').querySelectorAll('button'))button.disabled=busy;
}
$('#edit-form').onsubmit=async e=>{
  e.preventDefault();if(!state.edit || state.editSaving)return;
  const id=state.edit.id,body={...state.edit,...Object.fromEntries(new FormData(e.target))};
  setEditBusy(true);
  try {
    await api(`/api/devices/${id}`,jsonOptions('PUT',body));
    state.edit=null;state.editDirty=false;renderLibrary();await loadDevices();
    $('#device-details-content [data-edit]')?.focus({preventScroll:true});toast('Device updated');
  } catch(error) {$('#edit-error').textContent=error.message;}
  finally {setEditBusy(false);}
};
$('#delete-device').onclick=async()=>{
  if(!state.edit || state.editSaving || !confirm('Delete this device and its saved pairing code?'))return;
  const id=state.edit.id;setEditBusy(true);
  try {
    await api(`/api/devices/${id}`,{method:'DELETE'});
    state.edit=null;state.editDirty=false;state.selectedId=null;state.detailOpen=false;state.qrVisible=false;
    renderLibrary();await loadDevices();toast('Device deleted');
  } catch(error) {$('#edit-error').textContent=error.message;}
  finally {setEditBusy(false);}
};
$('#device-list').addEventListener('keydown',e=>{
  const button=e.target.closest('[data-select-device]');
  if(!button || !inventoryDesktop.matches || !['ArrowUp','ArrowDown','Home','End'].includes(e.key))return;
  e.preventDefault();const matches=matchingDevices(),index=matches.findIndex(d=>d.id===Number(button.dataset.selectDevice));
  const next=e.key==='Home'?0:e.key==='End'?matches.length-1:Math.max(0,Math.min(matches.length-1,index+(e.key==='ArrowDown'?1:-1)));
  if(matches[next])selectDevice(matches[next].id,true);
});
document.addEventListener('error',e=>{
  if(e.target.matches?.('img[data-pairing-qr]')) {
    const message=e.target.closest('.qr-reveal')?.querySelector('.qr-status');
    if(message)message.textContent='Could not load the QR code. Hide it and try again, or refresh the page.';
  }
},true);
document.addEventListener('visibilitychange',() => {if (document.hidden) stopCamera();});
window.addEventListener('pagehide',stopCamera);
window.addEventListener('beforeunload',e => {if (state.pending.length || state.duplicates.length || state.editDirty) {e.preventDefault();e.returnValue='';}});
loadDevices();
