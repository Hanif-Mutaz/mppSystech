/* MPP TV boot: tarik state dari server SEBELUM aplikasi membaca localStorage.
   Dimuat paling awal di <head> tv.html. XHR sengaja sinkron supaya data sudah siap
   saat aplikasi menginisialisasi variabel (attendance, db, dst.) dari localStorage. */
(function(){
  'use strict';
  try{
    var x=new XMLHttpRequest();
    x.open('GET','/api/state?_='+Date.now(),false);
    x.send();
    if(x.status!==200)return;
    var j=JSON.parse(x.responseText);
    if(!j||!j.ok||!j.payload)return;
    var n=0;
    Object.keys(j.payload).forEach(function(k){
      if(k.toLowerCase().indexOf('mpp')===0){localStorage.setItem(k,String(j.payload[k]));n++}
    });
    if(n){
      window.__mppTvBootVersion=j.version;
      sessionStorage.setItem('mppServerVersion',String(j.version));
    }
  }catch(e){console.warn('MPP TV boot sync gagal',e)}
})();
