"""Handlers de suscripción de Persona a Premisa.

Callbacks:
  - `prem_suscr_<premisa_id>`        → toggle desde el listado de premisas.
  - `prem_desuscr_<premisa_id>`      → borrarse desde "Mis suscripciones".
  - `caja_persona_suscripciones`     → ver mis suscripciones.
  - `caja_persona_ver_dm_suscriptores` → ver premisas del DM con suscriptores.

Notificación al DM: tras `subscribe()`, el handler envía DM a los DMs
distintos que han "usado" la premisa (catálogo dm_premisas ∪ sesiones).
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from tmjr.bot.keyboards import (
    boton_suscripcion_premisa,
    lista_mis_suscripciones,
)
from tmjr.db import async_session_maker
from tmjr.db.models import Persona
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc
from tmjr.services import suscripciones as sub_svc

logger = logging.getLogger(__name__)


async def _persona_o_redirige(update: Update) -> Persona | None:
    """Devuelve la Persona registrada o avisa de que use /start."""
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(
            session, update.effective_user.id
        )
    if persona is None:
        await update.effective_message.reply_text(
            "Primero usa /start para registrarte."
        )
    return persona


async def toggle_suscripcion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Suscribirse / desuscribirse a una premisa desde el listado.

    Tras hacer toggle, edita el `reply_markup` del mensaje para reflejar
    el nuevo estado y, si era una suscripción nueva, notifica por DM a
    los DMs que han usado la premisa.
    """
    query = update.callback_query
    await query.answer()
    premisa_id = int(query.data.removeprefix("prem_suscr_"))

    persona = await _persona_o_redirige(update)
    if persona is None:
        return

    async with async_session_maker() as session:
        existing = await sub_svc.is_subscribed(session, persona.id, premisa_id)
        if existing is not None:
            await sub_svc.unsubscribe(
                session, persona_id=persona.id, premisa_id=premisa_id
            )
            suscrito_ahora = False
            await query.answer("🔕 Desuscrito", show_alert=False)
        else:
            await sub_svc.subscribe(
                session, persona_id=persona.id, premisa_id=premisa_id
            )
            suscrito_ahora = True
            dm_ids = await sub_svc.dms_que_han_usado_premisa(
                session, premisa_id
            )
            premisa = await premisas_svc.get_premisa(session, premisa_id)
            personas_dm: list[Persona] = []
            for dm_id in dm_ids:
                p = await personas_svc.get_persona_by_dm(session, dm_id)
                if p is not None and p.id != persona.id:
                    personas_dm.append(p)

    try:
        await query.edit_message_reply_markup(
            reply_markup=boton_suscripcion_premisa(premisa_id, suscrito_ahora)
        )
    except TelegramError as exc:
        logger.warning(
            "No pude actualizar el botón de suscripción a premisa %s: %s",
            premisa_id, exc,
        )

    if suscrito_ahora and premisa is not None:
        for dm_persona in personas_dm:
            try:
                await context.bot.send_message(
                    chat_id=dm_persona.telegram_id,
                    text=(
                        f"🔔 <b>{persona.nombre}</b> se ha suscrito a tu premisa "
                        f"<b>{premisa.nombre}</b>.\n\n"
                        f"Cuando convoques una sesión nueva con esta premisa "
                        f"(o la primera de una campaña), se le notificará."
                    ),
                    parse_mode="HTML",
                )
            except TelegramError as exc:
                logger.warning(
                    "No pude notificar al DM %s (telegram_id=%s) de la nueva "
                    "suscripción a premisa %s: %s",
                    dm_persona.id, dm_persona.telegram_id, premisa_id, exc,
                )


async def mis_suscripciones(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Lista las premisas a las que la persona está suscrita.

    Cada entrada lleva un botón '🚪 Borrarme — <nombre>' para desuscribirse.
    """
    query = update.callback_query
    if query is not None:
        await query.answer()

    persona = await _persona_o_redirige(update)
    if persona is None:
        return

    async with async_session_maker() as session:
        premisas = await sub_svc.list_by_persona(session, persona.id)

    if not premisas:
        await update.effective_message.reply_text(
            "No estás suscrita a ninguna premisa. Ábrelas en la caja "
            "📜 Premisa → Listar y pulsa el botón 🔔 Suscribirse."
        )
        return

    lineas = ["<b>🔔 Mis suscripciones</b>"]
    for p in premisas:
        lineas.append(f"• {p.nombre}")
    await update.effective_message.reply_text(
        "\n".join(lineas),
        parse_mode="HTML",
        reply_markup=lista_mis_suscripciones(
            [(p.id, p.nombre) for p in premisas]
        ),
    )


async def desuscribirme(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Desuscribirse desde el mensaje de 'Mis suscripciones'.

    Tras borrar, edita el mismo mensaje refrescando la lista. Si ya no
    queda ninguna, lo sustituye por un texto plano.
    """
    query = update.callback_query
    await query.answer()
    premisa_id = int(query.data.removeprefix("prem_desuscr_"))

    persona = await _persona_o_redirige(update)
    if persona is None:
        return

    async with async_session_maker() as session:
        await sub_svc.unsubscribe(
            session, persona_id=persona.id, premisa_id=premisa_id
        )
        premisas = await sub_svc.list_by_persona(session, persona.id)

    if not premisas:
        await query.edit_message_text(
            "✅ Listo. Ya no estás suscrita a ninguna premisa."
        )
        return

    lineas = ["<b>🔔 Mis suscripciones</b>"]
    for p in premisas:
        lineas.append(f"• {p.nombre}")
    await query.edit_message_text(
        "\n".join(lineas),
        parse_mode="HTML",
        reply_markup=lista_mis_suscripciones(
            [(p.id, p.nombre) for p in premisas]
        ),
    )


async def dm_suscriptores(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Muestra al DM qué premisas suyas tienen suscriptores y cuántos."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    persona = await _persona_o_redirige(update)
    if persona is None:
        return
    if persona.id_master is None:
        await update.effective_message.reply_text(
            "Aún no tienes perfil de DM."
        )
        return

    async with async_session_maker() as session:
        premisas = await sub_svc.premisas_usadas_por_dm_con_suscriptores(
            session, persona.id_master
        )

    if not premisas:
        await update.effective_message.reply_text(
            "Ninguna de tus premisas tiene suscriptores todavía."
        )
        return

    lineas = ["<b>👥 Premisas con suscriptores</b>"]
    for premisa, count in premisas:
        lineas.append(
            f"• <b>{premisa.nombre}</b> — {count} "
            f"{'suscriptor' if count == 1 else 'suscriptores'}"
        )
    await update.effective_message.reply_text(
        "\n".join(lineas), parse_mode="HTML"
    )
