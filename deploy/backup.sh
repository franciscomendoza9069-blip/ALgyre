#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || exit 1
install -d -m 0700 /var/backups/algyre
NAME="/var/backups/algyre/data-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
systemctl stop algyre
trap 'systemctl start algyre' EXIT
# A brief offline snapshot keeps the accounts database and all company ledgers consistent.
umask 077
tar -czf "$NAME" -C /var/lib algyre
systemctl start algyre
trap - EXIT
# Only our own dated data snapshots in this explicitly named backup directory expire.
find /var/backups/algyre -maxdepth 1 -type f -name 'data-????????T??????Z.tar.gz' -mtime +13 -delete
echo "Copia creada: $NAME"
