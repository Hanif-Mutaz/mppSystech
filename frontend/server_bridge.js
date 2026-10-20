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
let pushing=false,again=false,applying=false,loadedAt=Date.now(),reloading=false;

/* Buang field timestamp yang berubah tiap halaman dimuat (bukan perubahan data sungguhan),
   supaya tidak memicu push/reload bolak-balik antar perangkat. */
function norm(k,v){
  if(v==null)return v;
  if(k!=='mpp23db'&&k!=='mppV359PersistentState')return v;
  try{const o=JSON.parse(v);
    if(k==='mpp23db'&&o&&o.__mppV34Meta)delete o.__mppV34Meta.updatedAt;
    if(k==='mppV359PersistentState'&&o)delete o.savedAt;
    return JSON.stringify(o)}catch(e){return v}
}
const same=(k,a,b)=>a===b||norm(k,a)===norm(k,b);
function current(){const x={};for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(synced(k))x[k]=localStorage.getItem(k)}return x}
function diff(){const cur=current(),changes={},removed=[];
  for(const k in cur)if(!(k in base)||!same(k,base[k],cur[k]))changes[k]=cur[k];
  for(const k in base)if(!(k in cur))removed.push(k);
  return{changes,removed,cur}}
function typing(){const a=document.activeElement;return a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)&&a.type!=='button'&&a.type!=='checkbox'}

/* Terapkan data server ke memori aplikasi TANPA reload halaman (tidak ada layar boot / login ulang).
   Aplikasi membaca localStorage sekali ke variabel global (let), jadi variabelnya diisi ulang lalu dirender. */
const J=k=>{const v=localStorage.getItem(k);return v==null?undefined:JSON.parse(v)};
const BINDERS={
  mpp23db:()=>{const v=J('mpp23db');if(v&&typeof db!=='undefined')db=v},
  mpp23assign:()=>{const v=J('mpp23assign');if(v&&typeof assigns!=='undefined')assigns=v},
  mpp25attendance:()=>{const v=J('mpp25attendance');if(v&&typeof attendance!=='undefined')attendance=v},
  mpp25dailyplans:()=>{const v=J('mpp25dailyplans');if(v&&typeof dailyPlans!=='undefined')dailyPlans=v},
  mpp25lastscans:()=>{const v=J('mpp25lastscans');if(v&&typeof lastScans!=='undefined')lastScans=v},
  mpp26shifts:()=>{const v=J('mpp26shifts');if(v&&typeof shiftSettings!=='undefined'){shiftSettings=v;if(typeof migrate==='function')migrate()}},
  mpp28users:()=>{const v=J('mpp28users');if(v&&typeof appUsers!=='undefined')appUsers=v},
  mpp211idleSettings:()=>{const v=J('mpp211idleSettings');if(v&&typeof idleSettings!=='undefined')idleSettings=v},
  mpp230features:()=>{const v=J('mpp230features');if(v&&typeof scanFeatureSettings!=='undefined')scanFeatureSettings=v},
  mpp2405AutoOut:()=>{const v=J('mpp2405AutoOut');if(v&&typeof v2405AutoOutSettings!=='undefined')v2405AutoOutSettings=v},
  mpp241Approvals:()=>{const v=J('mpp241Approvals');if(v&&typeof v241Approvals!=='undefined')v241Approvals=v},
  mpp241Absences:()=>{const v=J('mpp241Absences');if(v&&typeof v241Absences!=='undefined')v241Absences=v},
  mppV355SharedLeaders:()=>{const v=J('mppV355SharedLeaders');if(v)window.v355SharedLeaders=v}
};
let softFails=0;
function applyRemote(p){
  const touched=[];applying=true;
  try{
    for(const k in p){
      if(!synced(k))continue;
      const v=String(p[k]);
      if(k in base&&same(k,base[k],v)){continue}
      localStorage.setItem(k,v);base[k]=v;touched.push(k)
    }
    for(const k in base)if(!(k in p)){localStorage.removeItem(k);delete base[k];touched.push(k)}
  }finally{applying=false}
  if(!touched.length)return true;
  try{
    touched.forEach(k=>{if(BINDERS[k])BINDERS[k]()});
    if(touched.some(k=>BINDERS[k])){
      if(typeof renderThreeShiftDashboard==='function')renderThreeShiftDashboard();
      if(!IS_TV&&typeof render==='function')render();
    }
    softFails=0;return true
  }catch(e){console.warn('MPP apply gagal',e);return false}
}
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
    if(j.version===lastVersion)return;
    /* version berubah: reload HANYA bila isi data benar-benar beda dari yang kita punya.
       (perubahan oleh diri sendiri / timestamp / nilai sama tidak boleh memicu reload -> mencegah loop) */
    const rs=await fetch('/api/state',{cache:'no-store'}),sj=await rs.json();
    if(!sj||!sj.ok)return;
    const p=sj.payload||{};let remoteChanged=false;
    for(const k in p)if(synced(k)&&!(k in base&&same(k,base[k],String(p[k])))){remoteChanged=true;break}
    if(!remoteChanged)for(const k in base)if(!(k in p)){remoteChanged=true;break}
    if(!remoteChanged){lastVersion=sj.version;return}
    if(IS_TV){if(applyRemote(p)){lastVersion=sj.version;return}if(++softFails<3||Date.now()-loadedAt<10000)return;return reload()}
    const d=diff();
    if(Object.keys(d.changes).length||d.removed.length){await push();return}   /* kirim perubahan lokal dulu */
    if(typing())return;                                   /* jangan ganggu yang sedang mengetik */
    if(applyRemote(p)){lastVersion=sj.version;return}
    if(++softFails>=3)reload();
  }catch(e){console.warn('MPP check',e)}
}

window.MPPServer={pull:check,push,postScan:async(code,type='QR',extra={})=>fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({employee_code:code,scan_type:type,source:type==='FINGERPRINT'?'fingerprint':'scanner',device_id:extra.device_id||'',payload:extra})})};

if(!IS_TV){
  const oldSet=Storage.prototype.setItem,oldRem=Storage.prototype.removeItem;
  const sched=function(k){if(this===localStorage&&!applying&&synced(String(k))){clearTimeout(window.__mppPushTimer);window.__mppPushTimer=setTimeout(push,350)}};
  Storage.prototype.setItem=function(k){oldSet.apply(this,arguments);sched.call(this,k)};
  Storage.prototype.removeItem=function(k){oldRem.apply(this,arguments);sched.call(this,k)};
  addEventListener('DOMContentLoaded',()=>{setTimeout(push,800)});   /* seed server / kirim perubahan yang dibuat saat startup */
  setInterval(push,7000);
}
setInterval(check,IS_TV?2000:3000);
})();