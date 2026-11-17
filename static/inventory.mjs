import {deviceLabel} from './duplicates.mjs';

export const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const formatPairingCode = code => code.length===11 ? `${code.slice(0,4)}-${code.slice(4,7)}-${code.slice(7)}` : code;

export function resolveInventorySelection(matches,current,desktop) {
  if (!matches.some(device=>device.id===current.selectedId)) {
    return {selectedId:desktop ? matches[0]?.id ?? null : null,detailOpen:desktop && matches.length>0,qrVisible:false};
  }
  return {selectedId:current.selectedId,detailOpen:desktop || current.detailOpen,qrVisible:current.qrVisible && (desktop || current.detailOpen)};
}

export function toggleInventorySelection(current,id,desktop) {
  const detailOpen=desktop || current.selectedId!==id || !current.detailOpen;
  return {selectedId:id,detailOpen,qrVisible:current.selectedId===id && detailOpen ? current.qrVisible : false};
}

function dateMarkup(value) {
  if (!value) return 'Unknown';
  const date=new Date(value);
  if (!Number.isFinite(date.getTime())) return 'Unknown';
  const text=new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'short'}).format(date);
  return `<time datetime="${date.toISOString()}" title="${escapeHtml(date.toLocaleString())}">${escapeHtml(text)}</time>`;
}

export function inventoryRow(device,{selected,expanded,desktop,marker}) {
  const title=deviceLabel(device);
  const identity=device.name ? [device.brand,device.product].filter(Boolean).join(' ') : '';
  const suffix=device.manual_code.slice(-4);
  return `<article class="device-row${selected && expanded?' is-selected':''}" id="device-row-${device.id}" role="listitem">
    <h2 class="device-row-heading"><button class="device-trigger" id="device-trigger-${device.id}" data-select-device="${device.id}"
      aria-expanded="${expanded}" aria-controls="device-detail-panel" aria-label="${desktop || !expanded?'View':'Hide'} details for ${escapeHtml(title)}"
      ${desktop?`tabindex="${selected?'0':'-1'}"`:''}>
      <span class="device-symbol" aria-hidden="true">${marker}</span>
      <span class="device-summary"><strong>${escapeHtml(title)}</strong><span>${identity?`${escapeHtml(identity)} · `:''}<span class="code-suffix">…${escapeHtml(suffix)}</span></span></span>
      <svg class="icon device-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>
    </button></h2>
  </article>`;
}

export function inventoryDetails(device,{marker,colour,icon,qrVisible,homeAssistantHelp=false}) {
  const title=deviceLabel(device), escape=escapeHtml;
  const property=(label,value,raw=false)=>`<div><dt>${label}</dt><dd>${raw?value:escape(value || 'Not set')}</dd></div>`;
  const qr=qrVisible && device.qr_payload ? `<div class="qr-reveal" id="device-qr-content">
    <img class="saved-qr" data-pairing-qr="${device.id}" src="api/devices/${device.id}/qr" alt="Matter pairing QR code for ${escape(title)}" width="240" height="240">
    <p class="hint qr-status" role="status"></p>
    <details class="qr-payload"><summary>Original QR payload</summary><pre>${escape(device.qr_payload)}</pre></details>
  </div>` : '';
  return `<div class="detail-title-row"><div class="detail-device-heading"><span class="device-symbol" aria-hidden="true">${marker}</span><h2 id="selected-device-title">${escape(title)}</h2></div><button class="secondary detail-edit" data-edit="${device.id}">Edit</button></div>
    <dl class="device-properties">
      ${property('Brand',device.brand)}${property('Product',device.product)}
      ${property('Name / location',device.name)}${property('Device icon',icon || 'No icon')}
      ${property('Colour label',device.color?colour:'Not set')}${property('Date added',dateMarkup(device.created_at),true)}
      ${device.updated_at && device.updated_at!==device.created_at?property('Last updated',dateMarkup(device.updated_at),true):''}
    </dl>
    <section class="device-notes" aria-labelledby="device-notes-title"><h3 id="device-notes-title">Notes</h3><p>${escape(device.notes || 'No notes yet.')}</p></section>
    <section class="device-pairing" aria-labelledby="device-pairing-title"><h3 id="device-pairing-title">Pairing code</h3>
      <div class="detail-code-row"><code class="pairing-code">${escape(formatPairingCode(device.manual_code))}</code><button class="secondary" data-copy="${device.id}" aria-label="Copy pairing code for ${escape(title)}">Copy</button></div>
      ${device.qr_payload?`<button class="quiet qr-toggle" data-toggle-qr="${device.id}" aria-expanded="${qrVisible}" ${qrVisible?'aria-controls="device-qr-content"':''}>${qrVisible?'Hide':'Show'} pairing QR</button>${qr}`:'<p class="hint">No QR code saved. Use the pairing code above.</p>'}
    </section>${homeAssistantHelp?`<details class="home-assistant-help"><summary>Add to Home Assistant (optional)</summary><p>This entry stays in your Matterbase inventory. Pairing is a separate step in the Home Assistant Companion app.</p><ol><li>Put the physical device in pairing mode.</li><li>Use Copy above to copy its pairing code.</li><li>Open Home Assistant’s Matter setup on your phone, choose Add device, and use the manual-code option.</li></ol><p>If it already belongs to another Matter controller, enable sharing there and use its new pairing code.</p><a class="secondary" href="https://my.home-assistant.io/redirect/config_matter/" target="_blank" rel="noopener noreferrer">Open Home Assistant Matter setup</a><p class="hint">Matterbase does not send this code or track pairing status.</p></details>`:''}<button class="quiet collapse-details" data-select-device="${device.id}">Collapse details</button>`;
}
