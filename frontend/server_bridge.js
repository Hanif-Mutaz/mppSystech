(()=>{'use strict';
/* MPP server bridge. Server = sumber kebenaran; localStorage = cache.
   - Boot (storage_boot.js) sudah menarik data server sebelum aplikasi jalan.
   - Desktop: kirim HANYA key yang berubah (PATCH delta). Perangkat lain tidak saling menimpa.
   - Desktop & TV: cek versi server berkala; bila berubah oleh pihak lain -> reload (boot menarik data terbaru).
   - TV read-only. */
const IS_TV=location.pathname.toLowerCase().startsWith('/tv');
const SOURCE=IS_TV?'tv':'desktop';
const synced=window.__mppSynced||(k=>String(k).toLowerCase().startsWith('mpp')&&k!=='mpp220tvMode');
const base=window.__mppBase||{};                       /* snapshot terakhir yang diketahui sama dengan server */
let lastVersion=Number(window.__mppBootVersion||0),bootOK=!!window.__mppBootOK;
let pushing=false,again=false,dirty=false,loadedAt=Date.now(),reloading=false;

function current(){const x={};for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(synced(k))x[k]=localStorage.getItem(k)}return x}
function diff(){const cur=current(),changes={},removed=[];
  for(const k in cur)if(base[k]!==cur[k])changes[k]=cur[k];
  for(const k in base)if(!(k in cur))removed.push(k);
  return{changes,removed,cur}}
function typing(){const a=document.activeElement;return a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)&&a.type!=='button'&&a.type!=='checkbox'}
function reload(){if(reloading)return;reloading=true;location.reload()}

async function push(){
  if(IS_TV||!bootOK)return;                              /* bootOK=false: server belum terbaca, jangan kirim apa pun */
  if(pushing){again=true;return}
  const d=diff();if(!Object.keys(d.changes).length&&!d.removed.length)return;
  pushing=true;
  try{
    const r=await fetch('/api/state',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({changes:d.changes,removed:d.removed,source:SOURCE})});
    const j=await r.json();
    if(j.ok){
      Object.assign(base,d.changes);d.removed.forEach(k=>delete base[k]);
      if(j.previous_version!==lastVersion)dirty=true;      /* ada pihak lain yang menulis di sela-sela -> tarik ulang */
      lastVersion=j.version;
    }
  }catch(e){console.warn('MPP push',e)}
  finally{pushing=false;if(again){again=false;setTimeout(push,50)}}
}

async function check(){
  if(reloading||pushing)return;
  try{
    const r=await fetch('/api/state/version',{cache:'no-store'}),j=await r.json();
    if(!j||!j.ok)return;
    if(!bootOK){reload();return}                          /* boot gagal (server tadinya mati): coba lagi dari awal */
    if(j.version>lastVersion||dirty){
      if(IS_TV){if(Date.now()-loadedAt<5000)return;return reload()}
      const d=diff();
      if(Object.keys(d.changes).length||d.removed.length){await push();return}   /* kirim perubahan lokal dulu */
      if(typing())return;                                 /* jangan ganggu yang sedang mengetik */
      reload();
    }
  }catch(e){console.warn('MPP check',e)}
}

window.MPPServer={pull:check,push,postScan:async(code,type='QR',extra={})=>fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({employee_code:code,scan_type:type,source:type==='FINGERPRINT'?'fingerprint':'scanner',device_id:extra.device_id||'',payload:extra})})};

if(!IS_TV){
  const oldSet=Storage.prototype.setItem,oldRem=Storage.prototype.removeItem;
  const sched=function(k){if(this===localStorage&&synced(String(k))){clearTimeout(window.__mppPushTimer);window.__mppPushTimer=setTimeout(push,350)}};
  Storage.prototype.setItem=function(k){oldSet.apply(this,arguments);sched.call(this,k)};
  Storage.prototype.removeItem=function(k){oldRem.apply(this,arguments);sched.call(this,k)};
  addEventListener('DOMContentLoaded',()=>{setTimeout(push,800)});   /* seed server / kirim perubahan yang dibuat saat startup */
  setInterval(push,7000);
}
setInterval(check,IS_TV?2000:3000);
})();
