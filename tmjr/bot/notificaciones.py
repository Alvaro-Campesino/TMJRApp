"""Notificaciones DM al cruzar el umbral mínimo de jugadores.

Lo invocan los handlers que cambian la ocupación de una sesión:
`unirse.py`, `desapuntarse.py`, `invitados.py` (+1 / -1). Cada handler
mide la ocupación antes y después de su operación y llama a este
helper. Si hay cruce (sube/baja del mínimo), enviamos DM al DM.

Best-effort: cualquier fallo de Telegram se loguea y se sigue.
"""
from __future__ import annotations

import logging

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from tmjr.bot.object_links import build_object_link
from tmjr.db.models import Sesion
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc

logger = logging.getLogger(__name__)


async def notificar_cruce_minimo_si_aplica(
    bot: Bot,
    sesion: Sesion,
    *,
    ocupadas_antes: int,
    ocupadas_despues: int,
) -> None:
    """Si la ocupación ha cruzado el umbral mínimo de la sesión, DM al DM.

    Reglas en `sesiones.cruce_minimo`. Sube → ✅. Baja → ⚠️. Si no
    aplica (mínimo 0 o sin cruce), no hace nada.
    """
    direccion = sesiones_svc.cruce_minimo(
        ocupadas_antes, ocupadas_despues, sesion.plazas_minimas
    )
    if direccion is None:
        return

    from tmjr.db import async_session_maker

    async with async_session_maker() as session:
        dm_persona = await personas_svc.get_persona_by_dm(session, sesion.id_dm)
    if dm_persona is None:
        return

    titulo = sesion.nombre or f"Sesión #{sesion.id}"
    enlace = build_object_link("sesion", sesion.id, titulo)
    if direccion == "arriba":
        texto = (
            f"✅ Tu sesión {enlace} ha alcanzado el mínimo de jugadores "
            f"(<b>{ocupadas_despues}/{sesion.plazas_minimas}</b>)."
        )
    else:  # "abajo"
        texto = (
            f"⚠️ Tu sesión {enlace} ha bajado del mínimo de jugadores "
            f"(<b>{ocupadas_despues}/{sesion.plazas_minimas}</b>)."
        )

    try:
        await bot.send_message(
            chat_id=dm_persona.telegram_id,
            text=texto,
            parse_mode=ParseMode.HTML,
        )
    except TelegramError as exc:
        logger.warning(
            "No pude notificar al DM (persona %s, telegram_id=%s) del cruce "
            "de mínimo de la sesión %s: %s",
            dm_persona.id, dm_persona.telegram_id, sesion.id, exc,
        )
