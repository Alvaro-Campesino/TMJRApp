#!/usr/bin/env bash
# Genera un certificado TLS self-signed para que nginx termine HTTPS en el QNAP.
#
# Uso:
#   bash scripts/generate-cert.sh                         # CN por defecto: datacerberus.myqnapcloud.com
#   CERT_CN=otro.dominio.com bash scripts/generate-cert.sh
#
# Salida:
#   certs/nginx.pem  (público, para nginx Y para subir a Telegram)
#   certs/nginx.key  (privado, solo nginx, NUNCA se sube a Telegram)

set -euo pipefail

cd "$(dirname "$0")/.."

CN="${CERT_CN:-datacerberus.myqnapcloud.com}"
DAYS="${CERT_DAYS:-365}"
DIR="certs"

mkdir -p "$DIR"

if [[ -f "$DIR/nginx.pem" && -f "$DIR/nginx.key" ]]; then
    echo "⚠ Ya existen certs/nginx.pem y certs/nginx.key."
    read -rp "  ¿Sobrescribir? [y/N] " ans
    [[ "$ans" != "y" && "$ans" != "Y" ]] && { echo "Abort."; exit 0; }
fi

echo "→ Generando self-signed para CN=$CN, válido $DAYS días"
openssl req -newkey rsa:2048 -sha256 -nodes \
    -keyout "$DIR/nginx.key" \
    -x509 -days "$DAYS" \
    -out "$DIR/nginx.pem" \
    -subj "/CN=$CN" \
    -addext "subjectAltName=DNS:$CN"

chmod 600 "$DIR/nginx.key"
chmod 644 "$DIR/nginx.pem"

echo
echo "✓ Certificado generado"
echo "   $DIR/nginx.pem  (público)  — se monta en nginx y se sube a Telegram"
echo "   $DIR/nginx.key  (privado)  — solo nginx; NO compartir"
echo
echo "  Verificación:"
openssl x509 -in "$DIR/nginx.pem" -noout -subject -issuer -dates
