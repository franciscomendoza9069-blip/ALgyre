#!/bin/bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo 'Ejecuta este archivo con sudo.'; exit 1; fi
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
IP=${1:?Indica la IP pública: sudo bash deploy/install-debian.sh IP_PUBLICA}
python3 - "$IP" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1])
if ip.version!=4 or not ip.is_global: raise SystemExit('Indica una IPv4 pública, no la IP de Tailscale ni la IP de casa.')
PY
apt-get update
apt-get install -y python3-venv apache2 ca-certificates curl
if ! id algyre >/dev/null 2>&1; then useradd --system --home-dir /var/lib/algyre --shell /usr/sbin/nologin algyre; fi
install -d -m 0755 /opt/algyre /opt/algyre/static /opt/algyre/deploy /opt/algyre/algyre_core
install -d -o algyre -g algyre -m 0700 /var/lib/algyre
install -d -m 0700 /var/backups/algyre
# Back up previous code before updating; databases are stored separately and never overwritten.
if [[ -f /opt/algyre/app.py ]]; then
    bash /opt/algyre/deploy/backup.sh
    systemctl stop algyre.service
    tar --exclude='.venv' -czf "/var/backups/algyre/code-$(date -u +%Y%m%dT%H%M%SZ).tar.gz" -C /opt/algyre .
fi
for file in app.py tenancy.py manage.py import_workflow.py schema.sql requirements-lock.txt; do install -m 0644 "$SOURCE/$file" "/opt/algyre/$file"; done
find "$SOURCE/algyre_core" -maxdepth 1 -type f -name '*.py' -exec install -m 0644 '{}' /opt/algyre/algyre_core/ \;
find "$SOURCE/static" -maxdepth 1 -type f -exec install -m 0644 '{}' /opt/algyre/static/ \;
find "$SOURCE/deploy" -maxdepth 1 -type f -exec install -m 0644 '{}' /opt/algyre/deploy/ \;
python3 -m venv /opt/algyre/.venv
/opt/algyre/.venv/bin/python -m pip install -r /opt/algyre/requirements-lock.txt
if [[ ! -f /etc/algyre.env ]]; then
    python3 - "$IP" <<'PY'
import secrets,sys,os
from pathlib import Path
path=Path('/etc/algyre.env')
path.write_text('ALGYRE_MODE=public\nALGYRE_PUBLIC_URL=https://'+sys.argv[1]+'\nALGYRE_DATA_DIR=/var/lib/algyre\nALGYRE_PORT=8766\nALGYRE_SECRET_KEY='+secrets.token_hex(48)+'\n',encoding='utf-8')
os.chmod(path,0o640)
PY
    chown root:algyre /etc/algyre.env
fi
set -a
source /etc/algyre.env
set +a
runuser -u algyre -- /opt/algyre/.venv/bin/python /opt/algyre/manage.py migrate
install -m 0644 /opt/algyre/deploy/algyre.service /etc/systemd/system/algyre.service
install -m 0644 /opt/algyre/deploy/algyre-backup.service /etc/systemd/system/algyre-backup.service
install -m 0644 /opt/algyre/deploy/algyre-backup.timer /etc/systemd/system/algyre-backup.timer
systemctl daemon-reload
systemctl enable --now algyre.service algyre-backup.timer
systemctl restart algyre.service
echo 'ALgyre está instalado como servicio privado. Falta activar HTTPS con publish-ip.sh.'
