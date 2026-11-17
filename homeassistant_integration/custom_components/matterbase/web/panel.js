class MatterbasePanel extends HTMLElement {
  set hass(value) { this._hass=value; }
  set panel(value) { this._panel=value; this.render(); }
  connectedCallback() {this.render();}
  render() {
    if(!this.isConnected || !this._panel?.config?.url)return;
    const url=this._panel.config.url;
    if(this._url===url)return;
    const parsed=new URL(url);
    if(!['http:','https:'].includes(parsed.protocol) || parsed.username || parsed.password)return;
    this._url=url;
    const root=this.shadowRoot || this.attachShadow({mode:'open'});
    const style=document.createElement('style');
    style.textContent=':host{display:flex;flex-direction:column;height:100vh;height:100dvh;background:var(--primary-background-color);color:var(--primary-text-color)}header{display:flex;align-items:center;gap:16px;padding:10px 16px;min-height:44px;font:14px system-ui}header p{margin:0;flex:1}a{color:var(--primary-color);white-space:nowrap}iframe{border:0;flex:1;width:100%;min-height:0}button{font:inherit;background:none;border:0;color:inherit;min-width:44px;min-height:44px;cursor:pointer}';
    const header=document.createElement('header');
    const menu=document.createElement('button');menu.textContent='☰';menu.setAttribute('aria-label','Open Home Assistant menu');menu.onclick=()=>this.dispatchEvent(new CustomEvent('hass-toggle-menu',{bubbles:true,composed:true}));
    const text=document.createElement('p');text.textContent='Matterbase · separate inventory';
    const link=document.createElement('a');link.textContent='Open directly';link.href=url+'/';link.target='_blank';link.rel='noopener noreferrer';
    header.append(menu,text,link);
    const frame=document.createElement('iframe');frame.title='Matterbase inventory';frame.src=url+'/';frame.allow='camera; clipboard-write; fullscreen';
    frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms allow-modals allow-downloads allow-popups allow-popups-to-escape-sandbox');
    root.replaceChildren(style,header,frame);
  }
}
if(!customElements.get('matterbase-panel'))customElements.define('matterbase-panel',MatterbasePanel);
