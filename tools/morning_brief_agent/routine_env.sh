#!/usr/bin/env bash
# Bring up the ASA test environment inside a fresh Claude routine sandbox.
# Usage: source tools/morning_brief_agent/routine_env.sh   (from the repo root)
# Result: $ASA_VENV active (Python 3.12), local Postgres on :5433 migrated to head,
# ASA_DATABASE_URL / ASA_TEST_DATABASE_URL exported. If Postgres is unavailable the venv is
# still activated and ASA_PG_AVAILABLE=0 so callers can state the limitation in the PR.
set -u
ROOT="$(git rev-parse --show-toplevel)"
export ASA_VENV="${ASA_VENV:-${TMPDIR:-/tmp}/asa-venv312}"
if [ ! -x "$ASA_VENV/bin/python" ]; then
  uv venv -q --python 3.12 "$ASA_VENV" || python3.12 -m venv "$ASA_VENV"
fi
# shellcheck disable=SC1091
. "$ASA_VENV/bin/activate"
(cd "$ROOT" && { uv pip install -q -e '.[dev]' 2>/dev/null || pip install -q -e '.[dev]'; })

export ASA_PG_AVAILABLE=0
PGBIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)"
if [ -n "$PGBIN" ] && id postgres >/dev/null 2>&1; then
  PGROOT="${ASA_PG_ROOT:-/var/tmp/asa-pg}"
  mkdir -p "$PGROOT" && chown postgres "$PGROOT" && chmod 755 "$PGROOT"
  [ -d "$PGROOT/data" ] || su postgres -s /bin/bash -c "$PGBIN/initdb -D $PGROOT/data -A trust >/dev/null"
  su postgres -s /bin/bash -c "$PGBIN/pg_ctl -D $PGROOT/data -o '-p 5433 -k $PGROOT' -l $PGROOT/log -w start" >/dev/null 2>&1 || true
  if psql -h "$PGROOT" -p 5433 -U postgres -tAc 'select 1' >/dev/null 2>&1; then
    psql -h "$PGROOT" -p 5433 -U postgres -q -c "create user asa superuser password 'asa'" 2>/dev/null || true
    psql -h "$PGROOT" -p 5433 -U postgres -q -c "create database asa_test owner asa" 2>/dev/null || true
    export ASA_DATABASE_URL="postgresql+psycopg://asa:asa@localhost:5433/asa_test"
    export ASA_TEST_DATABASE_URL="$ASA_DATABASE_URL"
    (cd "$ROOT" && alembic upgrade head >/dev/null 2>&1) && export ASA_PG_AVAILABLE=1
  fi
fi
echo "asa routine env: python=$(python --version 2>&1) postgres_available=$ASA_PG_AVAILABLE"
