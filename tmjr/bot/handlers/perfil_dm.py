"""Caja Persona → acciones sobre el perfil de DM.

Incluye:
  - Crear perfil DM (ConversationHandler que pide biografía).
  - Ver perfil DM (one-shot: bio + nº juegos + nº premisas + botones de listado).
  - Listar juegos / premisas del DM (callbacks one-shot).
  - Editar perfil DM:
      * Editar biografía (ConversationHandler).
      * Añadir juego del catálogo global → picker que se refresca.
      * Añadir premisa del catálogo global → picker que se refresca.

Convenciones de callbacks:
  * `caja_persona_crear_dm`             → entry crear DM
  * `caja_persona_ver_dm`                → ver perfil DM
  * `caja_persona_ver_dm_juegos`         → listar juegos del DM
  * `caja_persona_ver_dm_premisas`       → listar premisas del DM
  * `caja_persona_editar_dm`             → abre submenú editar DM
  * `caja_persona_editar_dm_bio`         → entry editar biografía
  * `caja_persona_editar_dm_juego`       → abre picker de juegos
  * `caja_persona_editar_dm_premisa`     → abre picker de premisas
  * `dm_add_juego_<id>` / `dm_add_premisa_<id>` → enlazan y refrescan picker
  * `dm_picker_done`                     → cierra picker
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tmjr.bot.keyboards import (
    picker_juegos_para_dm,
    picker_premisas_para_dm,
    submenu_editar_dm,
    vista_perfil_dm,
)
from tmjr.bot.states import CrearPerfilDM, EditarPerfilDMBio
from tmjr.db import async_session_maker
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc

END = ConversationHandler.END


# ─────────────────────────── Crear perfil DM ──────────────────────


async def _crear_dm_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Punto de entrada del flujo de creación de perfil DM.

    Si la persona ya es DM, lo informa y termina sin pedir biografía.
    """
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None:
            await update.effective_message.reply_text(
                "Primero usa /start para registrarte."
            )
            return END
        if persona.id_master is not None:
            await update.effective_message.reply_text(
                "Ya tienes perfil de DM."
            )
            return END
        context.user_data["persona_id"] = persona.id

    await update.effective_message.reply_text(
        "Cuéntame en una frase tu experiencia como máster (o /skip)."
    )
    return CrearPerfilDM.BIO


