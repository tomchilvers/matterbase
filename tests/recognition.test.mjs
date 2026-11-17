import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeRecognition,useKnownProduct} from '../static/recognition.mjs';
import {collectScan,chooseOverwrite,excludeScanCode,overwriteEntry,reconcileSaveConflicts} from '../static/duplicates.mjs';

test('recognition preserves typed names and deliberate blanks', () => {
  const device={brand:'My brand',product:'',productEdited:true,color:'',colorEdited:true};
  mergeRecognition(device,{brand:'IKEA',product:'KAJPLATS',color:'#ffffff',icon:'bulb'});
  assert.equal(device.brand,'My brand');
  assert.equal(device.product,'');
  assert.equal(device.color,'');
  assert.equal(device.icon,'bulb');
});

test('a repeated scan enriches empty details without replacing existing matches', () => {
  const device={brand:'',product:'KAJPLATS KIT'};
  assert.equal(mergeRecognition(device,{brand:'IKEA',product:'KAJPLATS',identity_source:'label'}),true);
  assert.equal(device.brand,'IKEA');
  assert.equal(device.product,'KAJPLATS KIT');
  assert.equal(mergeRecognition(device,{brand:'IKEA',product:'KAJPLATS'}),false);
});

test('known names require the same vendor and product IDs', () => {
  const devices=[{vendor_id:4476,product_id:1,brand:'IKEA',product:'KAJPLATS'}];
  assert.equal(useKnownProduct({vendor_id:4476,product_id:1},devices).product,'KAJPLATS');
  assert.equal(useKnownProduct({vendor_id:4476,product_id:2},devices).product,undefined);
  assert.equal(useKnownProduct({vendor_id:null,product_id:null},devices).product,undefined);
  assert.equal(useKnownProduct({vendor_id:4476,product_id:1,product:'Name from label'},devices).product,'Name from label');
});

test('conflicting saved names are left for review', () => {
  const devices=[{vendor_id:4476,product_id:1,brand:'IKEA',product:'Bulb'},
    {vendor_id:4476,product_id:1,brand:'IKEA',product:'Lamp'}];
  const code=useKnownProduct({vendor_id:4476,product_id:1},devices);
  assert.equal(code.brand,'IKEA');
  assert.equal(code.product,undefined);
});

const original={id:7,revision:3,manual_code:'00054912336',qr_payload:'MT:EX7A00O6148-.548G00',name:'Hallway lamp',notes:'Keep me',brand:'IKEA',product:'Old name',color:'#6a9a8b',icon:'bulb'};
const scanState=()=>({devices:[{...original}],pending:[],duplicates:[],excludedCodes:new Set(),batchEdited:new Set()});

test('saved QR and formatted manual duplicates make one unresolved choice',()=>{
  const state=scanState();
  let result=collectScan(state,[{manual_code:'0005-491-2336',qr_payload:original.qr_payload}]);
  assert.equal(result.added,0);assert.equal(result.foundDuplicates,1);
  result=collectScan(state,[{manual_code:original.manual_code}]);
  assert.equal(result.foundDuplicates,0);assert.equal(state.duplicates.length,1);assert.equal(state.pending.length,0);
  assert.deepEqual(state.devices,[original]);
});

test('exclude is remembered through subsequent frames and delayed OCR',()=>{
  const state=scanState();
  collectScan(state,[{manual_code:original.manual_code}]);
  excludeScanCode(state,original.manual_code);
  const result=collectScan(state,[{manual_code:original.manual_code,product:'Recognised name'}]);
  assert.equal(result.excluded,1);assert.equal(state.duplicates.length,0);assert.equal(state.pending.length,0);
  assert.deepEqual(state.devices,[original]);
});

test('overwrite is a draft preserving identity, notes, and original QR',()=>{
  const state=scanState();
  collectScan(state,[{manual_code:original.manual_code,product:'KAJPLATS'}]);
  chooseOverwrite(state,original.manual_code);
  const draft=state.pending[0];
  assert.equal(draft.overwrite_id,7);assert.equal(draft.expected_revision,3);
  assert.equal(draft.product,'KAJPLATS');assert.equal(draft.name,original.name);
  assert.equal(draft.notes,original.notes);assert.equal(draft.qr_payload,original.qr_payload);
  assert.deepEqual(state.devices,[original]);assert.equal(state.duplicates.length,0);
});

test('OCR arriving after overwrite selection updates suggestions but keeps user edits',()=>{
  const state=scanState();
  collectScan(state,[{manual_code:original.manual_code}]);chooseOverwrite(state,original.manual_code);
  collectScan(state,[{manual_code:original.manual_code,product:'Recognised model'}]);
  assert.equal(state.pending[0].product,'Recognised model');
  state.pending[0].product='My model';state.pending[0].productEdited=true;
  collectScan(state,[{manual_code:original.manual_code,product:'Another OCR model'}]);
  assert.equal(state.pending[0].product,'My model');
});

test('removing an overwrite keeps the original unchanged and suppresses rediscovery',()=>{
  const state=scanState();
  collectScan(state,[{manual_code:original.manual_code}]);chooseOverwrite(state,original.manual_code);
  excludeScanCode(state,original.manual_code);collectScan(state,[{manual_code:original.manual_code}]);
  assert.equal(state.pending.length,0);assert.equal(state.duplicates.length,0);assert.deepEqual(state.devices,[original]);
});

test('new codes repeated in a scan are kept once, without a saved-duplicate prompt',()=>{
  const state=scanState();
  collectScan(state,[{manual_code:'14970212332'},{manual_code:'1497-021-2332'}]);
  assert.equal(state.pending.length,1);assert.equal(state.duplicates.length,0);
});

test('a save-time race requires a fresh explicit choice',()=>{
  const state=scanState();
  collectScan(state,[{manual_code:original.manual_code}]);chooseOverwrite(state,original.manual_code);
  const fresh={...original,revision:4,name:'Renamed lamp',notes:'New note'};
  reconcileSaveConflicts(state,[fresh]);
  assert.equal(state.pending.length,0);assert.equal(state.duplicates.length,1);
  chooseOverwrite(state,original.manual_code);
  assert.equal(state.pending[0].expected_revision,4);
  assert.equal(state.pending[0].name,'Renamed lamp');assert.equal(state.pending[0].notes,'New note');
});

test('explicit cleared overwrite fields remain blank',()=>{
  const draft=overwriteEntry({manual_code:original.manual_code,name:'',nameEdited:true,color:'',colorEdited:true},original);
  assert.equal(draft.name,'');assert.equal(draft.color,'');assert.equal(draft.notes,original.notes);
});
