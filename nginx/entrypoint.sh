#!/bin/sh
set -e

CERT_DIR=/etc/nginx/certs

if [ ! -f "${CERT_DIR}/server.crt" ]; then
    mkdir -p "${CERT_DIR}"
    echo "[openclaw] Generating self-signed TLS cert for IP: ${LAN_IP:-127.0.0.1}"
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "${CERT_DIR}/server.key" \
        -out    "${CERT_DIR}/server.crt" \
        -subj   "/CN=openclaw.local/O=Openclaw" \
        -addext "subjectAltName=IP:${LAN_IP:-127.0.0.1},DNS:openclaw.local"
    chmod 600 "${CERT_DIR}/server.key"
    echo "[openclaw] Certificate written to ${CERT_DIR}"
fi

exec nginx -g 'daemon off;'
