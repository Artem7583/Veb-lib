# -*- coding: utf-8 -*-
import os
import sys

import paramiko

HOST = "147.78.65.84"
USER = "root"
PASSWORD = os.environ.get("DEPLOY_PASSWORD")
if not PASSWORD:
    raise SystemExit("Задайте DEPLOY_PASSWORD")

cmd = (
    "cd /root/library-web-system && "
    "set -a && source .env && set +a && "
    'PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" '
    "-f sql/reset-catalog-only.sql"
)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
_, stdout, stderr = client.exec_command(cmd)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print(out)
if err.strip():
    print(err, file=sys.stderr)
client.close()
if "ERROR" in out.upper() or "ERROR" in err.upper():
    raise SystemExit(1)
print("Catalog reset OK")
