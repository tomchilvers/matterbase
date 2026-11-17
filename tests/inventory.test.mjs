import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveInventorySelection,toggleInventorySelection,inventoryDetails,inventoryRow} from '../static/inventory.mjs';
const devices=[{id:1,name:'Hallway lamp',brand:'IKEA',product:'KAJPLATS',manual_code:'34970112332',qr_payload:'MT:Y.K9042C00KA0648G00',notes:'First line\nSecond line',created_at:'2026-11-10T12:00:00Z',updated_at:'2026-11-11T12:00:00Z',color:'#6a9a8b',icon:'bulb'},{id:2,manual_code:'14970212332'}];
const closed={selectedId:null,detailOpen:false,qrVisible:false};
const options={marker:'',colour:'Teal',icon:'Bulb',qrVisible:false};
test('desktop starts with a device, mobile starts collapsed',()=>{
 assert.deepEqual(resolveInventorySelection(devices,closed,true),{selectedId:1,detailOpen:true,qrVisible:false});
 assert.deepEqual(resolveInventorySelection(devices,closed,false),closed);
});
test('mobile switching and collapsing discard a revealed QR',()=>{
 const open={selectedId:1,detailOpen:true,qrVisible:true};
 assert.deepEqual(toggleInventorySelection(open,2,false),{selectedId:2,detailOpen:true,qrVisible:false});
 assert.deepEqual(toggleInventorySelection(open,1,false),{selectedId:1,detailOpen:false,qrVisible:false});
});
test('desktop clicking the selected row keeps details visible',()=>{
 assert.equal(toggleInventorySelection({selectedId:1,detailOpen:true},1,true).detailOpen,true);
});
test('filtering away the selected device resolves each layout safely',()=>{
 const current={selectedId:2,detailOpen:true,qrVisible:true};
 assert.deepEqual(resolveInventorySelection([devices[0]],current,true),{selectedId:1,detailOpen:true,qrVisible:false});
 assert.deepEqual(resolveInventorySelection([devices[0]],current,false),closed);
 assert.deepEqual(resolveInventorySelection([],current,true),closed);
});
test('refresh and resize retain the selected device',()=>{
 const current={selectedId:2,detailOpen:true,qrVisible:false};
 assert.deepEqual(resolveInventorySelection(devices,current,true),current);
 assert.deepEqual(resolveInventorySelection(devices,current,false),current);
});
test('read-only details show metadata and no QR request before reveal',()=>{
 const html=inventoryDetails(devices[0],options);
 for(const value of ['Date added','Last updated','First line\nSecond line','3497-011-2332','data-edit="1"','Show pairing QR'])assert.ok(html.includes(value),value);
 assert.doesNotMatch(html,/<input|<textarea|<img|src=|MT:Y/);
});
test('QR reveal includes an image only for QR-backed records',()=>{
 assert.match(inventoryDetails(devices[0],{...options,qrVisible:true}),/src="api\/devices\/1\/qr"/);
 assert.doesNotMatch(inventoryDetails(devices[1],{...options,qrVisible:true}),/<img|data-toggle-qr/);
});
test('user text stays escaped in details and row labels',()=>{
 const device={...devices[0],name:'<img src=x onerror=alert(1)>',notes:'<script>bad</script>',created_at:'invalid',updated_at:''};
 const detail=inventoryDetails(device,options),row=inventoryRow(device,{marker:'',selected:true,expanded:true,desktop:false});
 assert.doesNotMatch(detail,/<img|<script/);assert.doesNotMatch(row,/<img/);
 assert.match(detail,/&lt;script&gt;bad/);assert.match(detail,/Unknown/);
 assert.match(row,/aria-expanded="true"/);
});

test('Home Assistant pairing guidance is opt-in and never embeds a code in the link',()=>{
 assert.doesNotMatch(inventoryDetails(devices[0],options),/home-assistant-help/);
 const html=inventoryDetails(devices[0],{...options,homeAssistantHelp:true});
 assert.match(html,/Add to Home Assistant \(optional\)/);
 assert.match(html,/href="https:\/\/my.home-assistant.io\/redirect\/config_matter\/"/);
 assert.doesNotMatch(html,/config_matter[^" ]*[?]/);
 assert.match(html,/does not send this code or track pairing status/);
});
