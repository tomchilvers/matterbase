import {mergeRecognition,useKnownProduct} from './recognition.mjs';

export const codeKey = value => String(value ?? '').replace(/[\s\-–—]/g,'');
export const deviceLabel = device => device.name || [device.brand,device.product].filter(Boolean).join(' ') || 'Unnamed device';

export function collectScan(state,codes,batch={}) {
  let added=0,duplicates=0,foundDuplicates=0,excluded=0,changed=false;
  for (const raw of codes) {
    const key=codeKey(raw.manual_code);
    if (state.excludedCodes.has(key)) {excluded++;continue;}
    const original=state.devices.find(d=>codeKey(d.manual_code)===key);
    const code={...(original ? raw : useKnownProduct(raw,state.devices))};
    for (const field of ['brand','product']) if (state.batchEdited.has(field)) code[field]=batch[field]?.trim() || '';
    const pending=state.pending.find(d=>codeKey(d.manual_code)===key);
    if (pending) {
      changed=mergeRecognition(pending,code)||changed;
      if(code.qr_payload && !pending.qr_from_scan){pending.qr_payload=code.qr_payload;pending.qr_from_scan=true;changed=true;}
      duplicates++;continue;
    }
    if (original) {
      const duplicate=state.duplicates.find(d=>d.key===key);
      if (duplicate) {
        changed=mergeRecognition(duplicate.scan,code)||changed;
        if(code.qr_payload && !duplicate.scan.qr_payload){duplicate.scan.qr_payload=code.qr_payload;changed=true;}
      }
      else {state.duplicates.push({key,original:{...original},scan:{...code}});foundDuplicates++;changed=true;}
      duplicates++;continue;
    }
    state.pending.push({color:'',icon:'',brand:'',product:'',...code,name:'',notes:''});
    added++;changed=true;
  }
  return {added,duplicates,foundDuplicates,excluded,changed};
}

export function overwriteEntry(scanned,original) {
  const qrFromScan=scanned.qr_from_scan ?? !!scanned.qr_payload;
  const entry={...scanned,manual_code:original.manual_code,
    qr_payload:(qrFromScan ? scanned.qr_payload : original.qr_payload) || '',qr_from_scan:qrFromScan,
    vendor_id:scanned.vendor_id ?? original.vendor_id, product_id:scanned.product_id ?? original.product_id,
    overwrite_id:original.id,expected_revision:original.revision,original_label:deviceLabel(original)};
  for (const field of ['brand','product','color','icon','name','notes']) {
    entry[field]=scanned[`${field}Edited`] ? scanned[field] : ['name','notes'].includes(field) ? original[field] || '' : scanned[field] || original[field] || '';
  }
  return entry;
}

export function chooseOverwrite(state,key) {
  const duplicate=state.duplicates.find(d=>d.key===key);
  if (!duplicate) return;
  state.pending.push(overwriteEntry(duplicate.scan,duplicate.original));
  state.duplicates=state.duplicates.filter(d=>d.key!==key);
}

export function excludeScanCode(state,key) {
  state.excludedCodes.add(key);
  state.duplicates=state.duplicates.filter(d=>d.key!==key);
  state.pending=state.pending.filter(d=>codeKey(d.manual_code)!==key);
}

export function reconcileSaveConflicts(state,conflicts) {
  for (const original of conflicts) {
    const key=codeKey(original.manual_code);
    const draft=state.pending.find(d=>codeKey(d.manual_code)===key);
    if (!draft) continue;
    state.pending=state.pending.filter(d=>codeKey(d.manual_code)!==key);
    state.duplicates=state.duplicates.filter(d=>d.key!==key);
    state.duplicates.push({key,original:{...original},scan:draft});
    state.excludedCodes.delete(key);
    const index=state.devices.findIndex(d=>d.id===original.id);
    if (index<0) state.devices.push({...original});else state.devices[index]={...original};
  }
}
