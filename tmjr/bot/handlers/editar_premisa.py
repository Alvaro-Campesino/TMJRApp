"""Editar una premisa existente del DM.

Flujo:
  1. PICK: picker con las premisas del DM (`edprempick_<id>`).
  2. CAMPO: submenú con los campos editables (`edpremcampo_<campo>`).
  3. Según el campo:
     - NOMBRE / DESC / AVISO → texto libre.
     - JUEGO → picker de juegos del DM + 'Añadir nuevo' (mismo subflujo
       que en crear premisa, con prefijos propios `epjuego_*` y
       `epnuevo_juego_*` para no chocar con los otros flujos).
  4. Persiste con `premisas.update_premisa`.

Solo el DM dueño puede editar (filtrado por `dm_premisas`).
"""
from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tmjr.bot.keyboards import (
    picker_premisas_dm_editar,
    submenu_editar_premisa,
)
from tmjr.bot.states import EditarPremisa
from tmjr.db import async_session_maker
from tmjr.db.models import Juego, Premisa
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc

END = ConversationHandler.END


# ─────────────────────── teclados específicos ─────────────────────


def _juegos_kb(juegos: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Teclado de juegos del DM con callbacks `epjuego_<id>` / `epjuego_nuevo`."""
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"epjuego_{jid}")]
        for jid, nombre in juegos
    ]
    rows.append([InlineKeyboardButton("➕ Añadir nuevo", callback_data="epjuego_nuevo")])
    return InlineKeyboardMarkup(rows)


def _confirmar_juego_nuevo_kb(nombre: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(f"✅ Crear '{nombre}'", callback_data="epnuevo_juego_ok"),
            InlineKeyboardButton("❌ Cancelar", callback_data="epnuevo_juego_no"),
        ]]
    )


# ─────────────────────────── entrypoint ───────────────────────────


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Carga las premisas del DM y muestra el picker."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text(
                "Solo los DMs pueden editar premisas."
            )
            return END
        premisas = await premisas_svc.list_premisas_for_dm(session, persona.id_master)
        context.user_data["editar_persona_id"] = persona.id

    if not premisas:
        await update.effective_message.reply_text(
            "No tienes premisas para editar. Crea una primero."
        )
        return END

    await update.effective_message.reply_text(
        "Elige la premisa a editar:",
        reply_markup=picker_premisas_dm_editar(
            [(p.id, p.nombre) for p in premisas]
        ),
    )
    return EditarPremisa.PICK


async def pick_premisa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la premisa elegida y muestra el submenú de campos."""
    query = update.callback_query
    await query.answer()
    premisa_id = int(query.data.removeprefix("edprempick_"))
    context.user_data["editar_premisa_id"] = premisa_id

    await query.edit_message_text(
        "¿Qué quieres cambiar?", reply_markup=submenu_editar_premisa()
    )
    return EditarPremisa.CAMPO


async def pick_campo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Despacha al estado correspondiente según el campo elegido."""
    query = update.callback_query
    await query.answer()
    campo = query.data.removeprefix("edpremcampo_")

    if campo == "nombre":
        await query.edit_message_text(
            "Escribe el nuevo nombre de la premisa (≤100 caracteres)."
        )
        return EditarPremisa.NOMBRE
    if campo == "desc":
        await query.edit_message_text(
            "Escribe la nueva descripción (≤400 caracteres) o /skip para vaciarla."
        )
        return EditarPremisa.DESC
    if campo == "aviso":
        await query.edit_message_text(
            "Escribe el nuevo aviso de contenido (≤200 caracteres) o /skip para vaciarlo."
        )
        return EditarPremisa.AVISO
    if campo == "juego":
        return await _ask_juego(update, context)

    await query.edit_message_text("Opción no reconocida.")
    return END


# ─────────────────────────── nombre / desc / aviso ────────────────


async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un nombre no vacío de hasta 100 caracteres."
        )
        return EditarPremisa.NOMBRE
    return await _persistir(update, context, nombre=nombre)


async def recibir_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.effective_message.text or ""
    if raw.strip().lower() in {"/skip", ""}:
        desc = ""
    else:
        if len(raw) > 400:
            await update.effective_message.reply_text(
                "Demasiado largo (máx. 400). Resúmelo o usa /skip."
            )
            return EditarPremisa.DESC
        desc = raw.strip()
    return await _persistir(update, context, descripcion=desc)


async def recibir_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.effective_message.text or ""
    if raw.strip().lower() in {"/skip", ""}:
        aviso = ""
    else:
        if len(raw) > 200:
            await update.effective_message.reply_text(
                "Demasiado largo (máx. 200). Resúmelo o usa /skip."
            )
            return EditarPremisa.AVISO
        aviso = raw.strip()
    return await _persistir(update, context, aviso_contenido=aviso)


# ─────────────────────────── juego (con subflujo añadir) ──────────


async def _ask_juego(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el teclado de juegos del DM + opción 'Añadir nuevo'."""
    persona_id = context.user_data["editar_persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        juegos = await juegos_svc.list_juegos_for_dm(session, persona.id_master)

    kb = _juegos_kb([(j.id, j.nombre) for j in juegos])
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Elige el sistema de rol o añade uno nuevo:", reply_markup=kb
        )
    else:
        await update.effective_message.reply_text(
            "Elige el sistema de rol o añade uno nuevo:", reply_markup=kb
        )
    return EditarPremisa.JUEGO


async def juego_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Resuelve la elección del teclado de juegos."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "epjuego_nuevo":
        await query.edit_message_text(
            "Escribe el nombre del juego (p. ej. D&D 5e, Vampiro)."
        )
        return EditarPremisa.NUEVO_JUEGO_NOMBRE

    juego_id = int(data.split("_", 1)[1])
    async with async_session_maker() as session:
        juego = await session.get(Juego, juego_id)
        nombre = juego.nombre if juego else "?"

    await query.edit_message_text(f"🎮 Juego: *{nombre}*", parse_mode="Markdown")
    return await _persistir(update, context, id_juego=juego_id)


async def nuevo_juego_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja el nombre de un juego nuevo: lookup en catálogo o pedir confirmación."""
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un nombre no vacío de hasta 100 caracteres."
        )
        return EditarPremisa.NUEVO_JUEGO_NOMBRE

    context.user_data["editar_nuevo_juego_nombre"] = nombre
    persona_id = context.user_data["editar_persona_id"]

    async with async_session_maker() as session:
        existing = await juegos_svc.find_juego_by_name(session, nombre)
        if existing is not None:
            persona = await personas_svc.get_persona(session, persona_id)
            await juegos_svc.add_juego_to_dm(
                session, id_dm=persona.id_master, id_juego=existing.id
            )
            await update.effective_message.reply_text(
                f"✅ '{existing.nombre}' ya estaba en el catálogo, lo añado a tu lista."
            )
            return await _persistir(update, context, id_juego=existing.id)

    await update.effective_message.reply_text(
        f"'{nombre}' no está en el catálogo global. ¿Lo creo y lo añado a tu lista?",
        reply_markup=_confirmar_juego_nuevo_kb(nombre),
    )
    return EditarPremisa.CONFIRMAR_NUEVO_JUEGO


async def confirmar_nuevo_juego(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "epnuevo_juego_no":
        await query.edit_message_text(
            "Cancelado. Vuelve a escribir el nombre o usa /cancelar."
        )
        return EditarPremisa.NUEVO_JUEGO_NOMBRE

    nombre = context.user_data["editar_nuevo_juego_nombre"]
    persona_id = context.user_data["editar_persona_id"]

    async with async_session_maker() as session:
        juego = await juegos_svc.create_juego(session, nombre=nombre)
        persona = await personas_svc.get_persona(session, persona_id)
        await juegos_svc.add_juego_to_dm(
            session, id_dm=persona.id_master, id_juego=juego.id
        )

    await query.edit_message_text(f"✅ Creado '{juego.nombre}' en el catálogo.")
    return await _persistir(update, context, id_juego=juego.id)


# ─────────────────────────── persistir ────────────────────────────


async def _persistir(
    update: Update, context: ContextTypes.DEFAULT_TYPE, **fields
) -> int:
    """Aplica los cambios a la premisa y confirma."""
    premisa_id = context.user_data["editar_premisa_id"]
    async with async_session_maker() as session:
        premisa = await session.get(Premisa, premisa_id)
        if premisa is None:
            await update.effective_message.reply_text("Esa premisa ya no existe.")
            return END
        try:
            await premisas_svc.update_premisa(session, premisa, **fields)
        except ValueError as e:
            await update.effective_message.reply_text(f"❌ {e}")
            return END

    await update.effective_message.reply_text("✅ Cambio guardado.")
    return END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_handler() -> ConversationHandler:
    """ConversationHandler de editar premisa. Entry: caja_premisa_editar."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(_entry, pattern=r"^caja_premisa_editar$"),
        ],
        states={
            EditarPremisa.PICK: [
                CallbackQueryHandler(pick_premisa, pattern=r"^edprempick_\d+$"),
            ],
            EditarPremisa.CAMPO: [
                CallbackQueryHandler(pick_campo, pattern=r"^edpremcampo_"),
            ],
            EditarPremisa.NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre),
            ],
            EditarPremisa.DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_desc),
                CommandHandler("skip", recibir_desc),
            ],
            EditarPremisa.AVISO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_aviso),
                CommandHandler("skip", recibir_aviso),
            ],
            EditarPremisa.JUEGO: [
                CallbackQueryHandler(juego_pick, pattern=r"^epjuego_"),
            ],
            EditarPremisa.NUEVO_JUEGO_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_juego_nombre),
            ],
            EditarPremisa.CONFIRMAR_NUEVO_JUEGO: [
                CallbackQueryHandler(
                    confirmar_nuevo_juego, pattern=r"^epnuevo_juego_(ok|no)$"
                ),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="editar_premisa",
        persistent=False,
    )
