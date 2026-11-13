// Boot frontend/index.html (atau tv.html) di jsdom dan kembalikan window.
const { JSDOM, VirtualConsole } = require('jsdom');
const fs = require('fs');
const path = require('path');

exports.boot = async function boot(file = 'index.html') {
  const full = path.join(__dirname, '..', 'frontend', file);
  const html = fs.readFileSync(full, 'utf8').replace(/<script src="\/frontend\/[^"]+"><\/script>/g, '');
  const dom = new JSDOM(html, {
    runScripts: 'dangerously', pretendToBeVisual: true, url: 'http://localhost:5000/',
    virtualConsole: new VirtualConsole(),
    beforeParse(w) {
      w.__alerts = [];
      w.alert = m => { w.__alerts.push(String(m)); };
      w.structuredClone = o => JSON.parse(JSON.stringify(o));
      w.confirm = () => true;
      w.prompt = () => null;
      w.fetch = () => Promise.reject(new Error('offline'));
      w.WebSocket = function () { this.send = () => {}; this.close = () => {}; };
      w.HTMLElement.prototype.scrollIntoView = () => {};
      w.scrollTo = () => {};
    },
  });
  await new Promise(r => setTimeout(r, 2500)); // tunggu skrip boot + setTimeout(0) milik patch lama
  return dom.window;
};

// Data kecil yang terkontrol, dipasang ke db milik aplikasi.
exports.seed = function seed(w, { employees, skills, lines, plan = ['41SY01'] }) {
  w.__seed = { employees, skills, lines, plan };
  w.eval(`(function(){const s=window.__seed;
    db.Master_Karyawan=s.employees; db.Master_Line=s.lines; db.Skill_Matrix=s.skills;
    assigns.length=0; attendance.length=0; for(const k of Object.keys(lastScans)) delete lastScans[k];
    for(const k of Object.keys(dailyPlans)) delete dailyPlans[k];
    if(s.plan) dailyPlans[dailyPlanKey('2026-11-13','SHIFT 1')]=s.plan;
    window.getScanInContext=function(){return {name:'SHIFT 1',workDate:'2026-11-13'}};
    window.formatShiftWindow=function(){return 'x'};
  })()`);
};

exports.emp = (id, extra = {}) => ({ EmpID: id, Barcode: id, Nama: 'N' + id, Departemen: 'PRODUKSI', Group: 'A', Status: 'ACTIVE', Join_Date: '2026-01-01', WorkType: 'SHIFT', Position: 'OPERATOR', ...extra });
exports.line = (name, opt, { cell = 1, ins = 1 } = {}) => ({ Line: name, 'Cell Leader': cell, Inspector: ins, 'Opt Produksi': opt, Total: cell + ins + opt });
exports.entries = (id, list) => ({ EmpID: id, Nama: 'N' + id, 'Skill Entries': list.map(([line, process], i) => ({ line, process, priority: i + 1 })) });

exports.scan = function scan(w, id) {
  w.document.getElementById('barcode').value = id;
  w.scanIn();
  return {
    assigns: JSON.parse(JSON.stringify(w.eval('assigns'))),
    att: JSON.parse(JSON.stringify(w.eval('attendance'))).find(a => a.emp === id),
    msg: (w.document.getElementById('scanMsg') || {}).textContent || '',
  };
};
