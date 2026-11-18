#!/bin/bash
set -euo pipefail
URL=${ALGYRE_PUBLIC_URL:?}
IP=${URL#https://}
# Validate the real HTTPS certificate and Apache-to-ALgyre path without relying on NAT loopback.
curl --fail --silent --show-error --retry 5 --retry-all-errors --retry-delay 2 --max-time 15 --connect-to "$IP:443:127.0.0.1:443" "$URL/api/health"
