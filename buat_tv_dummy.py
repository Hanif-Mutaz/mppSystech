#!/usr/bin/env python3
"""Bikin frontend/tv_dummy.html dari frontend/tv.html dengan DATA DUMMY (semua slot terisi).

Pemakaian (dari folder repo):
    python buat_tv_dummy.py
Lalu buka frontend/tv_dummy.html (klik 2x / drag ke browser). Tidak butuh server/PostgreSQL.

Aman: skrip sinkronisasi server (storage_boot.js & server_bridge.js) DIBUANG di file dummy,
jadi data dummy tidak pernah dikirim ke server dan data asli tidak tertimpa.
Tambah ?keep=1 di URL kalau tidak mau data di-reset tiap refresh.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'frontend', 'tv.html')
OUT = os.path.join(HERE, 'frontend', 'tv_dummy.html')

# (nama line, standard MP) -> 1 Cell Leader + (std-2) Operator + 1 Inspector
LINES = [('41SY01', 7), ('41SY02', 5), ('41SY05', 3), ('41SY08', 4), ('41SY09', 5), ('41SY16', 4),
         ('41SY21', 3), ('41SY22', 3), ('41SY23', 7), ('41SY25', 6), ('41SY30', 5), ('41SY31', 5),
         ('41SY32', 3), ('41SY33', 3), ('41SY34', 3), ('41SY35', 3), ('41SY36', 5), ('41SY39', 8)]

SEED = r"""
(function(){
  'use strict';
  var LINES=__LINES__;
  var SHIFTS=['SHIFT 1','SHIFT 2','SHIFT 3'];
  var FIRST=['Andi','Budi','Citra','Dewi','Eko','Fajar','Gita','Hadi','Indra','Joko','Kartika','Lukman','Maya','Nanda','Oki','Putri','Qori','Rini','Sandi','Tika','Umar','Vina','Wawan','Yoga','Zahra','Agus','Bayu','Dina','Edi','Fitri','Galih','Heni','Irfan','Jihan','Kevin','Lina','Mirza','Nisa','Rizki','Sari'];
  var LAST=['Pratama','Saputra','Wijaya','Lestari','Hidayat','Kurniawan','Permata','Santoso','Rahma','Nugroho','Utami','Firmansyah','Ramadhan','Susanto','Anggraini','Maulana','Setiawan','Puspita','Hakim','Wibowo'];
  function pad(n,l){return String(n).padStart(l||2,'0')}
  function ld(d){return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())}
  var q=location.search;
  if(/[?&]keep=1\b/.test(q)&&localStorage.getItem('mpp23db'))return;   /* jangan reset */

  var db={Master_Karyawan:[],Skill_Matrix:[],Master_Line:[]};
  LINES.forEach(function(l){db.Master_Line.push({Line:l[0],'Cell Leader':1,'Opt Produksi':l[1]-2,Inspector:1,Total:l[1],'':''})});

  /* satu kelompok karyawan per shift, supaya orang yang sama tidak muncul di 2 shift sekaligus */
  var seq=0,pool={},assignsTpl={};
  SHIFTS.forEach(function(sh,si){
    pool[sh]=[];
    LINES.forEach(function(l){
      var roles=['CELL LEADER'];for(var i=1;i<=l[1]-2;i++)roles.push('OPT '+i);roles.push('INSPECTOR');
      roles.forEach(function(role){
        seq++;
        var id='DMY'+pad(seq,4),nm=FIRST[(seq*7+si)%FIRST.length]+' '+LAST[(seq*3+si)%LAST.length];
        db.Master_Karyawan.push({EmpID:id,Barcode:'9'+pad(seq,7),Nama:nm,Departemen:'PRODUKSI',Group:'ABC'.charAt(si),Status:seq%4?'Tetap':'Kontrak',Join_Date:'2025-01-02 00:00:00',WorkType:'SHIFT'});
        var sk={EmpID:id,Nama:nm};
        for(var k=1;k<=5;k++){sk['Skill Line '+k]=k===1?l[0]:'';sk['Skill Proses '+k]=k===1?role:''}
        db.Skill_Matrix.push(sk);
        pool[sh].push({emp:id,name:nm,line:l[0],job:role});
      });
    });
  });

  /* karyawan MENUNGGU LINE: sudah absen masuk, tapi belum ditempatkan di line mana pun */
  var WAIT_N=8,waitPool={};
  SHIFTS.forEach(function(sh,si){
    waitPool[sh]=[];
    for(var w=0;w<WAIT_N;w++){
      seq++;
      var wid='DMY'+pad(seq,4),wnm=FIRST[(seq*5+si)%FIRST.length]+' '+LAST[(seq*11+si)%LAST.length];
      db.Master_Karyawan.push({EmpID:wid,Barcode:'9'+pad(seq,7),Nama:wnm,Departemen:'PRODUKSI',Group:'ABC'.charAt(si),Status:'Tetap',Join_Date:'2025-03-03 00:00:00',WorkType:'SHIFT'});
      var wl=LINES[(w*5+si)%LINES.length],wsk={EmpID:wid,Nama:wnm};
      for(var k=1;k<=5;k++){wsk['Skill Line '+k]=(k===1&&w%4!==3)?wl[0]:'';wsk['Skill Proses '+k]=(k===1&&w%4!==3)?(w%2?'OPT 1':'INSPECTOR'):''}
      db.Skill_Matrix.push(wsk);
      waitPool[sh].push({emp:wid,name:wnm,min:w*3});
    }
  });

  var assigns=[],attendance=[],plans={},now=new Date();
  for(var off=-2;off<=2;off++){
    var d=new Date(now.getFullYear(),now.getMonth(),now.getDate()+off),date=ld(d);
    SHIFTS.forEach(function(sh){
      plans[date+'|'+sh]=LINES.map(function(l){return l[0]});
      pool[sh].forEach(function(p){
        assigns.push({emp:p.emp,name:p.name,shift:sh,line:p.line,job:p.job,date:date,workDate:date,assignmentSource:'DUMMY',locked:true});
        attendance.push({emp:p.emp,barcode:'',name:p.name,date:date,workDate:date,shift:sh,in:'07:50:00',inDateTime:date+' 07:50:00',inISO:date+'T00:50:00.000Z',out:'',outDateTime:'',duration:'',line:p.line,job:p.job,status:'CHECK IN'});
      });
      waitPool[sh].forEach(function(p){
        var hh=pad(7+Math.floor((50+p.min)/60)),mm=pad((50+p.min)%60);
        attendance.push({emp:p.emp,barcode:'',name:p.name,date:date,workDate:date,shift:sh,in:hh+':'+mm+':00',inDateTime:date+' '+hh+':'+mm+':00',inISO:date+'T'+pad(Math.max(0,Number(hh)-7))+':'+mm+':00.000Z',out:'',outDateTime:'',duration:'',line:'',job:'',status:'CHECK IN'});
      });
    });
  }
  /* (karyawan menunggu line ditambahkan ke attendance di bawah) */
  var shifts={count:2,mode:'AUTO',items:[
    {name:'SHIFT 1',start:'08:00',end:'20:00',endDay:0,earlyHours:2,lateHours:6},
    {name:'SHIFT 2',start:'20:00',end:'08:00',endDay:1,earlyHours:2,lateHours:6},
    {name:'SHIFT 3',start:'08:00',end:'16:00',endDay:0,earlyHours:2,lateHours:6}]};
  try{
    localStorage.removeItem('MPP_EMPTY_DATABASE');
    localStorage.setItem('mpp23db',JSON.stringify(db));
    localStorage.setItem('mpp23assign',JSON.stringify(assigns));
    localStorage.setItem('mpp25attendance',JSON.stringify(attendance));
    localStorage.setItem('mpp25dailyplans',JSON.stringify(plans));
    localStorage.setItem('mpp25lastscans','{}');
    localStorage.setItem('mpp26shifts',JSON.stringify(shifts));
    localStorage.setItem('mpp220tvMode','1');
  }catch(e){console.warn('Seed dummy gagal',e)}
})();
""".replace('__LINES__', json.dumps(LINES))


def main():
    s = open(SRC, encoding='utf-8').read()
    boot = '<script src="/frontend/storage_boot.js"></script>'
    bridge = '<script src="/frontend/server_bridge.js"></script>'
    if boot not in s:
        sys.exit('storage_boot.js tag tidak ditemukan di tv.html')
    s = s.replace(boot, '<script id="mppDummySeed">' + SEED + '</script>', 1)
    s = s.replace(bridge, '<!-- server_bridge.js dimatikan di file dummy -->')
    open(OUT, 'w', encoding='utf-8').write(s)
    print('OK ->', OUT)


if __name__ == '__main__':
    main()
