#!/bin/bash
# IP certificates require a recent Certbot with IP identifier support.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Ejecuta con sudo.'; exit 1; }
IP=${1:?Indica la IP pública}
python3 - "$IP" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1])
if ip.version!=4 or not ip.is_global: raise SystemExit('La dirección debe ser una IPv4 pública.')
PY
[[ -f /etc/algyre.env ]] || { echo 'Primero ejecuta install-debian.sh'; exit 1; }
NAME=000-000-algyre-ip
CONF=/etc/apache2/sites-available/$NAME.conf
install -d -m 0755 /var/www/algyre-acme/.well-known/acme-challenge
BACKUP="/var/backups/algyre/apache-$(date -u +%Y%m%dT%H%M%SZ)"
install -d -m 0700 "$BACKUP"
cp -a /etc/apache2/sites-available /etc/apache2/sites-enabled "$BACKUP/"
if [[ -f "$CONF" ]]; then cp "$CONF" "$BACKUP/previous.conf"; fi
rollback() {
  if [[ -f "$BACKUP/previous.conf" ]]; then cp "$BACKUP/previous.conf" "$CONF";
  else a2dissite "$NAME" >/dev/null 2>&1 || true; rm -f -- "$CONF"; fi
  apache2ctl configtest && systemctl reload apache2 || true
}
trap rollback ERR
a2enmod proxy proxy_http headers ssl rewrite >/dev/null
cat > "$CONF" <<EOF
<VirtualHost *:80>
    ServerName $IP
    DocumentRoot /var/www/algyre-acme
    <Directory /var/www/algyre-acme>
        Require all granted
        Options -Indexes
    </Directory>
    RewriteEngine On
    RewriteCond %{REQUEST_URI} !^/.well-known/acme-challenge/
    RewriteRule ^ - [R=503,L]
    ErrorLog \${APACHE_LOG_DIR}/algyre-error.log
    CustomLog \${APACHE_LOG_DIR}/algyre-access.log combined
</VirtualHost>
EOF
a2ensite "$NAME" >/dev/null
apache2ctl configtest
systemctl reload apache2
# Separate venv leaves the existing certificates/renewal service untouched.
python3 -m venv /opt/algyre-certbot
/opt/algyre-certbot/bin/python -m pip install --upgrade 'certbot>=5.4'
install -d -m 0700 /etc/algyre-acme /var/lib/algyre-acme /var/log/algyre-acme
ACME=(/opt/algyre-certbot/bin/certbot certonly --non-interactive --agree-tos --register-unsafely-without-email
      --config-dir /etc/algyre-acme --work-dir /var/lib/algyre-acme --logs-dir /var/log/algyre-acme
      --preferred-profile shortlived --webroot --webroot-path /var/www/algyre-acme --ip-address "$IP" --cert-name algyre-ip)
if [[ ! -f /etc/algyre-acme/live/algyre-ip/fullchain.pem ]]; then
    "${ACME[@]}" --staging --dry-run
    "${ACME[@]}"
fi
cat > "$CONF" <<EOF
<VirtualHost *:80>
    ServerName $IP
    DocumentRoot /var/www/algyre-acme
    <Directory /var/www/algyre-acme>
        Require all granted
        Options -Indexes
    </Directory>
    RewriteEngine On
    RewriteCond %{REQUEST_URI} !^/.well-known/acme-challenge/
    RewriteRule ^ https://$IP%{REQUEST_URI} [R=308,L,NE]
    ErrorLog \${APACHE_LOG_DIR}/algyre-error.log
    CustomLog \${APACHE_LOG_DIR}/algyre-access.log combined
</VirtualHost>
<VirtualHost *:443>
    ServerName $IP
    SSLEngine on
    SSLCertificateFile /etc/algyre-acme/live/algyre-ip/fullchain.pem
    SSLCertificateKeyFile /etc/algyre-acme/live/algyre-ip/privkey.pem
    SSLProtocol -all +TLSv1.2 +TLSv1.3
    ProxyRequests Off
    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-For expr=%{REMOTE_ADDR}
    ProxyPass / http://127.0.0.1:8766/ connectiontimeout=5 timeout=120
    ProxyPassReverse / http://127.0.0.1:8766/
    Header always set Strict-Transport-Security "max-age=86400"
    LimitRequestBody 25165824
    ErrorLog \${APACHE_LOG_DIR}/algyre-error.log
    CustomLog \${APACHE_LOG_DIR}/algyre-access.log combined
</VirtualHost>
EOF
apache2ctl configtest
systemctl reload apache2
install -m 0644 /opt/algyre/deploy/algyre-cert-renew.service /etc/systemd/system/algyre-cert-renew.service
install -m 0644 /opt/algyre/deploy/algyre-cert-renew.timer /etc/systemd/system/algyre-cert-renew.timer
install -m 0644 /opt/algyre/deploy/algyre-health.service /etc/systemd/system/algyre-health.service
install -m 0644 /opt/algyre/deploy/algyre-health.timer /etc/systemd/system/algyre-health.timer
systemctl daemon-reload
systemctl enable --now algyre-cert-renew.timer algyre-health.timer
trap - ERR
echo "ALgyre: https://$IP"
echo "Copia de la configuración anterior: $BACKUP"
