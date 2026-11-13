const test = require('node:test');
const assert = require('node:assert/strict');
const { boot, seed, emp, line, entries, scan } = require('./helpers');
const J = o => JSON.parse(JSON.stringify(o)); // array dari jsdom beda realm: samakan dulu sebelum deepEqual

const LINES = [line('41SY01', 5), line('41SY02', 6), line('41SY03', 2)];
let w;
test.before(async () => { w = await boot('index.html'); });
test.after(() => { try { w.close(); } catch (e) {} });

// ---------- Aturan 1: Skill Proses terikat ke Skill Line (scan) ----------
test('scan memakai pasangan Line+Proses persis dari Skill Entries', () => {
  seed(w, { employees: [emp('E1')], lines: LINES, plan: ['41SY01', '41SY02'], skills: [entries('E1', [['41SY01', 'Inspector'], ['41SY02', 'Opt 2']])] });
  const r = scan(w, 'E1');
  assert.equal(r.assigns.length, 1);
  assert.deepEqual([r.assigns[0].line, r.assigns[0].job], ['41SY01', 'INSPECTOR']);
});

test('slot pasangan penuh: TIDAK dilempar ke line lain sebagai proses yang sama', () => {
  seed(w, { employees: [emp('E1'), emp('E2')], lines: LINES, plan: ['41SY01', '41SY02'],
    skills: [entries('E1', [['41SY01', 'Inspector']]), entries('E2', [['41SY01', 'Inspector'], ['41SY02', 'Opt 2']])] });
  scan(w, 'E1');
  const r = scan(w, 'E2');
  // Inspector 41SY01 sudah terisi. E2 boleh ke 41SY02/OPT 2 (pasangan sendiri), tidak boleh 41SY02/INSPECTOR.
  assert.equal(r.assigns.length, 2);
  assert.deepEqual([r.assigns[1].line, r.assigns[1].job], ['41SY02', 'OPT 2']);
});

test('hanya punya Inspector@41SY01 dan slot penuh -> menunggu, bukan Inspector di 41SY02', () => {
  seed(w, { employees: [emp('E1'), emp('E2')], lines: LINES, plan: ['41SY01', '41SY02'],
    skills: [entries('E1', [['41SY01', 'Inspector']]), entries('E2', [['41SY01', 'Inspector']])] });
  scan(w, 'E1');
  const r = scan(w, 'E2');
  assert.equal(r.assigns.length, 1);
  assert.equal(r.att.waitingLine, true);
});

test('proses yang sama di dua line berbeda sama-sama dikenali', () => {
  seed(w, { employees: [emp('E1')], lines: LINES, plan: ['41SY02'], skills: [entries('E1', [['41SY01', 'Opt 2'], ['41SY02', 'Opt 2']])] });
  const r = scan(w, 'E1');
  assert.deepEqual([r.assigns[0].line, r.assigns[0].job], ['41SY02', 'OPT 2']);
});

// ---------- Aturan 3 ----------
test('hanya Cell Leader yang boleh lebih dari 1; Inspector maksimal 1', () => {
  const roles = w.v234MasterRoles({ Line: 'X', 'Cell Leader': 2, Inspector: 5, 'Opt Produksi': 2 });
  assert.deepEqual(J(roles), ['CELL LEADER', 'CELL LEADER 2', 'OPT 1', 'OPT 2', 'INSPECTOR']);
});

// ---------- Aturan 4 ----------
test('normalizeLine2312 tidak lagi menukar Inspector dan Opt diam-diam', () => {
  const n = w.normalizeLine2312({ Line: 'L', 'Cell Leader': 1, Inspector: 5, 'Opt Produksi': 1 });
  assert.equal(n.Inspector, 5);
  assert.equal(n['Opt Produksi'], 1);
});

// ---------- Aturan 5 ----------
test('plan kosong: auto-assign ditolak dengan pesan jelas, absensi tetap tercatat', () => {
  seed(w, { employees: [emp('E1')], lines: LINES, plan: null, skills: [entries('E1', [['41SY01', 'Opt 1']])] });
  const r = scan(w, 'E1');
  assert.equal(r.assigns.length, 0);
  assert.ok(r.att, 'absensi harus tercatat');
  assert.match(r.att.waitingReason, /AUTO-ASSIGN DITOLAK.*Line Aktif Harian/);
});

test('line yang tidak dicentang tidak menerima auto-assign', () => {
  seed(w, { employees: [emp('E1')], lines: LINES, plan: ['41SY02'], skills: [entries('E1', [['41SY01', 'Opt 1']])] });
  assert.equal(scan(w, 'E1').assigns.length, 0);
});

// ---------- Aturan 7: Position ----------
for (const pos of ['SUPERVISOR', 'MANAGER', 'STAFF', 'LINE LEADER']) {
  test(`Position ${pos} tidak di-auto-assign, tapi absen tercatat`, () => {
    seed(w, { employees: [emp('E1', { Position: pos })], lines: LINES, skills: [entries('E1', [['41SY01', 'Opt 1']])] });
    const r = scan(w, 'E1');
    assert.equal(r.assigns.length, 0);
    assert.ok(r.att);
    assert.match(r.att.waitingReason, /tidak ditempatkan otomatis/);
  });
}

