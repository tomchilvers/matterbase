class MatterbasePanel extends HTMLElement {
  set hass(value){this._hass=value;this._port?.postMessage({type:"theme",dark:!!value.themes?.darkMode});}
  set panel(value){this._panel=value;this.render();}
  connectedCallback(){this.render();}
  disconnectedCallback(){this._port?.close();window.removeEventListener('message',this._onMessage);this._key=null;}
  render(){
    if(!this.isConnected || !this._panel?.config)return;
    const config=this._panel.config;
    const key=JSON.stringify(config);
    if(this._key===key)return;
    this._key=key;this._port?.close();window.removeEventListener('message',this._onMessage);
    const root=this.shadowRoot || this.attachShadow({mode:'open'});
    const style=document.createElement('style');
    style.textContent=':host{display:flex;flex-direction:column;height:100vh;height:100dvh;background:var(--primary-background-color);color:var(--primary-text-color)}header{display:flex;align-items:center;gap:12px;padding:6px 16px;min-height:48px;font:14px system-ui}header p{margin:0;flex:1}a{color:var(--primary-color);white-space:nowrap}iframe{border:0;flex:1;width:100%;min-height:0}button{font:inherit;background:none;border:0;color:inherit;min-width:44px;min-height:44px;cursor:pointer}';
    const header=document.createElement('header');const menu=document.createElement('button');
    menu.textContent='☰';menu.setAttribute('aria-label','Open Home Assistant menu');
    menu.onclick=()=>this.dispatchEvent(new CustomEvent('hass-toggle-menu',{bubbles:true,composed:true}));
    const title=document.createElement('p');title.textContent=config.native?'Matterbase · native inventory':'Matterbase · external inventory';header.append(menu,title);
    const frame=document.createElement('iframe');frame.title='Matterbase inventory';frame.allow='camera; clipboard-write; fullscreen';
    frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms allow-modals allow-downloads allow-popups allow-popups-to-escape-sandbox');
    if(config.native){
      this._onMessage=event=>{
        if(event.origin!==location.origin || event.source!==frame.contentWindow || event.data?.type!=='matterbase-native-ready')return;
        this._port?.close();const channel=new MessageChannel();this._port=channel.port1;
        channel.port1.onmessage=async({data})=>{
          if(!Number.isSafeInteger(data?.id))return;
          try{
            const result=await this._hass.callApi('POST','matterbase/inventory',{method:data.method,path:data.path,body:data.body || {}});
            channel.port1.postMessage({id:data.id,result});
          }catch(error){channel.port1.postMessage({id:data.id,result:{status:error?.status_code || 503,body:{error:'Could not access the native inventory. Check your Home Assistant session and try again.'}}});}
        };
        frame.contentWindow.postMessage({type:'matterbase-native-connect',pairing_help:!!config.pairing_help,dark:!!this._hass?.themes?.darkMode},location.origin,[channel.port2]);
      };
      window.addEventListener('message',this._onMessage);
      frame.src='/matterbase-native/index.html';
    }else{
      const url=new URL(config.url);
      if(!['http:','https:'].includes(url.protocol) || url.username || url.password)return;
      const link=document.createElement('a');link.textContent='Open directly';link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';header.append(link);frame.src=url.href;
    }
    root.replaceChildren(style,header,frame);
  }
}
if(!customElements.get('matterbase-panel'))customElements.define('matterbase-panel',MatterbasePanel);
