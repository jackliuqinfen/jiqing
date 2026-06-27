#!/usr/bin/env bash
set -euo pipefail

APP_ROOT=/www/wwwroot/shenjikanban
API_ROOT=/opt/shenjikanban/server
DB_DIR=/var/lib/shenjikanban
ENV_DIR=/etc/jiqing-engineering
ENV_FILE=${ENV_DIR}/audit-kanban.env
BACKUP_DIR=/var/backups/shenjikanban
STAMP=$(date +%Y%m%d%H%M%S)
RELEASE_DIR=/tmp/shenjikanban-release-current

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
python3 - <<'PY'
import zipfile
zipfile.ZipFile('/tmp/shenjikanban-release.zip').extractall('/tmp/shenjikanban-release-current')
PY

if [ -d "$APP_ROOT" ]; then
  cp -a "$APP_ROOT" "${APP_ROOT}.bak.${STAMP}"
fi

mkdir -p "$APP_ROOT" "$API_ROOT" "$DB_DIR" "$ENV_DIR" "$BACKUP_DIR"
chmod 700 "$ENV_DIR"

if [ -f "$DB_DIR/audit-kanban.sqlite3" ]; then
  cp -a "$DB_DIR/audit-kanban.sqlite3" "$BACKUP_DIR/audit-kanban.${STAMP}.sqlite3"
fi

write_env_line() {
  local key="$1"
  local value="$2"
  python3 - "$key" "$value" <<'PY'
import shlex
import sys
print(f"{sys.argv[1]}={shlex.quote(sys.argv[2])}")
PY
}

if [ ! -f "$ENV_FILE" ]; then
  SESSION_SECRET=$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)
  {
    write_env_line SESSION_SECRET "$SESSION_SECRET"
    write_env_line ADMIN_INIT_USERNAME "${ADMIN_INIT_USERNAME:-admin}"
    if [ -n "${ADMIN_INIT_PASSWORD:-}" ]; then
      write_env_line ADMIN_INIT_PASSWORD "$ADMIN_INIT_PASSWORD"
    fi
    write_env_line ADMIN_INIT_DISPLAY_NAME "${ADMIN_INIT_DISPLAY_NAME:-系统管理员}"
  } >"$ENV_FILE"
  chmod 600 "$ENV_FILE"
elif [ -n "${ADMIN_INIT_PASSWORD:-}" ] && ! grep -q '^ADMIN_INIT_PASSWORD=' "$ENV_FILE"; then
  write_env_line ADMIN_INIT_PASSWORD "$ADMIN_INIT_PASSWORD" >>"$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

find "$APP_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp -a "$RELEASE_DIR/dist/." "$APP_ROOT/"
cp -a "$RELEASE_DIR/server/." "$API_ROOT/"

cat >/etc/systemd/system/audit-kanban.service <<'EOF'
[Unit]
Description=Audit Kanban SQLite API
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/shenjikanban/server
Environment=AUDIT_DB_PATH=/var/lib/shenjikanban/audit-kanban.sqlite3
Environment=AUDIT_API_HOST=127.0.0.1
Environment=AUDIT_API_PORT=3008
EnvironmentFile=-/etc/jiqing-engineering/audit-kanban.env
ExecStart=/usr/bin/python3 /opt/shenjikanban/server/audit_api.py --host 127.0.0.1 --port 3008
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now audit-kanban
systemctl restart audit-kanban
sleep 1

cat >/etc/nginx/conf.d/shenjikanban.conf <<'EOF'
server {
    listen 8088;
    server_name _;
    root /www/wwwroot/shenjikanban;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:3008/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /assets/ {
        try_files $uri =404;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF

nginx -t
systemctl reload nginx

systemctl status audit-kanban --no-pager -l | sed -n '1,14p'
ss -lntp | grep -E ':8088|:3008' || true
curl -fsS http://127.0.0.1:3008/api/health
printf '\n'
curl -fsS http://127.0.0.1:8088/api/audit/dashboard/summary
printf '\nDEPLOY_OK\n'
