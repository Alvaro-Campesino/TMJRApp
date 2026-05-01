#!/usr/bin/env bash
# Genera un docker-compose-env.yaml self-contained con todas las variables
# de .env sustituidas, listo para desplegar en QNAP Container Station.
#
# Uso:
#   bash scripts/build-compose-env.sh             # genera + tarball
#   bash scripts/build-compose-env.sh --no-tar    # solo el yaml
#
# Variables de entorno opcionales (con valores QNAP por defecto):
#   QNAP_POSTGRES_PATH=/share/VMTemplates/TMJR/postgresql
#   QNAP_NGINX_CONF=/share/VMTemplates/TMJR/nginx/default.conf
#   QNAP_CERT_PEM=/share/VMTemplates/TMJR/certs/nginx.pem
#   QNAP_CERT_KEY=/share/VMTemplates/TMJR/certs/nginx.key
#
# Salida:
#   docker-compose-env.yaml   ← compose con env vars resueltas + paths QNAP
#   tmjr-deploy.tar.gz        ← yaml + nginx/ + certs/  → sube esto al QNAP
#
# CUIDADO: el yaml generado contiene secretos en plano (TOKEN, etc.).
# El tarball además contiene la clave privada del cert. Ambos gitignorados.
# No los subas a repos públicos.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "✗ No encuentro .env en $(pwd)" >&2
    exit 1
fi

if [[ ! -f certs/nginx.pem || ! -f certs/nginx.key ]]; then
    echo "✗ Falta cert TLS. Ejecuta primero: bash scripts/generate-cert.sh" >&2
    exit 1
fi

NO_TAR=0
for arg in "$@"; do
    case "$arg" in
        --no-tar) NO_TAR=1 ;;
        --no-up) ;;  # legacy, ya no aplicable
        *) echo "Flag desconocida: $arg" >&2; exit 1 ;;
    esac
done

OUTPUT="docker-compose-env.yaml"
TARBALL="tmjr-deploy.tar.gz"
PROFILE="${PROFILE:-public}"
REPO_ROOT_ABS="$(pwd)"

# Rutas en el QNAP donde irán los datos persistentes, config nginx y certs
QNAP_POSTGRES_PATH="${QNAP_POSTGRES_PATH:-/share/VMTemplates/TMJR/postgresql}"
QNAP_NGINX_CONF="${QNAP_NGINX_CONF:-/share/VMTemplates/TMJR/nginx/default.conf}"
QNAP_CERT_PEM="${QNAP_CERT_PEM:-/share/VMTemplates/TMJR/certs/nginx.pem}"
QNAP_CERT_KEY="${QNAP_CERT_KEY:-/share/VMTemplates/TMJR/certs/nginx.key}"

echo "→ Generando $OUTPUT (profile=$PROFILE)"
docker compose --profile "$PROFILE" --env-file .env config > "$OUTPUT"

echo "→ Reescribiendo paths absolutos del repo → relativos"
sed -i "s|${REPO_ROOT_ABS}|.|g" "$OUTPUT"

echo "→ Limpiando para Container Station: quito 'build:' y 'profiles:'"
echo "  + aplicando paths QNAP + anclando volumen postgres"
python3 - <<PY
from pathlib import Path
import re

p = Path("$OUTPUT")
data = p.read_text()

# 1. Quita el bloque build: del servicio app. La imagen ya está en QNAP.
data = re.sub(
    r'^    build:\n(?:      .*\n)+',
    '',
    data,
    flags=re.MULTILINE,
)

# 2. Quita el bloque profiles: ["public"] (no aplicable en Container Station).
data = re.sub(
    r'^    profiles:\n(?:      - .*\n)+',
    '',
    data,
    flags=re.MULTILINE,
)

# 3. Bind del nginx config y certs: paths relativos → rutas absolutas del QNAP
data = data.replace(
    "source: ./nginx/default.conf",
    "source: $QNAP_NGINX_CONF",
)
data = data.replace(
    "source: ./certs/nginx.pem",
    "source: $QNAP_CERT_PEM",
)
data = data.replace(
    "source: ./certs/nginx.key",
    "source: $QNAP_CERT_KEY",
)

# 4. Volumen postgres: añade driver_opts para anclarlo a la ruta del QNAP.
data = re.sub(
    r"(  tmjr_pgdata:\n    name: tmjrapp_tmjr_pgdata)",
    r"""\1
    driver: local
    driver_opts:
      type: none
      o: bind
      device: $QNAP_POSTGRES_PATH""",
    data,
)

p.write_text(data)
PY

echo "✓ $OUTPUT escrito ($(wc -l < "$OUTPUT") líneas)"

if [[ $NO_TAR -eq 1 ]]; then
    echo "→ --no-tar: no genero el tarball."
    exit 0
fi

echo
echo "→ Empaquetando $TARBALL para QNAP Container Station"
tar czf "$TARBALL" "$OUTPUT" nginx/ certs/nginx.pem certs/nginx.key
echo "✓ $TARBALL ($(du -h "$TARBALL" | cut -f1))"
echo
echo "  Para desplegar en QNAP:"
echo "    1. Crea estas rutas en el NAS (vacías):"
echo "         $QNAP_POSTGRES_PATH"
echo "         $(dirname "$QNAP_NGINX_CONF")"
echo "         $(dirname "$QNAP_CERT_PEM")"
echo "    2. Sube $TARBALL al NAS y desempaqueta: tar xzf $TARBALL"
echo "    3. Mueve los ficheros:"
echo "         nginx/default.conf  →  $QNAP_NGINX_CONF"
echo "         certs/nginx.pem     →  $QNAP_CERT_PEM"
echo "         certs/nginx.key     →  $QNAP_CERT_KEY"
echo "    4. Container Station → Crear → Aplicación → importar $OUTPUT"
echo "       (o por SSH: docker compose -f $OUTPUT up -d)"
