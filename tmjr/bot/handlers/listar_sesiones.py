"""Listados de sesiones en el chat privado con el bot.

Dos vistas, ambas renderizan cada sesión con el mismo formato que la
tarjeta publicada en el canal (`render_tarjeta_sesion_html`); cambia solo
el inline keyboard debajo de cada tarjeta.

- `mis_sesiones`: las sesiones del DM logueado. Cada tarjeta lleva un
  único botón ✏️ Editar (callback `edsespick_<id>`, entry_point del
  flujo de edición).
- `sesiones_publicadas`: todas las sesiones abiertas. Cada tarjeta lleva
  los mismos botones que en el canal (apuntarse, borrarse, +1, -1) para
  poder apuntarse sin salir del privado.
"""
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from tmjr.bot.keyboards import tarjeta_sesion, tarjeta_sesion_editar
from tmjr.bot.publicador import (
    render_tarjeta_sesion_dm_html,
    render_tarjeta_sesion_html,
)
from tmjr.db import async_session_maker
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc


async def mis_sesiones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista las sesiones futuras del DM logueado con botón ✏️ Editar."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text(
                "Solo los DMs tienen sesiones propias."
            )
            return
        sesiones = await sesiones_svc.list_sesiones_for_dm(
            session, persona.id_master, only_future=True
        )

    if not sesiones:
        await update.effective_message.reply_text(
            "No tienes sesiones futuras."
        )
        return

    await update.effective_message.reply_text(
        f"<b>Mis sesiones</b> ({len(sesiones)}):",
        parse_mode=ParseMode.HTML,
    )
    for s in sesiones:
        texto = await render_tarjeta_sesion_dm_html(s)
        await update.effective_message.reply_text(
            texto,
            parse_mode=ParseMode.HTML,
            reply_markup=tarjeta_sesion_editar(s.id),
        )


async def sesiones_publicadas(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Lista todas las sesiones abiertas con los botones del canal."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    async with async_session_maker() as session:
        sesiones = await sesiones_svc.listar_sesiones_abiertas(session)

    if not sesiones:
        await update.effective_message.reply_text(
            "No hay sesiones abiertas en este momento."
        )
        return

    await update.effective_message.reply_text(
        f"<b>Sesiones publicadas</b> ({len(sesiones)}):",
        parse_mode=ParseMode.HTML,
    )
    for s in sesiones:
        texto = await render_tarjeta_sesion_html(s)
        await update.effective_message.reply_text(
            texto,
            parse_mode=ParseMode.HTML,
            reply_markup=tarjeta_sesion(s.id),
        )
