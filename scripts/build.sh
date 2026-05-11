#!/usr/bin/env bash
# Construye la imagen `tmjrapp` con el tag de VERSION + `latest`.
#
# Uso:
#   bash scripts/build.sh
#
# Lee el tag del fichero VERSION en la raíz del repo. Pasa el tag como
# build-arg para que el LABEL OCI y ENV TMJR_VERSION queden correctos
# dentro de la imagen.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f VERSION ]]; then
    echo "✗ No encuentro el fichero VERSION en la raíz." >&2
    exit 1
fi

VERSION="$(tr -d '[:space:]' < VERSION)"
if [[ -z "$VERSION" ]]; then
    echo "✗ VERSION está vacío." >&2
    exit 1
fi

echo "→ Construyendo tmjrapp:${VERSION} (y :latest)"
docker build \
    --build-arg "VERSION=${VERSION}" \
    -t "tmjrapp:${VERSION}" \
    -t "tmjrapp:latest" \
    .

echo "✓ Imagen tmjrapp:${VERSION} lista."
