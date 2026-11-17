import {detectMarkers} from './markers.mjs';
let decoderPromise,workerPromise,worker;
const local=path=>new URL('../vendor/'+path,import.meta.url).href;
async function decoder(){
  return decoderPromise ||= import('../vendor/zxing/es/reader/index.js').then(module=>{
    module.prepareZXingModule({overrides:{locateFile:path=>local('zxing/reader/'+path)}});return module;
  });
}
async function ocrWorker(progress){
  return workerPromise ||= (async()=>{
    progress('Preparing local OCR. The first scan may take a moment…');
    await import('../vendor/tesseract/tesseract.min.js');
    worker=await Tesseract.createWorker('eng',1,{workerPath:local('tesseract/worker.min.js'),corePath:local('core'),langPath:local('lang'),workerBlobURL:false});
    await worker.setParameters({tessedit_pageseg_mode:'11'});return worker;
  })().catch(error=>{workerPromise=null;throw error;});
}
function linesFrom(data){
  return (data.blocks || []).flatMap(block=>(block.paragraphs || []).flatMap(paragraph=>(paragraph.lines || []).map(line=>({text:line.text.trim(),confidence:line.confidence || 0,x:line.bbox.x0,y:line.bbox.y0,w:line.bbox.x1-line.bbox.x0,h:line.bbox.y1-line.bbox.y0,words:(line.words || []).map(word=>({text:word.text,confidence:word.confidence || 0}))})))).filter(line=>line.text).slice(0,2000);
}
async function recognize(canvas,progress){
  const instance=await ocrWorker(progress);
  let timer;
  try{
    return await Promise.race([instance.recognize(canvas,{}, {blocks:true}),new Promise((_,reject)=>{timer=setTimeout(()=>{worker?.terminate();worker=null;workerPromise=null;reject(new Error('OCR timed out'));},45000);})]);
  }finally{clearTimeout(timer);}
}
export async function scan(blob,withText=true,progress=()=>{}){
  if(!(blob instanceof Blob) || blob.size>16*1024*1024)throw new Error('Choose an image smaller than 16 MB.');
  let image;
  try{image=await createImageBitmap(blob);}catch{throw new Error('Choose a supported JPG, PNG, or WebP image.');}
  if(image.width*image.height>30000000){image.close();throw new Error('Choose an image under 30 megapixels.');}
  const scale=Math.min(1,3200/Math.max(image.width,image.height)),canvas=document.createElement('canvas');
  canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);
  const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(image,0,0,canvas.width,canvas.height);image.close();
  const reader=await decoder(),barcodes=[],seen=new Set();
  const views=[{canvas,x:0,y:0}];
  if(withText)for(const y of [0,Math.floor(canvas.height/3)])for(const x of [0,Math.floor(canvas.width/3)]){
    const tile=document.createElement('canvas');tile.width=Math.floor(canvas.width*2/3);tile.height=Math.floor(canvas.height*2/3);tile.getContext('2d').drawImage(canvas,x,y,tile.width,tile.height,0,0,tile.width,tile.height);views.push({canvas:tile,x,y});
  }
  for(const view of views){
    const data=view.canvas.getContext('2d').getImageData(0,0,view.canvas.width,view.canvas.height);
    for(const barcode of await reader.readBarcodes(data,{formats:['QRCode'],tryHarder:true,maxNumberOfSymbols:200})){
      if(seen.has(barcode.text))continue;seen.add(barcode.text);
      const position=Object.fromEntries(Object.entries(barcode.position).map(([key,p])=>[key,{x:p.x+view.x,y:p.y+view.y}]));
      const points=Object.values(position),xs=points.map(p=>p.x),ys=points.map(p=>p.y);
      barcodes.push({text:barcode.text,bounds:[Math.min(...xs),Math.min(...ys),Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys)],...detectMarkers(canvas,position)});
    }
  }
  let lines=[],notice='';
  if(withText){
    try{
      progress('Reading names and printed codes locally…');
      const result=await recognize(canvas,progress);lines=linesFrom(result.data);
      // A second page-layout reading helps when sparse mode fragments a heading.
      if(!lines.some(line=>line.confidence>=65 && /[A-Za-z]{4}/.test(line.text))){
        const instance=await ocrWorker(progress);await instance.setParameters({tessedit_pageseg_mode:'3'});
        try{const retry=await recognize(canvas,progress);lines=linesFrom(retry.data);}finally{if(worker)await instance.setParameters({tessedit_pageseg_mode:'11'});}
      }
    }catch{notice='Local OCR could not finish. QR results are available; try a sharper photo or enter missing details manually.';}
  }
  return {barcodes,lines,width:canvas.width,height:canvas.height,notice};
}
window.addEventListener('pagehide',()=>{worker?.terminate();worker=null;workerPromise=null;});
