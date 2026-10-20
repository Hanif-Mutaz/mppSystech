(()=>{'use strict';if(location.pathname.toLowerCase().startsWith('/tv'))return;
let after=sessionStorage.getItem('mppLastScanEvent'),busy=false,queue=[],draining=false;
after=after===null?null:Number(after)||0;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function applyScan(e){
 const input=document.getElementById('barcode'); if(!input)return;
 input.value=e.employee_code; input.dispatchEvent(new Event('input',{bubbles:true})); input.focus();
 if(typeof window.scanIn==='function') window.scanIn();
}
/* Scan beruntun diproses satu per satu (scanIn punya debounce ~350 ms; tanpa antrean event ikut terbuang). */
async function drain(){if(draining)return;draining=true;try{while(queue.length){applyScan(queue.shift());await sleep(450)}}finally{draining=false}}
async function poll(){if(busy)return;busy=true;try{
 /* Tab baru: mulai dari event terbaru, JANGAN memutar ulang seluruh riwayat scan lama. */
 if(after===null){const r0=await fetch('/api/scans/latest',{cache:'no-store'}),j0=await r0.json();if(!j0.ok)return;after=Number(j0.id)||0;sessionStorage.setItem('mppLastScanEvent',after);return}
 const r=await fetch('/api/scans?after='+after+'&limit=50',{cache:'no-store'}),j=await r.json();
 if(j.ok){for(const e of j.events){after=Math.max(after,Number(e.id)||0);queue.push(e)}sessionStorage.setItem('mppLastScanEvent',after);drain()}
}catch(e){console.warn('Device poll',e)}finally{busy=false}}
// USB HID scanner: captures fast keyboard wedges even when barcode field is not focused.
let buf='',last=0;document.addEventListener('keydown',e=>{if(e.ctrlKey||e.altKey||e.metaKey)return;const now=Date.now();if(now-last>80)buf='';last=now;if(e.key==='Enter'){if(buf.length>=3){const code=buf;buf='';fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({employee_code:code,scan_type:'QR',source:'scanner',device_id:'USB-HID',payload:{transport:'keyboard'}})});}return}if(e.key.length===1)buf+=e.key;},true);
setInterval(poll,700);addEventListener('DOMContentLoaded',poll);
window.MPPDevices={status:()=>fetch('/api/devices/status').then(r=>r.json()),fingerprintTest:(employee_code)=>fetch('/api/fingerprint/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({employee_code,device_id:'TEST-FINGERPRINT'})})};
})();