async def _crear_dm_bio(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Recibe la biografía inicial y crea el perfil DM."""
    raw = update.effective_message.text or ""
    bio = None if raw.strip().lower() in {"/skip", ""} else raw.strip()

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        await personas_svc.ensure_dm(session, persona, biografia=bio)

    await update.effective_message.reply_text("✅ Perfil de DM creado.")
    return END


# ─────────────────────────── Ver perfil DM ────────────────────────


async def ver_perfil_dm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Muestra biografía + nº de juegos + nº de premisas, con botones de listado."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text(
                "Aún no tienes perfil de DM."
            )
            return
        dm = await personas_svc.get_dm(session, persona.id_master)
        juegos = await juegos_svc.list_juegos_for_dm(session, persona.id_master)
        premisas = await premisas_svc.list_premisas_for_dm(session, persona.id_master)

    bio = dm.biografia if dm and dm.biografia else "_(sin biografía)_"
    msg = (
        f"*Tu perfil DM*\n"
        f"• Biografía: {bio}\n"
        f"• Juegos en tu lista: {len(juegos)}\n"
        f"• Premisas creadas: {len(premisas)}"
    )
    await update.effective_message.reply_text(
        msg, parse_mode="Markdown", reply_markup=vista_perfil_dm()
    )


async def ver_dm_juegos(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Muestra la lista de juegos del DM."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text("No tienes perfil de DM.")
            return
        juegos = await juegos_svc.list_juegos_for_dm(session, persona.id_master)

    if not juegos:
        await update.effective_message.reply_text("No tienes juegos en tu lista.")
        return

    lineas = "\n".join(f"• {j.nombre}" for j in juegos)
    await update.effective_message.reply_text(
        f"*Tus juegos*\n{lineas}", parse_mode="Markdown"
    )


async def ver_dm_premisas(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Muestra la lista de premisas del DM."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text("No tienes perfil de DM.")
            return
        premisas = await premisas_svc.list_premisas_for_dm(session, persona.id_master)

    if not premisas:
        await update.effective_message.reply_text("No tienes premisas creadas.")
        return

    lineas = "\n".join(f"• {p.nombre}" for p in premisas)
    await update.effective_message.reply_text(
        f"*Tus premisas*\n{lineas}", parse_mode="Markdown"
    )


# ─────────────────────────── Editar perfil DM ─────────────────────


async def abrir_editar_dm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Muestra el submenú de edición de perfil DM (3 botones inline)."""
    query = update.callback_query
    if query is not None:
        await query.answer()
    await update.effective_message.reply_text(
        "Editar perfil DM — ¿qué quieres cambiar?",
        reply_markup=submenu_editar_dm(),
    )


# ── Editar biografía (ConversationHandler) ──


async def _editar_bio_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Pide la nueva biografía del DM."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text("No tienes perfil de DM.")
            return END
        context.user_data["dm_id"] = persona.id_master

    await update.effective_message.reply_text(
        "Escribe tu nueva biografía como DM (≤400 caracteres) o /skip para vaciarla."
    )
    return EditarPerfilDMBio.BIO


async def _editar_bio_recibir(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Guarda la biografía recibida (o la vacía si /skip)."""
    raw = update.effective_message.text or ""
    bio = None if raw.strip().lower() in {"/skip", ""} else raw.strip()
    if bio and len(bio) > 400:
        await update.effective_message.reply_text(
            "Demasiado largo (máx. 400). Resúmelo o usa /skip."
        )
        return EditarPerfilDMBio.BIO

    dm_id = context.user_data["dm_id"]
    async with async_session_maker() as session:
        dm = await personas_svc.get_dm(session, dm_id)
        await personas_svc.update_dm_biografia(session, dm, biografia=bio)

    await update.effective_message.reply_text("✅ Biografía actualizada.")
    return END


# ── Añadir juego al DM (picker) ──


async def abrir_picker_juegos(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Muestra el picker con los juegos del catálogo que el DM aún no tiene."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text("No tienes perfil de DM.")
            return
        disponibles = await juegos_svc.list_juegos_not_in_dm(session, persona.id_master)

    if not disponibles:
        await update.effective_message.reply_text(
            "Ya tienes todos los juegos del catálogo en tu lista."
        )
        return

    await update.effective_message.reply_text(
        "Elige un juego para añadirlo a tu lista (pulsa ✅ Hecho cuando termines):",
        reply_markup=picker_juegos_para_dm([(j.id, j.nombre) for j in disponibles]),
    )


async def add_juego(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enlaza el juego elegido al DM y refresca el picker con la lista actualizada."""
    query = update.callback_query
    await query.answer()
    juego_id = int(query.data.removeprefix("dm_add_juego_"))

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await query.edit_message_text("No tienes perfil de DM.")
            return
        await juegos_svc.add_juego_to_dm(
            session, id_dm=persona.id_master, id_juego=juego_id
        )
        disponibles = await juegos_svc.list_juegos_not_in_dm(session, persona.id_master)

    if not disponibles:
        await query.edit_message_text(
            "✅ Añadido. Ya tienes todos los juegos del catálogo."
        )
        return

    await query.edit_message_text(
        "✅ Añadido. Elige otro o pulsa ✅ Hecho:",
        reply_markup=picker_juegos_para_dm([(j.id, j.nombre) for j in disponibles]),
    )


# ── Añadir premisa al DM (picker) ──


async def abrir_picker_premisas(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Muestra el picker con las premisas globales que el DM aún no tiene."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text("No tienes perfil de DM.")
            return
        disponibles = await premisas_svc.list_premisas_not_in_dm(
            session, persona.id_master
        )

    if not disponibles:
        await update.effective_message.reply_text(
            "No hay premisas disponibles para añadir."
        )
        return

    await update.effective_message.reply_text(
        "Elige una premisa para añadirla a tu lista (pulsa ✅ Hecho cuando termines):",
        reply_markup=picker_premisas_para_dm(
            [(p.id, p.nombre) for p in disponibles]
        ),
    )


async def add_premisa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enlaza la premisa elegida al DM y refresca el picker."""
    query = update.callback_query
    await query.answer()
    premisa_id = int(query.data.removeprefix("dm_add_premisa_"))

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await query.edit_message_text("No tienes perfil de DM.")
            return
        await premisas_svc.link_premisa_to_dm(
            session, id_dm=persona.id_master, id_premisa=premisa_id
        )
        disponibles = await premisas_svc.list_premisas_not_in_dm(
            session, persona.id_master
        )

    if not disponibles:
        await query.edit_message_text(
            "✅ Añadida. Ya tienes todas las premisas disponibles."
        )
        return

    await query.edit_message_text(
        "✅ Añadida. Elige otra o pulsa ✅ Hecho:",
        reply_markup=picker_premisas_para_dm(
            [(p.id, p.nombre) for p in disponibles]
        ),
    )


async def picker_done(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Cierra el picker editando el mensaje y eliminando los botones."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Listo.")


# ─────────────────────────── fallbacks ────────────────────────────


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback /cancelar para cerrar cualquiera de los flujos."""
    await update.effective_message.reply_text("Cancelado.")
    return END


# ─────────────────────────── builders ─────────────────────────────


def build_crear_dm_handler() -> ConversationHandler:
    """Construye el ConversationHandler para crear el perfil de DM."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _crear_dm_entry, pattern=r"^caja_persona_crear_dm$"
            ),
        ],
        states={
            CrearPerfilDM.BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _crear_dm_bio),
                CommandHandler("skip", _crear_dm_bio),
            ],
        },
        fallbacks=[CommandHandler("cancelar", _cancel)],
        name="crear_perfil_dm",
        persistent=False,
    )


def build_editar_dm_bio_handler() -> ConversationHandler:
    """Construye el ConversationHandler para editar la biografía del DM."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                _editar_bio_entry, pattern=r"^caja_persona_editar_dm_bio$"
            ),
        ],
        states={
            EditarPerfilDMBio.BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _editar_bio_recibir),
                CommandHandler("skip", _editar_bio_recibir),
            ],
        },
        fallbacks=[CommandHandler("cancelar", _cancel)],
        name="editar_perfil_dm_bio",
        persistent=False,
    )
