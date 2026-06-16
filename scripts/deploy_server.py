# -*- coding: utf-8 -*-
"""Upload project files to production server and restart PM2."""
from __future__ import annotations

import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import paramiko

HOST = "147.78.65.84"
USER = "root"
PASSWORD = os.environ.get("DEPLOY_PASSWORD")
if not PASSWORD:
    raise SystemExit("Задайте переменную окружения DEPLOY_PASSWORD для деплоя.")
REMOTE_DIR = "/root/library-web-system"

ROOT = Path(__file__).resolve().parents[1]

FILES = [
    "app.py",
    "requirements.txt",
    "smoke_test.py",
    "README.md",
    "deploy-upgrade.sh",
    "data/catalog_import_template.csv",
    "public/index.html",
    "public/js/app.js",
    "public/js/layout.js",
    "public/css/styles.css",
    "public/img/logo.svg",
    "public/img/icon-vk.svg",
    "public/img/icon-max.svg",
    "public/img/author-pushkin.svg",
    "public/img/author-akhmatova.svg",
    "public/img/author-gogol.svg",
    "public/favicon.svg",
    "sql/schema.sql",
    "sql/reset-demo-data.sql",
    "sql/reset-catalog-only.sql",
    "sql/fix-categories.sql",
    "sql/seed.sql",
    "data/catalog_import_template.csv",
]

UPLOAD_DIRS = [
    "public/partials",
    "public/img/authors",
    "public/img/home",
    "public/uploads",
]


def run(client, cmd):
    print(f"$ {cmd}")
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip() and code != 0:
        print(err.rstrip())
    return code, out


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=60)
    sftp = client.open_sftp()

    run(client, f"mkdir -p {REMOTE_DIR}/public/js {REMOTE_DIR}/public/css {REMOTE_DIR}/public/uploads/covers {REMOTE_DIR}/sql")

    for rel in FILES:
        local = ROOT / rel
        if not local.is_file():
            print(f"SKIP missing: {rel}")
            continue
        remote = f"{REMOTE_DIR}/{rel.replace(chr(92), '/')}"
        remote_dir = os.path.dirname(remote)
        run(client, f"mkdir -p {remote_dir}")
        print(f"Upload: {rel}")
        sftp.put(str(local), remote)

    for rel_dir in UPLOAD_DIRS:
        local_dir = ROOT / rel_dir
        if not local_dir.exists():
            continue
        for local in local_dir.rglob("*"):
            if local.is_file():
                rel = local.relative_to(ROOT).as_posix()
                remote = f"{REMOTE_DIR}/{rel}"
                run(client, f"mkdir -p {os.path.dirname(remote)}")
                print(f"Upload: {rel}")
                sftp.put(str(local), remote)

    sftp.close()
    run(client, f"chmod +x {REMOTE_DIR}/deploy-upgrade.sh")
    code, _ = run(client, f"bash {REMOTE_DIR}/deploy-upgrade.sh")
    run(client, "pm2 list | grep library || true")
    run(client, "curl -s http://127.0.0.1:3001/api/health")
    client.close()
    if code != 0:
        sys.exit(code)
    print("\nDeploy completed successfully.")
    print("Site: http://147.78.65.84:3001")


if __name__ == "__main__":
    main()
