#!/usr/bin/env bash
set -euo pipefail

ZIP_PATH="/tmp/shenjikanban-release.zip"
WORK_DIR="/tmp/shenjikanban-release-current"
FRONTEND_ROOT="/www/wwwroot/shenjikanban"
API_ROOT="/opt/shenjikanban/server"
SERVICE_NAME="audit-kanban.service"

if [[ ! -f "$ZIP_PATH" ]]; then
  echo "Release package not found: $ZIP_PATH" >&2
  exit 1
fi

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$FRONTEND_ROOT" "$API_ROOT"

python3 - "$ZIP_PATH" "$WORK_DIR" <<'PY'
import sys
import zipfile
from pathlib import Path

zip_path = Path(sys.argv[1])
work_dir = Path(sys.argv[2])
with zipfile.ZipFile(zip_path) as archive:
    archive.extractall(work_dir)
PY

if [[ ! -d "$WORK_DIR/dist" ]]; then
  echo "Release package missing dist directory" >&2
  exit 1
fi

if [[ ! -f "$WORK_DIR/server/audit_api.py" ]]; then
  echo "Release package missing server/audit_api.py" >&2
  exit 1
fi

cp -a "$WORK_DIR/dist/." "$FRONTEND_ROOT/"

cp "$WORK_DIR/server/audit_api.py" "$API_ROOT/audit_api.py"
cp "$WORK_DIR/server/schema.sql" "$API_ROOT/schema.sql"
if [[ -f "$WORK_DIR/server/postgres_schema.sql" ]]; then
  cp "$WORK_DIR/server/postgres_schema.sql" "$API_ROOT/postgres_schema.sql"
fi
mkdir -p "$API_ROOT/uploads"

systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"
nginx -t
systemctl reload nginx

python3 - <<'PY'
import json
import urllib.request

checks = [
    "http://127.0.0.1:3008/api/health",
    "http://127.0.0.1:8088/api/audit/dashboard/summary",
]

for url in checks:
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8")
        if response.status != 200:
            raise SystemExit(f"Health check failed: {url} -> {response.status}")
        try:
            data = json.loads(body)
        except Exception:
            data = {"raw": body[:120]}
        print(f"HEALTH_OK {url} {data}")
PY

echo "DEPLOY_OK"
