// Standalone Docker transport. The native integration supplies a local adapter.
export const request=(url,options={})=>fetch(url.replace(/^\//,''),options);
export const pairingQrUrl=device=>`api/devices/${device.id}/qr`;
export const exportBackup=()=>window.location.assign('api/export');
