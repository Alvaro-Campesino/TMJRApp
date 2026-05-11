"""Caja Premisa → Listar catálogo / comando /listar_premisas."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.bot.object_links import build_object_link
from tmjr.db import async_session_maker
from tmjr.db.models import Juego
from tmjr.services import premisas as premisas_svc


async def listar_premisas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el catálogo global de premisas con nombre, descripción y juego."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    async with async_session_maker() as session:
        premisas = await premisas_svc.list_all_premisas(session)
        # Resolvemos los juegos en una única pasada para no hacer N+1.
        ids_juego = {p.id_juego for p in premisas if p.id_juego is not None}
        juegos_por_id: dict[int, str] = {}
        for jid in ids_juego:
            juego = await session.get(Juego, jid)
            if juego is not None:
                juegos_por_id[jid] = juego.nombre

    if not premisas:
        await update.effective_message.reply_text(
            "Aún no hay premisas. Crea una desde la caja 📜 Premisa → Crear."
        )
        return

    lines = [f"<b>Catálogo de premisas</b> ({len(premisas)}):"]
    for p in premisas:
        juego_nombre = juegos_por_id.get(p.id_juego) if p.id_juego else None
        cabecera = f"• {build_object_link('premisa', p.id, p.nombre)}"
        if juego_nombre and p.id_juego is not None:
            cabecera += f" — {build_object_link('juego', p.id_juego, juego_nombre)}"
        lines.append(cabecera)

    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode="HTML"
    )
