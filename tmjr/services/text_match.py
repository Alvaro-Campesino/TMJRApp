"""Detección de duplicados de cadenas (juegos, premisas, …).

Combinación de dos capas:

1. **Normalización** (`normalizar`): lowercase + sin tildes + sin
   puntuación + espacios colapsados. Captura los duplicados accidentales
   (mayúsculas, tildes, espacios extra, signos).

2. **Similitud difusa** (`buscar_similares`) con `rapidfuzz` y el
   scorer `token_sort_ratio` (ordena tokens antes de calcular, así
   "D&D 5e" y "5e D&D" puntúan 100). Umbral por defecto: 80.

Uso típico: antes de crear una entrada nueva, llama a `buscar_similares`
con los candidatos actuales del catálogo. Si devuelve algo, presenta
los matches al usuario para que decida si reusa uno o crea igualmente.
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz, process

SIMILARITY_THRESHOLD = 80


def normalizar(s: str) -> str:
    """Lower-case + sin tildes + sin puntuación + espacios colapsados.

    Idempotente. Pensada para usarse de clave de comparación, NO para
    guardarse en BD reemplazando al nombre original.
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    # Mantenemos & porque es semánticamente relevante ("D&D", "Pen & Paper").
    s = re.sub(r"[^\w\s&]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def buscar_similares(
    candidatos: list[tuple[int, str]],
    nombre: str,
    *,
    score_cutoff: int = SIMILARITY_THRESHOLD,
    limit: int = 5,
) -> list[tuple[int, str, int]]:
    """Devuelve los candidatos suficientemente parecidos a `nombre`.

    Cada tupla de entrada es `(id, nombre_original)`. Salida: lista de
    `(id, nombre_original, score)` ordenada por score desc.

    Match exacto post-normalización siempre devuelve 100. Si el catálogo
    está vacío o no hay candidatos por encima del umbral, devuelve `[]`.
    """
    if not candidatos:
        return []
    key = normalizar(nombre)
    if not key:
        return []
    norms = [normalizar(n) for _, n in candidatos]
    # `process.extract` aplica el scorer sobre cada candidato y filtra
    # por score_cutoff. Devuelve (choice, score, index_in_choices).
    raw = process.extract(
        key,
        norms,
        scorer=fuzz.token_sort_ratio,
        limit=limit,
        score_cutoff=score_cutoff,
    )
    out: list[tuple[int, str, int]] = []
    for _choice, score, idx in raw:
        obj_id, original = candidatos[idx]
        out.append((obj_id, original, int(score)))
    return out
