# -*- coding: utf-8 -*-
import os
import sys

import paramiko

HOST = "147.78.65.84"
USER = "root"
PASSWORD = os.environ.get("DEPLOY_PASSWORD", "vhvtm45LULbB")
REMOTE = "/root/library-web-system"

cmds = [
    "pm2 list",
    "curl -s -m 5 http://127.0.0.1:3001/api/health || echo HEALTH_FAIL",
    f"cd {REMOTE} && bash deploy-upgrade.sh",
    "sleep 2",
    "curl -s -m 5 http://127.0.0.1:3001/api/health || echo HEALTH_FAIL",
    "ss -tlnp | grep 3001 || true",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
for cmd in cmds:
    sys.stdout.buffer.write(f"\n=== {cmd} ===\n".encode("utf-8"))
    sys.stdout.flush()
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    out = stdout.read()
    err = stderr.read()
    if out:
        sys.stdout.buffer.write(out)
    if err:
        sys.stdout.buffer.write(b"ERR: ")
        sys.stdout.buffer.write(err)
client.close()
