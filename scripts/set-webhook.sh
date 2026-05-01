#!/usr/bin/env bash
# Registra el webhook en Telegram subiendo el cert self-signed.
# Lee variables de .env del repo. Requiere certs/nginx.pem.
#
# Uso:
#   bash scripts/set-webhook.sh             # registra
#   bash scripts/set-webhook.sh --info      # muestra el estado actual
#   bash scripts/set-webhook.sh --delete    # quita el webhook

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "✗ Falta .env" >&2
    exit 1
fi

# Carga .env sin parseo raro
set -a
# shellcheck disable=SC1091
source .env
set +a

: "${TELEGRAM_TOKEN:?TELEGRAM_TOKEN no está en .env}"

API="https://api.telegram.org/bot${TELEGRAM_TOKEN}"

case "${1:-set}" in
    --info|info)
        echo "→ getWebhookInfo"
        curl -s "${API}/getWebhookInfo" | python3 -m json.tool
        ;;

    --delete|delete)
        echo "→ deleteWebhook"
        curl -s "${API}/deleteWebhook" | python3 -m json.tool
        ;;

    set|"")
        : "${TELEGRAM_WEBHOOK_URL:?TELEGRAM_WEBHOOK_URL no está en .env}"
        if [[ ! -f certs/nginx.pem ]]; then
            echo "✗ Falta certs/nginx.pem (corre scripts/generate-cert.sh)" >&2
            exit 1
        fi

        echo "→ setWebhook url=$TELEGRAM_WEBHOOK_URL  cert=certs/nginx.pem"
        curl -s \
            -F "url=${TELEGRAM_WEBHOOK_URL}" \
            -F "certificate=@certs/nginx.pem" \
            ${TELEGRAM_WEBHOOK_SECRET:+-F "secret_token=${TELEGRAM_WEBHOOK_SECRET}"} \
            "${API}/setWebhook" | python3 -m json.tool
        echo
        echo "→ Estado tras el registro:"
        curl -s "${API}/getWebhookInfo" | python3 -m json.tool
        ;;

    *)
        echo "Uso: $0 [set|--info|--delete]" >&2
        exit 1
        ;;
esac
