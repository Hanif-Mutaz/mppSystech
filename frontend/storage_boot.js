/* MPP storage boot  (dimuat PALING AWAL di <head>, desktop DAN TV)
   Masalah: localStorage terikat ke origin (http://localhost:5000 berbeda dengan
   http://192.168.x.x:5000), sehingga tiap URL punya data sendiri.
   Solusi: server (SQLite) adalah satu-satunya sumber kebenaran. Sebelum aplikasi
   membaca localStorage, data server ditarik (XHR sinkron) dan DITULIS ke localStorage
   origin yang sedang dipakai. localStorage hanya berfungsi sebagai cache. */
(function(){
  'use strict';
  var LOCAL_ONLY={'mpp220tvMode':1};            /* setelan per-perangkat, tidak disinkronkan */
  function synced(k){return typeof k==='string'&&k.toLowerCase().indexOf('mpp')===0&&!LOCAL_ONLY[k]}
  window.__mppSynced=synced;
  window.__mppBase={};window.__mppBootVersion=0;window.__mppBootOK=false;window.__mppServerEmpty=false;
  try{
    var x=new XMLHttpRequest();
    x.open('GET','/api/state?_='+Date.now(),false);
    x.send();
    if(x.status!==200)return;
    var j=JSON.parse(x.responseText);
    if(!j||!j.ok)return;
    var p=(j.payload&&typeof j.payload==='object')?j.payload:{};
    var keys=Object.keys(p).filter(synced);
    window.__mppBootOK=true;window.__mppBootVersion=Number(j.version)||0;
    if(!keys.length){window.__mppServerEmpty=true;return}   /* server kosong: data lokal dipakai untuk mengisi server */
    /* server menang: buang key mpp* lokal yang tidak ada di server (data basi origin lain) */
    var stale=[];
    for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(synced(k)&&!Object.prototype.hasOwnProperty.call(p,k))stale.push(k)}
    stale.forEach(function(k){localStorage.removeItem(k)});
    keys.forEach(function(k){var v=String(p[k]);if(localStorage.getItem(k)!==v)localStorage.setItem(k,v);window.__mppBase[k]=v});
  }catch(e){console.warn('MPP boot sync gagal (pakai data lokal)',e)}
})();