test('OPERATOR dengan skill Cell Leader tidak ke-assign jadi Cell Leader', () => {
  seed(w, { employees: [emp('E1')], lines: LINES, skills: [entries('E1', [['41SY01', 'Cell Leader']])] });
  assert.equal(scan(w, 'E1').assigns.length, 0);
});

// ---------- Aturan 2 + 6: import ----------
const wb = skill => ({
  Master_Karyawan: [emp('E1')],
  Master_Line: [line('41SY01', 5), line('41SY02', 6), line('41SY03', 2)],
  Skill_Matrix: skill,
});
const pairsOf = x => J(x.Skill_Matrix).flatMap(r => r['Skill Entries'].map(e => e.line + '/' + w.mppSkillRules.proc(e.process)));

test('format lama (Skill Line + Skill 1..10): pasangan tidak diacak', () => {
  const x = w.normalizeV230Workbook(wb([
    { EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY01', 'Skill 1': 'Inspector', 'Skill 2': 'Opt 1', 'Skill 3': 'Opt 5' },
    { EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY02', 'Skill 1': 'Opt 2' },
    { EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY03', 'Skill 1': 'Opt 2' },
  ]));
  assert.deepEqual(pairsOf(x), ['41SY01/INSPECTOR', '41SY01/OPT 1', '41SY01/OPT 5', '41SY02/OPT 2', '41SY03/OPT 2']);
});

test('format hasil export aplikasi (Skill Line, Skill Proses, Urutan) tidak jadi kosong', () => {
  const x = w.normalizeV230Workbook(wb([
    { EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY02', 'Skill Proses': 'Opt 2', Urutan: 2 },
    { EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY01', 'Skill Proses': 'Inspector', Urutan: 1 },
  ]));
  assert.deepEqual(pairsOf(x), ['41SY01/INSPECTOR', '41SY02/OPT 2']);
});

test('format lebar: Skill Line N berpasangan dengan Skill Proses N', () => {
  const x = w.normalizeV230Workbook(wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line 1': '41SY01', 'Skill Line 2': '41SY02', 'Skill Proses 1': 'Opt 1', 'Skill Proses 2': 'Opt 2' }]));
  assert.deepEqual(pairsOf(x), ['41SY01/OPT 1', '41SY02/OPT 2']);
});

test('normalisasi idempoten (dipanggil dua kali tidak menghapus skill)', () => {
  const x = w.normalizeV230Workbook(wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY01', 'Skill 1': 'Opt 1' }]));
  const y = w.normalizeV230Workbook(x);
  assert.deepEqual(pairsOf(y), ['41SY01/OPT 1']);
});

test('validasi: data bersih lolos tanpa error', () => {
  const r = w.validateImportDetailed(wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY01', 'Skill 1': 'Opt 1', 'Skill 2': 'Inspector' }]));
  assert.deepEqual(J(r.errors), []);
});

test('validasi: typo proses ditolak', () => {
  const r = w.validateImportDetailed(wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY01', 'Skill 1': 'Optt 1' }]));
  assert.ok(r.errors.some(e => /tidak dikenali pada 41SY01/.test(e)), r.errors.join('|'));
});

test('validasi: nomor Opt melebihi kapasitas line ditolak', () => {
  const r = w.validateImportDetailed(wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY03', 'Skill 1': 'Opt 3' }]));
  assert.ok(r.errors.some(e => /melebihi kapasitas 41SY03 \(maksimal OPT 2\)/.test(e)), r.errors.join('|'));
});

test('validasi: pasangan kosong sebelah ditolak (proses tanpa line, line tanpa proses)', () => {
  const r1 = w.validateImportDetailed(wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line 1': '41SY01', 'Skill Proses 1': 'Opt 1', 'Skill Proses 2': 'Opt 2' }]));
  assert.ok(r1.errors.some(e => /Skill Proses 2 \(Opt 2\) tidak punya pasangan Skill Line 2/.test(e)), r1.errors.join('|'));
  const r2 = w.validateImportDetailed(wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line 1': '41SY01', 'Skill Line 2': '41SY02', 'Skill Proses 1': 'Opt 1' }]));
  assert.ok(r2.errors.some(e => /Skill Line 2 \(41SY02\) belum punya Skill Proses/.test(e)), r2.errors.join('|'));
});

test('validasi: Inspector > 1 ditolak dengan petunjuk kolom tertukar, tanpa koreksi diam-diam', () => {
  const x = wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY01', 'Skill 1': 'Opt 1' }]);
  x.Master_Line = [{ Line: '41SY01', 'Cell Leader': 1, Inspector: 5, 'Opt Produksi': 1, Total: 7 }];
  const r = w.validateImportDetailed(x);
  assert.ok(r.errors.some(e => /Inspector = 5.*tertukar/.test(e)), r.errors.join('|'));
  assert.equal(x.Master_Line[0].Inspector, 5);
});

test('validasi: Skill Line yang tidak ada di Master_Line tetap ditolak', () => {
  const r = w.validateImportDetailed(wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line': '99XX', 'Skill 1': 'Opt 1' }]));
  assert.ok(r.errors.some(e => /tidak ada di Master_Line: 99XX/.test(e)));
});

// ---------- Aturan 1: drag-drop ----------
function asRole(role, reason) {
  w.eval(`currentUser={username:'tester',role:'${role}'}`);
  w.prompt = () => reason; w.__alerts.length = 0;
}

test('drag ke pasangan tanpa skill: SUPERVISOR boleh lanjut dengan alasan (warning, bukan blokir)', () => {
  seed(w, { employees: [emp('E1')], lines: LINES, plan: ['41SY01', '41SY02'], skills: [entries('E1', [['41SY01', 'Opt 1']])] });
  asRole('SUPERVISOR', 'bantu line kekurangan');
  assert.equal(w.mppSkillRules.gate('E1', '41SY02', 'OPT 2').proceed, true);
  assert.equal(w.mppSkillRules.gate('E1', '41SY02', 'OPT 2').overridden, true);
});

test('drag ke pasangan tanpa skill: LEADER ditahan', () => {
  asRole('LEADER', 'apa saja');
  const g = w.mppSkillRules.gate('E1', '41SY02', 'OPT 2');
  assert.equal(g.proceed, false);
  assert.match(w.__alerts.join('\n'), /Hanya ADMIN atau SUPERVISOR/);
});

test('drag ke pasangan tanpa skill: alasan < 5 karakter ditolak, dibatalkan = tidak lanjut', () => {
  asRole('SUPERVISOR', 'ok');
  assert.equal(w.mppSkillRules.gate('E1', '41SY02', 'OPT 2').proceed, false);
  asRole('SUPERVISOR', null);
  assert.equal(w.mppSkillRules.gate('E1', '41SY02', 'OPT 2').proceed, false);
});

test('drag ke pasangan yang punya skill: langsung lanjut tanpa prompt', () => {
  asRole('SUPERVISOR', null);
  const g = w.mppSkillRules.gate('E1', '41SY01', 'OPT 1');
  assert.deepEqual([g.proceed, g.overridden], [true, false]);
});

test('v2381Move (drag antar slot) dengan override mencatat MANUAL_OVERRIDE + alasan', () => {
  seed(w, { employees: [emp('E1')], lines: LINES, plan: ['41SY01', '41SY02'], skills: [entries('E1', [['41SY01', 'Opt 1']])] });
  scan(w, 'E1');
  asRole('SUPERVISOR', 'line 2 kekurangan orang');
  const a = w.eval('assigns[0]');
  const ok = w.v2381Move(a, '41SY02', 'OPT 2', '2026-11-13', 'SHIFT 1');
  assert.equal(ok, true);
  assert.deepEqual([a.line, a.job, a.skillStatus, a.overrideReason], ['41SY02', 'OPT 2', 'MANUAL_OVERRIDE', 'line 2 kekurangan orang']);
});

// ---------- Import end-to-end (importXlsx asli, hanya pembaca file yang di-stub) ----------
async function runImport(mode, workbook) {
  w.readXlsxStable = async () => JSON.parse(JSON.stringify(workbook));
  w.readXlsx = w.readXlsxStable;
  const input = w.document.getElementById('xlsx');
  Object.defineProperty(input, 'files', { configurable: true, value: [new w.File([new Uint8Array([1])], 'master.xlsx')] });
  const sel = w.document.getElementById('importMode');
  if (sel) sel.value = mode;
  await w.importXlsx();
  return J(w.eval('db.Skill_Matrix'));
}

for (const mode of ['REPLACE', 'MERGE']) {
  test(`import end-to-end (${mode}): skill per pasangan tersimpan utuh, termasuk proses sama di line berbeda`, async () => {
    const rows = await runImport(mode, wb([
      { EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY01', 'Skill 1': 'Inspector', 'Skill 2': 'Opt 1' },
      { EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY02', 'Skill 1': 'Opt 2' },
      { EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY03', 'Skill 1': 'Opt 2' },
    ]));
    const e1 = rows.find(r => r.EmpID === 'E1');
    assert.ok(e1, 'E1 harus ada');
    assert.deepEqual(e1['Skill Entries'].map(e => e.line + '/' + e.process), ['41SY01/Inspector', '41SY01/Opt 1', '41SY02/Opt 2', '41SY03/Opt 2']);
  });
}

test('import end-to-end: file bermasalah ditolak dan data lama tidak berubah', async () => {
  const before = J(w.eval('db.Skill_Matrix'));
  await runImport('REPLACE', wb([{ EmpID: 'E1', Nama: 'A', 'Skill Line': '41SY03', 'Skill 1': 'Opt 9' }]));
  assert.deepEqual(J(w.eval('db.Skill_Matrix')), before);
});
