"""Caja Sesión → Listar / comando /listar_sesiones."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.bot.keyboards import tarjeta_sesion
from tmjr.db import async_session_maker
from tmjr.services import sesiones as sesiones_svc


async def listar_sesiones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        f"*Sesiones abiertas* ({len(sesiones)}):", parse_mode="Markdown"
    )
    for s in sesiones:
        titulo = s.nombre or f"Sesión #{s.id}"
        texto = (
            f"*{titulo}*\n"
            f"📅 {s.fecha.isoformat()}\n"
            f"🪑 {s.plazas_totales} plazas"
        )
        await update.effective_message.reply_text(
            texto,
            parse_mode="Markdown",
            reply_markup=tarjeta_sesion(s.id),
        )
