"""Versión de TMJRApp.

Fuente de verdad: fichero `VERSION` en la raíz del repo. Si no está
disponible (p.ej. tests sin checkout completo), se usa el fallback
'dev'. La imagen Docker copia el fichero a `/app/VERSION`.
"""
from __future__ import annotations

from pathlib import Path


def _read_version() -> str:
    """Lee la versión del fichero VERSION; devuelve 'dev' si no se encuentra."""
    # __file__ = .../tmjr/version.py → repo root = parent.parent
    candidates = [
        Path(__file__).resolve().parent.parent / "VERSION",
        Path("/app/VERSION"),  # dentro del contenedor
    ]
    for c in candidates:
        if c.is_file():
            return c.read_text(encoding="utf-8").strip() or "dev"
    return "dev"


__version__ = _read_version()
