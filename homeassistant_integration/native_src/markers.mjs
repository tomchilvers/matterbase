// Conservative marker recognition beside each decoded QR. Unknown artwork stays blank.
function components(mask,width,height){
  const seen=new Uint8Array(mask.length),result=[];
  for(let start=0;start<mask.length;start++){
    if(!mask[start] || seen[start])continue;
    const queue=[start];seen[start]=1;let left=width,right=0,top=height,bottom=0;
    for(let at=0;at<queue.length;at++){
      const index=queue[at],x=index%width,y=Math.floor(index/width);
      left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
      for(const next of [x>0?index-1:-1,x<width-1?index+1:-1,y>0?index-width:-1,y<height-1?index+width:-1]){
        if(next>=0 && mask[next] && !seen[next]){seen[next]=1;queue.push(next);}
      }
    }
    result.push({left,right,top,bottom,w:right-left+1,h:bottom-top+1,pixels:queue});
  }
  return result;
}
function holes(component,mask,width){
  const w=component.w,h=component.h,white=new Uint8Array(w*h);
  for(let y=0;y<h;y++)for(let x=0;x<w;x++)white[y*w+x]=mask[(y+component.top)*width+x+component.left]?0:1;
  return components(white,w,h).filter(c=>c.left>0 && c.top>0 && c.right<w-1 && c.bottom<h-1 && c.pixels.length>=8).length;
}
export function analyzeMarkerPatch({data,width,height}){
  const channels=[[],[],[]];
  for(let i=0;i<data.length;i+=16){if(Math.min(data[i],data[i+1],data[i+2])>145)for(let c=0;c<3;c++)channels[c].push(data[i+c]);}
  const paper=channels.map(values=>{values.sort((a,b)=>a-b);return values[Math.floor(values.length*.9)] || 255;});
  const rgb=new Uint8ClampedArray(width*height*3),color=new Uint8Array(width*height),dark=new Uint8Array(width*height);
  for(let i=0;i<width*height;i++){
    const x=i%width;if(x>=185 && x<=295)continue;
    for(let c=0;c<3;c++)rgb[i*3+c]=Math.min(255,data[i*4+c]*255/paper[c]);
    const values=[rgb[i*3],rgb[i*3+1],rgb[i*3+2]],max=Math.max(...values),min=Math.min(...values),delta=max-min;
    color[i]=delta>18 && delta/Math.max(max,1)>.12 && max>70 && min<245?1:0;
    dark[i]=max<115?1:0;
  }
  const colors=components(color,width,height).filter(c=>c.w>=20 && c.w<=115 && c.h>=20 && c.h<=115 && c.w/c.h>.65 && c.w/c.h<1.5 && c.pixels.length/(c.w*c.h)>.55 && Math.abs((c.top+c.bottom)/2-80)<25);
  const icons=[];
  for(const c of components(dark,width,height)){
    if(c.w<15 || c.w>65 || c.h<25 || c.h>100 || Math.abs((c.top+c.bottom)/2-80)>40 || c.pixels.length/(c.w*c.h)>.6)continue;
    const count=holes(c,dark,width);
    if(count>=2 && c.h/c.w>1.45 && c.h>=40)icons.push({...c,icon:'switch'});
    if(count===1){
      let runs=0,inRun=false;
      for(let y=c.bottom+2;y<Math.min(height,c.bottom+20);y++){
        let hits=0,total=0;
        for(let x=Math.round(c.left+c.w*.25);x<=Math.round(c.right-c.w*.25);x++){hits+=dark[y*width+x];total++;}
        const marked=hits/Math.max(total,1)>.7;
        if(marked && !inRun)runs++;inRun=marked;
      }
      if(runs>=2)icons.push({...c,icon:'bulb'});
    }
  }
  const score=c=>Math.abs((c.left+c.right)/2-240)+3*Math.abs((c.top+c.bottom)/2-80);
  const choose=list=>{list.sort((a,b)=>score(a)-score(b));return list.length>1 && score(list[1])-score(list[0])<15?null:list[0];};
  const chosen=choose(colors),icon=choose(icons);let hex='';
  if(chosen){
    const centerX=(chosen.left+chosen.right)/2,centerY=(chosen.top+chosen.bottom)/2;
    const samples=chosen.pixels.filter(i=>Math.hypot(i%width-centerX,Math.floor(i/width)-centerY)<Math.min(chosen.w,chosen.h)*.25);
    hex='#'+[0,1,2].map(c=>{const values=samples.map(i=>rgb[i*3+c]).sort((a,b)=>a-b);return (values[Math.floor(values.length/2)] || 0).toString(16).padStart(2,'0');}).join('');
  }
  return {color:hex,icon:icon?.icon || ''};
}
export function detectMarkers(canvas,position){
  const a=position.topLeft,b=position.topRight,c=position.bottomLeft;
  if(!a || !b || !c)return {color:'',icon:''};
  const ux=b.x-a.x,uy=b.y-a.y,vx=c.x-a.x,vy=c.y-a.y,det=ux*vy-uy*vx;
  if(Math.abs(det)<16)return {color:'',icon:''};
  const patch=document.createElement('canvas');patch.width=520;patch.height=180;
  const context=patch.getContext('2d',{willReadFrequently:true});context.fillStyle='white';context.fillRect(0,0,520,180);
  const aa=80*vy/det,bb=-80*uy/det,cc=-80*vx/det,dd=80*ux/det;
  context.setTransform(aa,bb,cc,dd,200-aa*a.x-cc*a.y,40-bb*a.x-dd*a.y);context.drawImage(canvas,0,0);
  return analyzeMarkerPatch(context.getImageData(0,0,520,180));
}
