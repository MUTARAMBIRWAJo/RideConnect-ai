#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -z "${DATABASE_URL:-}" && -f .env ]]; then
  DATABASE_URL="$(grep -E '^DATABASE_URL=' .env | head -n1 | cut -d= -f2- || true)"
  export DATABASE_URL
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set. Set it in your environment or .env."
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required but not installed."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but not installed."
  exit 1
fi

echo "[1/5] Aligning legacy driver_locations schema (safe, idempotent)..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
ALTER TABLE IF EXISTS driver_locations
  ADD COLUMN IF NOT EXISTS recorded_at TIMESTAMP DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS heading NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS speed_kmh NUMERIC(6,2),
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_driver_locations_recorded_at
  ON driver_locations(recorded_at DESC);

DO $$
DECLARE
  fk_name text;
  ref_table text;
BEGIN
  SELECT tc.constraint_name, ccu.table_name
  INTO fk_name, ref_table
  FROM information_schema.table_constraints tc
  JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
   AND tc.table_schema = kcu.table_schema
  JOIN information_schema.constraint_column_usage ccu
    ON ccu.constraint_name = tc.constraint_name
   AND ccu.table_schema = tc.table_schema
  WHERE tc.table_name = 'driver_locations'
    AND tc.constraint_type = 'FOREIGN KEY'
    AND kcu.column_name = 'driver_id'
  LIMIT 1;

  IF fk_name IS NOT NULL AND ref_table <> 'drivers' THEN
    EXECUTE format('ALTER TABLE driver_locations DROP CONSTRAINT %I', fk_name);
    EXECUTE 'ALTER TABLE driver_locations ADD CONSTRAINT driver_locations_driver_id_fkey FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE';
  END IF;
END
$$;
SQL

echo "[2/5] Applying AI migration..."
psql "$DATABASE_URL" -f migrations/001_ai_tables.sql >/dev/null

echo "[3/5] Repairing sequence values..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
DECLARE
  r RECORD;
  max_id bigint;
BEGIN
  FOR r IN
    SELECT
      seq_ns.nspname AS seq_schema,
      seq.relname AS seq_name,
      tbl_ns.nspname AS tbl_schema,
      tbl.relname AS tbl_name,
      col.attname AS col_name
    FROM pg_class seq
    JOIN pg_namespace seq_ns ON seq_ns.oid = seq.relnamespace
    JOIN pg_depend dep ON dep.objid = seq.oid AND dep.deptype = 'a'
    JOIN pg_class tbl ON tbl.oid = dep.refobjid
    JOIN pg_namespace tbl_ns ON tbl_ns.oid = tbl.relnamespace
    JOIN pg_attribute col ON col.attrelid = tbl.oid AND col.attnum = dep.refobjsubid
    WHERE seq.relkind = 'S'
      AND tbl_ns.nspname = 'public'
  LOOP
    EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I.%I', r.col_name, r.tbl_schema, r.tbl_name)
      INTO max_id;
    EXECUTE format('SELECT setval(%L, %s, %s)',
      r.seq_schema || '.' || r.seq_name,
      GREATEST(max_id, 1),
      CASE WHEN max_id > 0 THEN 'true' ELSE 'false' END
    );
  END LOOP;
END
$$;
SQL

echo "[4/5] Running Rwanda seed script..."
python3 seeds/002_rwanda_seed.py

echo "[5/5] Seed complete."
