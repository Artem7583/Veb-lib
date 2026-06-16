#!/usr/bin/env bash
# Обновление кода на сервере БЕЗ сброса базы данных (сохраняет .env)
set -euo pipefail

APP_DIR="/root/library-web-system"
cd "$APP_DIR"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

.venv/bin/python -c "import app; app.ensure_schema(); app.ensure_upload_dirs()"

set -a
[ -f .env ] && source .env
set +a

pm2 delete library-web-system >/dev/null 2>&1 || true
FLASK_DEBUG=false pm2 start ".venv/bin/python app.py" \
  --name library-web-system \
  --cwd "$APP_DIR" \
  --time \
  --update-env

pm2 save
sleep 2
curl -fsS "http://127.0.0.1:${PORT:-3001}/api/health"
echo ""
echo "Upgrade OK"
