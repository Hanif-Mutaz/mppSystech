-- Skema PostgreSQL untuk MPP Server.
-- Dijalankan otomatis oleh backend.init_db() (idempoten, aman dijalankan berulang).

-- ============ Sumber data utama (kontrak API lama tetap sama) ============
-- Satu baris per key localStorage (mpp23db, mpp25attendance, ...), bukan satu blob raksasa.
CREATE TABLE IF NOT EXISTS app_kv (
  key         TEXT PRIMARY KEY,
  value       TEXT        NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by  TEXT        NOT NULL DEFAULT 'desktop'
);

-- Counter versi global (dipakai server_bridge.js untuk deteksi perubahan).
CREATE TABLE IF NOT EXISTS app_revision (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  version     BIGINT      NOT NULL DEFAULT 0,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  source      TEXT        NOT NULL DEFAULT 'desktop'
);
INSERT INTO app_revision (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS scan_events (
  id             BIGSERIAL PRIMARY KEY,
  device_id      TEXT        NOT NULL DEFAULT '',
  employee_code  TEXT        NOT NULL,
  scan_type      TEXT        NOT NULL DEFAULT 'QR',
  source         TEXT        NOT NULL DEFAULT 'scanner',
  payload        JSONB       NOT NULL DEFAULT '{}'::jsonb,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_scan_events_created ON scan_events (created_at);
CREATE INDEX IF NOT EXISTS ix_scan_events_emp     ON scan_events (employee_code);

-- ============ Tabel per entitas (read model, diisi otomatis dari app_kv) ============
-- Bisa di-query dengan SQL biasa untuk laporan/integrasi. Jangan ditulis manual:
-- isinya dibangun ulang dari key terkait tiap kali key itu berubah.

CREATE TABLE IF NOT EXISTS employees (          -- dari mpp23db.Master_Karyawan
  emp_id      TEXT PRIMARY KEY,
  barcode     TEXT,
  nama        TEXT,
  departemen  TEXT,
  grp         TEXT,
  status      TEXT,
  work_type   TEXT,
  position    TEXT,
  line        TEXT,
  join_date   TEXT,
  data        JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_employees_barcode ON employees (barcode);

CREATE TABLE IF NOT EXISTS lines (              -- dari mpp23db.Master_Line
  line  TEXT PRIMARY KEY,
  data  JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_matrix (       -- dari mpp23db.Skill_Matrix
  id          BIGSERIAL PRIMARY KEY,
  emp_id      TEXT,
  nama        TEXT,
  skill_line  TEXT,
  data        JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_skill_emp ON skill_matrix (emp_id);

CREATE TABLE IF NOT EXISTS attendance (         -- dari mpp25attendance
  id         BIGSERIAL PRIMARY KEY,
  emp_id     TEXT,
  name       TEXT,
  line       TEXT,
  shift      TEXT,
  work_date  DATE,
  time_in    TEXT,
  time_out   TEXT,
  data       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_att_emp  ON attendance (emp_id);
CREATE INDEX IF NOT EXISTS ix_att_date ON attendance (work_date);

CREATE TABLE IF NOT EXISTS assignments (        -- dari mpp23assign
  id         BIGSERIAL PRIMARY KEY,
  emp_id     TEXT,
  name       TEXT,
  line       TEXT,
  job        TEXT,
  shift      TEXT,
  work_date  DATE,
  data       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_assign_emp  ON assignments (emp_id);
CREATE INDEX IF NOT EXISTS ix_assign_date ON assignments (work_date);

CREATE TABLE IF NOT EXISTS app_users (          -- dari mpp28users (TANPA password)
  username  TEXT PRIMARY KEY,
  role      TEXT,
  fullname  TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (          -- dari mpp28audit
  id         BIGSERIAL PRIMARY KEY,
  logged_at  TEXT,
  username   TEXT,
  role       TEXT,
  action     TEXT
);
