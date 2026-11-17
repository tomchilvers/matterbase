import test from 'node:test';
import assert from 'node:assert/strict';
import {analyzeMarkerPatch} from '../native_src/markers.mjs';
function patch(){const data=new Uint8ClampedArray(520*180*4);data.fill(255);return {width:520,height:180,data};}
function paint(p,x,y,rgb){const i=(y*p.width+x)*4;p.data.set([...rgb,255],i);}
test('blank label leaves uncertain markers empty',()=>assert.deepEqual(analyzeMarkerPatch(patch()),{color:'',icon:''}));
test('a filled coloured dot beside a QR yields its label colour',()=>{
 const p=patch();for(let y=45;y<115;y++)for(let x=75;x<145;x++)if(Math.hypot(x-110,y-80)<34)paint(p,x,y,[204,107,61]);
 assert.deepEqual(analyzeMarkerPatch(p),{color:'#cc6b3d',icon:''});
});
test('a narrow outlined switch with two enclosed button holes is recognized',()=>{
 const p=patch();for(let y=45;y<=115;y++)for(let x=100;x<=130;x++)if(x<104||x>126||y<49||y>111||y>=77&&y<=81)paint(p,x,y,[0,0,0]);
 assert.equal(analyzeMarkerPatch(p).icon,'switch');
});
