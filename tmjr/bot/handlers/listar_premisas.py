"""Caja Premisa → Listar catálogo / comando /listar_premisas.

Renderiza UN mensaje por premisa con su botón inline de suscripción
(🔔 Suscribirse / 🔕 Suscrito ✓), para que la persona pueda darse de
alta/baja en cada una sin salir del listado.
"""
from __future__ import annotations

from html import escape

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.bot.keyboards import boton_suscripcion_premisa
from tmjr.bot.object_links import build_object_link
from tmjr.db import async_session_maker
from tmjr.db.models import Juego
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc
from tmjr.services import suscripciones as sub_svc


async def listar_premisas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el catálogo: una tarjeta por premisa con botón de suscripción."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    async with async_session_maker() as session:
        premisas = await premisas_svc.list_all_premisas(session)
        ids_juego = {p.id_juego for p in premisas if p.id_juego is not None}
        juegos_por_id: dict[int, str] = {}
        for jid in ids_juego:
            juego = await session.get(Juego, jid)
            if juego is not None:
                juegos_por_id[jid] = juego.nombre

        persona = await personas_svc.get_persona_by_telegram(
            session, update.effective_user.id
        )
        suscritas_ids: set[int] = set()
        if persona is not None:
            premisas_suscritas = await sub_svc.list_by_persona(
                session, persona.id
            )
            suscritas_ids = {p.id for p in premisas_suscritas}

    if not premisas:
        await update.effective_message.reply_text(
            "Aún no hay premisas. Crea una desde la caja 📜 Premisa → Crear."
        )
        return

    await update.effective_message.reply_text(
        f"<b>Catálogo de premisas</b> ({len(premisas)}):", parse_mode="HTML"
    )
    for p in premisas:
        lineas = [f"📜 {build_object_link('premisa', p.id, p.nombre)}"]
        if p.id_juego is not None and (
            juego_nombre := juegos_por_id.get(p.id_juego)
        ):
            lineas.append(
                f"🎮 {build_object_link('juego', p.id_juego, juego_nombre)}"
            )
        if p.descripcion:
            lineas.append(f"<i>{escape(p.descripcion)}</i>")
        await update.effective_message.reply_text(
            "\n".join(lineas),
            parse_mode="HTML",
            reply_markup=boton_suscripcion_premisa(
                p.id, suscrito=p.id in suscritas_ids
            ),
        )
