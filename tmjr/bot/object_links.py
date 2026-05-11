"""Deep links genéricos a objetos de dominio.

Construye enlaces `https://t.me/<bot>?start=obj_<kind>_<id>` que, al
pinchar, abren un chat privado con el bot y disparan `/start
obj_<kind>_<id>`. El handler de /start parsea el payload, consulta el
formatter registrado para `kind` y devuelve la información del objeto.

Los enlaces se rendererizan como HTML (`<a href=...>label</a>`) porque
el parser Markdown legacy de Telegram tiene problemas con URLs que
contienen guiones bajos (interpreta `_..._` como cursiva incluso dentro
de la URL, rompiendo el enlace).

Uso:
    register_formatter("premisa", _format_premisa)   # al importar
    set_bot_username("MiBot")                        # al arrancar
    msg = build_object_link("premisa", 42, "Strahd") # en un mensaje HTML
    info = await format_object(session, "premisa", 42)  # en /start
"""
from __future__ import annotations

import html
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

# Async formatter: recibe sesión y id, devuelve Markdown o None si no existe.
Formatter = Callable[[AsyncSession, int], Awaitable[str | None]]

_FORMATTERS: dict[str, Formatter] = {}
_BOT_USERNAME: str | None = None


def register_formatter(kind: str, fn: Formatter) -> None:
    """Registra un formatter para un tipo de objeto."""
    _FORMATTERS[kind] = fn


def set_bot_username(username: str | None) -> None:
    """Cachea el username del bot. Llamar una vez al arrancar."""
    global _BOT_USERNAME
    _BOT_USERNAME = username


def get_bot_username() -> str | None:
    """Devuelve el username cacheado, o None si aún no se ha set-eado."""
    return _BOT_USERNAME


def build_object_link(kind: str, obj_id: int, label: str) -> str:
    """Devuelve un enlace HTML al objeto: `<a href="URL">label</a>`.

    El label se escapa con `html.escape` para evitar que un `<` o `&` en
    el nombre rompa el parser de Telegram.

    Si el username del bot no está aún cacheado (p.ej. tests sin
    Telegram), devuelve solo el label escapado sin enlace.
    """
    safe_label = html.escape(label)
    if _BOT_USERNAME is None:
        return safe_label
    payload = f"obj_{kind}_{obj_id}"
    url = f"https://t.me/{_BOT_USERNAME}?start={payload}"
    return f'<a href="{url}">{safe_label}</a>'


def parse_object_payload(payload: str) -> tuple[str, int] | None:
    """Parsea `obj_<kind>_<id>` → (kind, id), o None si no encaja.

    `kind` puede contener guiones bajos (p.ej. `obj_dm_juego_3`); el id
    es siempre el último segmento numérico.
    """
    if not payload.startswith("obj_"):
        return None
    parts = payload.split("_")
    if len(parts) < 3:
        return None
    try:
        obj_id = int(parts[-1])
    except ValueError:
        return None
    kind = "_".join(parts[1:-1])
    if not kind:
        return None
    return kind, obj_id


async def format_object(
    session: AsyncSession, kind: str, obj_id: int
) -> str | None:
    """Ejecuta el formatter registrado para `kind`.

    Devuelve None si no hay formatter registrado o si el objeto no existe.
    """
    fn = _FORMATTERS.get(kind)
    if fn is None:
        return None
    return await fn(session, obj_id)
