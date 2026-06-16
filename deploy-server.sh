#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/library-web-system"
APP_DB_USER="library_app"
APP_DB_PASSWORD="Lib2026!Db83"
APP_DB_NAME="library_system"

systemctl start postgresql

mkdir -p "$APP_DIR"

cd "$APP_DIR"
python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${APP_DIR}/.venv/bin/python" -m pip install -r requirements.txt

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${APP_DB_USER}'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE USER ${APP_DB_USER} WITH PASSWORD '${APP_DB_PASSWORD}';"
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${APP_DB_NAME}'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE ${APP_DB_NAME} OWNER ${APP_DB_USER};"
fi

cat > "${APP_DIR}/.env" <<EOF
PORT=3001
DB_HOST=localhost
DB_PORT=5432
DB_NAME=${APP_DB_NAME}
DB_USER=${APP_DB_USER}
DB_PASSWORD=${APP_DB_PASSWORD}
AUTH_SECRET=library-secret
EOF

export PGPASSWORD="${APP_DB_PASSWORD}"
psql -h localhost -U "${APP_DB_USER}" -d "${APP_DB_NAME}" -c "DROP TABLE IF EXISTS book_requests, book_transactions, system_settings, loans, app_users, patrons, book_copies, books, categories CASCADE;"
psql -h localhost -U "${APP_DB_USER}" -d "${APP_DB_NAME}" -f "${APP_DIR}/sql/schema.sql"
psql -h localhost -U "${APP_DB_USER}" -d "${APP_DB_NAME}" -f "${APP_DIR}/sql/reset-demo-data.sql"

pm2 delete library-web-system >/dev/null 2>&1 || true
pm2 start "${APP_DIR}/.venv/bin/python app.py" --name library-web-system --update-env --cwd "${APP_DIR}" --time
pm2 save

curl -fsS http://127.0.0.1:3001/api/health
