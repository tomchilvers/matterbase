import qrcode from '../vendor/qrcode/qrcode.mjs';
let port,sequence=0,readyResolve;
const pending=new Map();
const ready=new Promise(resolve=>{readyResolve=resolve;});
window.addEventListener('message',event=>{
  if(event.source!==parent || event.origin!==location.origin || event.data?.type!=='matterbase-native-connect' || !event.ports[0] || port)return;
  port=event.ports[0];document.body.dataset.homeAssistantHelp=String(!!event.data.pairing_help);
  port.onmessage=({data})=>{
    const request=pending.get(data?.id);if(!request)return;
    clearTimeout(request.timer);pending.delete(data.id);request.resolve(data.result);
  };
  readyResolve();
});
parent.postMessage({type:'matterbase-native-ready'},location.origin);

async function rpc(method,path,body={}){
  await Promise.race([ready,new Promise((_,reject)=>setTimeout(()=>reject(new Error('Open Matterbase from its Home Assistant sidebar and sign in as an administrator.')),12000))]);
  const id=++sequence;
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Home Assistant took too long to respond. Try again.'));},90000);
    pending.set(id,{resolve,timer});port.postMessage({id,method,path,body});
  });
}
export async function request(url,options={}){
  const path=url.replace(/^\//,'');
  let result;
  if(path==='api/scan'){
    const {scan}=await import('./native-scanner.mjs');
    const recognized=await scan(options.body.get('image'),options.body.get('text')!=='false',message=>{const status=document.getElementById('scan-status');if(status)status.textContent=message;});
    result=await rpc('POST','api/recognize',recognized);
  }else{
    result=await rpc(options.method || 'GET',path,options.body?JSON.parse(options.body):{});
  }
  return new Response(result.status===204?null:JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}});
}
export function pairingQrUrl(device){
  try{const qr=qrcode(0,'M');qr.addData(device.qr_payload);qr.make();return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(qr.createSvgTag({cellSize:4,margin:8,scalable:true}));}
  catch{return 'data:image/svg+xml,';}
}
export async function exportBackup(){
  const response=await request('api/export');const backup=await response.json();
  if(!response.ok)throw new Error(backup.error || 'Could not export inventory.');
  const url=URL.createObjectURL(new Blob([JSON.stringify(backup,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='matterbase-backup.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
}
