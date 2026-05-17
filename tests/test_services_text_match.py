"""Tests de `text_match.normalizar` y `buscar_similares`."""
from __future__ import annotations

from tmjr.services.text_match import (
    SIMILARITY_THRESHOLD,
    buscar_similares,
    normalizar,
)


def test_normalizar_quita_tildes_y_minuscula():
    assert normalizar("Maldición") == "maldicion"
    assert normalizar("D&D 5E") == "d&d 5e"


def test_normalizar_colapsa_espacios_y_quita_puntuacion():
    assert normalizar("  La  Maldición   de  Strahd!! ") == "la maldicion de strahd"


def test_normalizar_idempotente():
    s = "La Maldición de Strahd"
    assert normalizar(s) == normalizar(normalizar(s))


def test_buscar_similares_match_exacto_tras_normalizar():
    candidatos = [(1, "La Maldición de Strahd"), (2, "Otra cosa")]
    res = buscar_similares(candidatos, "la maldicion de strahd")
    assert len(res) >= 1
    assert res[0][0] == 1
    assert res[0][2] == 100


def test_buscar_similares_typo_pequeno():
    """Un cambio de letra debería superar el umbral por defecto (80)."""
    candidatos = [(1, "Vampire la Mascarada")]
    res = buscar_similares(candidatos, "Vampyre la Mascarada")
    assert len(res) == 1
    assert res[0][0] == 1
    assert res[0][2] >= SIMILARITY_THRESHOLD


def test_buscar_similares_orden_tokens_invertido():
    """`token_sort_ratio` ordena tokens, así que 'D&D 5e' == '5e D&D'."""
    candidatos = [(1, "D&D 5e")]
    res = buscar_similares(candidatos, "5e D&D")
    assert len(res) == 1
    assert res[0][2] == 100


def test_buscar_similares_no_devuelve_si_score_bajo():
    candidatos = [(1, "Vampiro la Mascarada")]
    res = buscar_similares(candidatos, "Cthulhu")
    assert res == []


def test_buscar_similares_catalogo_vacio():
    assert buscar_similares([], "lo que sea") == []


def test_buscar_similares_input_vacio():
    assert buscar_similares([(1, "Algo")], "") == []
    assert buscar_similares([(1, "Algo")], "   ") == []


def test_buscar_similares_orden_por_score_desc_y_limit():
    candidatos = [
        (1, "Vampire la Mascarada"),
        (2, "Vampyre la Mascarada"),
        (3, "Vampire la Bohème"),
    ]
    res = buscar_similares(candidatos, "Vampire la Mascarada", limit=2)
    assert len(res) <= 2
    # El primero debe ser match exacto (id=1).
    assert res[0][0] == 1
    # Y ningún score posterior es mayor que el primero.
    scores = [s for _, _, s in res]
    assert scores == sorted(scores, reverse=True)
