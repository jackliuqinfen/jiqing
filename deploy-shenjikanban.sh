#!/usr/bin/env bash
set -euo pipefail

ZIP_PATH="/tmp/shenjikanban-release.zip"
WORK_DIR="/tmp/shenjikanban-release-current"
RELEASE_REPO="/opt/shenjikanban/release-git"
FRONTEND_ROOT="/www/wwwroot/shenjikanban"
API_ROOT="/opt/shenjikanban/server"
OCR_VENV_BASE="/opt/shenjikanban/ocr-venvs"
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

if ! command -v git >/dev/null 2>&1; then
  echo "Git is required before deployment. Please install git on the server." >&2
  exit 1
fi

mkdir -p "$RELEASE_REPO"
if [[ ! -d "$RELEASE_REPO/.git" ]]; then
  git -C "$RELEASE_REPO" init
  git -C "$RELEASE_REPO" config user.name "Shenjikanban Deploy Bot"
  git -C "$RELEASE_REPO" config user.email "deploy@shenjikanban.local"
fi

find "$RELEASE_REPO" -mindepth 1 -maxdepth 1 ! -name ".git" -exec rm -rf {} +
cp -a "$WORK_DIR/." "$RELEASE_REPO/"
find "$RELEASE_REPO" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$RELEASE_REPO" -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.sqlite3" -o -name "*.db" \) -delete
cat > "$RELEASE_REPO/.gitignore" <<'EOF'
__pycache__/
*.pyc
*.pyo
*.sqlite3
*.db
uploads/
node_modules/
EOF
git -C "$RELEASE_REPO" add -A
if ! git -C "$RELEASE_REPO" diff --cached --quiet; then
  git -C "$RELEASE_REPO" commit -m "deploy: $(date '+%Y-%m-%d %H:%M:%S %z')"
else
  echo "GIT_SYNC_NO_CHANGES"
fi
echo "GIT_SYNC_OK $(git -C "$RELEASE_REPO" rev-parse --short HEAD)"

OCR_REQUIREMENTS="$WORK_DIR/server/requirements-ocr.txt"
if [[ ! -f "$OCR_REQUIREMENTS" ]]; then
  echo "Release package missing server/requirements-ocr.txt" >&2
  exit 1
fi
OCR_REQUIREMENTS_HASH="$(sha256sum "$OCR_REQUIREMENTS" | awk '{print $1}')"
OCR_VENV_ROOT="$OCR_VENV_BASE/$OCR_REQUIREMENTS_HASH"
mkdir -p "$OCR_VENV_BASE"
OCR_HASH_FILE="$OCR_VENV_ROOT/.requirements-ocr.sha256"
INSTALLED_OCR_HASH=""
if [[ -f "$OCR_HASH_FILE" ]]; then
  INSTALLED_OCR_HASH="$(cat "$OCR_HASH_FILE")"
fi
if [[ ! -x "$OCR_VENV_ROOT/bin/python" || "$OCR_REQUIREMENTS_HASH" != "$INSTALLED_OCR_HASH" ]]; then
  if [[ ! -x "$OCR_VENV_ROOT/bin/python" ]]; then
    python3 -m venv "$OCR_VENV_ROOT"
  fi
  "$OCR_VENV_ROOT/bin/python" -m pip install --disable-pip-version-check -r "$OCR_REQUIREMENTS"
  "$OCR_VENV_ROOT/bin/python" -c "import PIL, pypdfium2, qcloud_cos; print('OCR_IMPORT_OK')"
  printf '%s' "$OCR_REQUIREMENTS_HASH" > "$OCR_HASH_FILE"
else
  "$OCR_VENV_ROOT/bin/python" -c "import PIL, pypdfium2, qcloud_cos; print('OCR_IMPORT_OK')"
fi
OCR_SITE_PACKAGES="$("$OCR_VENV_ROOT/bin/python" -c 'import site; print(site.getsitepackages()[0])')"

cp -a "$WORK_DIR/dist/." "$FRONTEND_ROOT/"

# Sync runtime source and schema files without touching the production database,
# uploads, or test fixtures. Lifecycle modules are imported by audit_api.py and
# must be released together with it.
find "$WORK_DIR/server" -maxdepth 1 -type f \( -name "*.py" -o -name "*.sql" -o -name "requirements-*.txt" \) \
  -exec cp -f {} "$API_ROOT/" \;
mkdir -p "$API_ROOT/recognition"
cp -a "$WORK_DIR/server/recognition/." "$API_ROOT/recognition/"
for required_file in audit_api.py schema.sql lifecycle.py lifecycle_repository.py migrations.py requirements-ocr.txt recognition_service.py recognition_worker.py; do
  if [[ ! -f "$API_ROOT/$required_file" ]]; then
    echo "Deployed API runtime missing $required_file" >&2
    exit 1
  fi
done
for required_file in recognition/contracts.py recognition/registry.py; do
  if [[ ! -f "$API_ROOT/$required_file" ]]; then
    echo "Deployed API runtime missing $required_file" >&2
    exit 1
  fi
done

mkdir -p "/etc/systemd/system/$SERVICE_NAME.d"
cat > "/etc/systemd/system/$SERVICE_NAME.d/document-ocr.conf" <<EOF
[Service]
Environment="PYTHONPATH=$OCR_SITE_PACKAGES"
EOF

mkdir -p "$API_ROOT/uploads/documents"
mkdir -p /etc/nginx/conf.d
cat > /etc/nginx/conf.d/shenjikanban-upload-size.conf <<'EOF'
client_max_body_size 500m;
EOF

# PDF.js is loaded as an ES module worker. Some OpenCloudOS images do not
# register .mjs in nginx's default MIME map, which makes browsers reject the
# worker and fall back to the slower/incompatible fake-worker path.
if ! grep -Eq '^[[:space:]]*application/javascript[[:space:]]+.*\bmjs;' /etc/nginx/mime.types; then
  sed -i -E 's/^([[:space:]]*application\/javascript[[:space:]]+)js;$/\1js mjs;/' /etc/nginx/mime.types
fi

systemctl daemon-reload
systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"
nginx -t
systemctl reload nginx

python3 - <<'PY'
import json
import time
import urllib.request

checks = [
    "http://127.0.0.1:3008/api/health",
    "http://127.0.0.1:8088/api/health",
]

for url in checks:
    last_error = None
    for _ in range(20):
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                body = response.read().decode("utf-8")
                if response.status != 200:
                    raise RuntimeError(f"{response.status}")
                try:
                    data = json.loads(body)
                except Exception:
                    data = {"raw": body[:120]}
                health = data.get("data", data)
                if not isinstance(health, dict) or health.get("recognitionWorkerAlive") is not True:
                    raise RuntimeError("recognition worker is not alive")
                print(f"HEALTH_OK {url} {data}")
                break
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    else:
        raise SystemExit(f"Health check failed: {url} -> {last_error}")
PY

echo "DEPLOY_OK"
