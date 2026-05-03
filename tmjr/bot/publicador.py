"""Publica/actualiza la tarjeta de una sesión en el canal de Telegram."""
from __future__ import annotations

from telegram import Bot
from telegram.constants import ParseMode

from tmjr.config import get_settings
from tmjr.db.models import Premisa, Sesion

from .keyboards import tarjeta_sesion

def _getItembyIndex(lista, index):
    try:
        return lista[index-1]
    except IndexError:
        return ""

def _formatear(sesion: Sesion, jugadores: [str | None], premisa: Premisa | None = None) -> str:
    # Nombre: el de la sesion tiene prioridad; si no, el de la premisa;
    # si tampoco, "Sesión #N".
    # TODO el nombre de la premisa se toma del nombre de la sesión, no se da opción a configurarlo.
    titulo = sesion.nombre or (premisa.nombre if premisa else None) or f"Sesión #{sesion.id}"
    lines = [f"*{titulo}*"]

    # Descripción: la específica de esta sesión tiene prioridad; si no, la de
    # la premisa. Si ninguna hay, no se imprime línea.
    # Lo que se genera aquí es el mensaje que se postea en telegram
    descripcion = sesion.descripcion or (premisa.descripcion if premisa else None)
    if descripcion:
        lines.append(f"*Descripcion*: _{descripcion}_")


    lines.append("")
    lines.append(f"📅 {sesion.fecha.isoformat()}")
    lines.append(
        f"🪑 {sesion.plazas_totales} plazas "
        # TODO revisar las plazas sin reserva
        #f"({sesion.plazas_sin_reserva} sin reserva)"
    )
    printed = 0
    # TODO añadir aquí los jugadores desde el servicio APY.
    lines.append(
        f"*Jugadores apuntados:*"

    )
    while sesion.plazas_totales - printed >0:
        printed += 1
        nombreJugadorApuntado = _getItembyIndex(jugadores, printed)
        lines.append(f"{printed}. {nombreJugadorApuntado}")

    return "\n".join(lines)


async def publicar_sesion(
    bot: Bot,
    sesion: Sesion,
    jugadores:[ str | None] ,
    *,
    premisa: Premisa | None = None,
) -> tuple[str, int | None, int]:
    """Publica la tarjeta. Devuelve (chat_id, thread_id, message_id)."""
    s = get_settings()
    if not s.telegram_chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID no configurado")

    if not sesion.telegram_message_id:

        msg = await bot.send_message(
            chat_id=s.telegram_chat_id,
            message_thread_id=s.telegram_thread_id,
            text=_formatear(sesion, jugadores, premisa ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=tarjeta_sesion(sesion.id),
        )
    else:
        msg = await bot.edit_message_text(
            chat_id=s.telegram_chat_id,
            message_id=sesion.telegram_message_id,
            text =_formatear(sesion, jugadores, premisa),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=tarjeta_sesion(sesion.id),
        )
        print(msg)
    return s.telegram_chat_id, s.telegram_thread_id, msg.message_id


