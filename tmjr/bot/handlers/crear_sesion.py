"""Flujo: crear sesión.

Pasos:
  1. Si la persona no es DM, le pedimos biografía y creamos perfil DM.
  2. Pedimos el nombre de la premisa (título de la partida).
  3. Pedimos descripción de la premisa (con /skip).
  4. Mostramos teclado con los juegos del DM + 'Añadir nuevo'.
       - Si elige existente → seguimos.
       - Si elige 'añadir nuevo' → pedimos nombre, lookup en catálogo:
            * Si existe → lo enlazamos al DM y seguimos.
            * Si no existe → confirmamos y lo creamos en catálogo + DM.
  5. Pedimos fecha (ISO).
  6. Pedimos plazas (1-6).
  7. Creamos premisa + sesion(id_premisa=...) + publicamos tarjeta.
"""
from __future__ import annotations

from datetime import date

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tmjr.bot.keyboards import confirmar_juego_nuevo, juegos_del_dm
from tmjr.bot.publicador import publicar_sesion
from tmjr.bot.states import CrearSesion
from tmjr.db import async_session_maker
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc
from tmjr.services import sesiones as sesiones_svc

END = ConversationHandler.END


# ─────────────────────────── entrypoint ───────────────────────────


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        context.user_data["persona_id"] = persona.id

        if persona.id_master is None:
            await update.effective_message.reply_text(
                "Aún no eres DM. Cuéntame en una frase tu experiencia "
                "como máster (o /skip)."
            )
            return CrearSesion.DM_BIO

    await _ask_nombre(update)
    return CrearSesion.PREMISA_NOMBRE


async def dm_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bio = update.effective_message.text or ""
    if bio.strip().lower() in {"/skip", ""}:
        bio = None

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        await personas_svc.ensure_dm(session, persona, biografia=bio)

    await update.effective_message.reply_text("✅ Perfil de DM creado.")
    await _ask_nombre(update)
    return CrearSesion.PREMISA_NOMBRE


# ─────────────────────────── premisa ──────────────────────────────


async def _ask_nombre(update: Update) -> None:
    await update.effective_message.reply_text(
        "¿Cómo se llama la partida? (título corto, ≤100 caracteres)"
    )


async def premisa_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un título no vacío de hasta 100 caracteres."
        )
        return CrearSesion.PREMISA_NOMBRE
    context.user_data["premisa_nombre"] = nombre

    await update.effective_message.reply_text(
        "Descripción breve (≤400 caracteres) o /skip si no quieres añadir."
    )
    return CrearSesion.PREMISA_DESC


async def premisa_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.effective_message.text or ""
    desc = None if raw.strip().lower() in {"/skip", ""} else raw.strip()
    if desc and len(desc) > 400:
        await update.effective_message.reply_text(
            "Demasiado largo (máx. 400). Resúmelo o usa /skip."
        )
        return CrearSesion.PREMISA_DESC
    context.user_data["premisa_desc"] = desc

    return await _ask_juego(update, context)


# ─────────────────────────── juego ────────────────────────────────


async def _ask_juego(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        juegos = await juegos_svc.list_juegos_for_dm(session, persona.id_master)

    if juegos:
        kb = juegos_del_dm([(j.id, j.nombre) for j in juegos])
        await update.effective_message.reply_text(
            "¿Para qué sistema de rol? Elige uno o añade nuevo:",
            reply_markup=kb,
        )
    else:
        kb = juegos_del_dm([])
        await update.effective_message.reply_text(
            "Aún no tienes juegos en tu lista. Añade el primero:",
            reply_markup=kb,
        )
    return CrearSesion.PREMISA_JUEGO


async def premisa_juego_pick(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "juego_nuevo":
        await query.edit_message_text(
            "Escribe el nombre del juego (p. ej. D&D 5e, Vampiro, Blades in the Dark)."
        )
        return CrearSesion.NUEVO_JUEGO_NOMBRE

    # data == "juego_<id>"
    juego_id = int(data.split("_", 1)[1])
    context.user_data["juego_id"] = juego_id

    async with async_session_maker() as session:
        from tmjr.db.models import Juego
        juego = await session.get(Juego, juego_id)
        nombre = juego.nombre if juego else "?"

    await query.edit_message_text(f"Juego: *{nombre}*", parse_mode="Markdown")
    await query.message.reply_text("¿Qué fecha? (formato AAAA-MM-DD)")
    return CrearSesion.FECHA


# ─────────────────── nuevo juego (subflujo) ───────────────────────


async def nuevo_juego_nombre(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un nombre no vacío de hasta 100 caracteres."
        )
        return CrearSesion.NUEVO_JUEGO_NOMBRE

    context.user_data["nuevo_juego_nombre"] = nombre
    persona_id = context.user_data["persona_id"]

    async with async_session_maker() as session:
        existing = await juegos_svc.find_juego_by_name(session, nombre)
        if existing is not None:
            # Ya está en el catálogo global → enlaza al DM (idempotente) y sigue.
            persona = await personas_svc.get_persona(session, persona_id)
            await juegos_svc.add_juego_to_dm(
                session, id_dm=persona.id_master, id_juego=existing.id
            )
            context.user_data["juego_id"] = existing.id
            await update.effective_message.reply_text(
                f"✅ '{existing.nombre}' ya estaba en el catálogo, lo añado a tu lista."
            )
            await update.effective_message.reply_text(
                "¿Qué fecha? (formato AAAA-MM-DD)"
            )
            return CrearSesion.FECHA

    # No existe → confirmar antes de crear.
    await update.effective_message.reply_text(
        f"'{nombre}' no está en el catálogo global. "
        "¿Lo creo y lo añado a tu lista?",
        reply_markup=confirmar_juego_nuevo(nombre),
    )
    return CrearSesion.CONFIRMAR_NUEVO_JUEGO


async def confirmar_nuevo_juego(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "nuevo_juego_no":
        await query.edit_message_text(
            "Cancelado. Vuelve a escribir el nombre o usa /cancelar."
        )
        return CrearSesion.NUEVO_JUEGO_NOMBRE

    # nuevo_juego_ok
    nombre = context.user_data["nuevo_juego_nombre"]
    persona_id = context.user_data["persona_id"]

    async with async_session_maker() as session:
        juego = await juegos_svc.create_juego(session, nombre=nombre)
        persona = await personas_svc.get_persona(session, persona_id)
        await juegos_svc.add_juego_to_dm(
            session, id_dm=persona.id_master, id_juego=juego.id
        )
    context.user_data["juego_id"] = juego.id

    await query.edit_message_text(f"✅ Creado '{juego.nombre}' en el catálogo.")
    await query.message.reply_text("¿Qué fecha? (formato AAAA-MM-DD)")
    return CrearSesion.FECHA


# ─────────────────────────── fecha + plazas ───────────────────────


async def fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text or "").strip()
    try:
        f = date.fromisoformat(raw)
    except ValueError:
        await update.effective_message.reply_text(
            "Formato no válido. Usa AAAA-MM-DD."
        )
        return CrearSesion.FECHA

    context.user_data["fecha"] = f
    await update.effective_message.reply_text("¿Cuántas plazas? (1-6)")
    return CrearSesion.PLAZAS


async def plazas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text or "").strip()
    try:
        n = int(raw)
        assert 1 <= n <= 6
    except (ValueError, AssertionError):
        await update.effective_message.reply_text(
            "Tiene que ser un número entre 1 y 6."
        )
        return CrearSesion.PLAZAS
    context.user_data["plazas"] = n

    await update.effective_message.reply_text(
        "¿Quieres añadir una nota específica para *esta* sesión? "
        "(≤400 caracteres, o /skip para usar solo la descripción de la premisa)",
        parse_mode="Markdown",
    )
    return CrearSesion.SESION_DESC


async def sesion_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.effective_message.text or ""
    if raw.strip().lower() in {"/skip", ""}:
        sesion_desc_text = None
    else:
        if len(raw) > 400:
            await update.effective_message.reply_text(
                "Demasiado largo (máx. 400). Resúmelo o usa /skip."
            )
            return CrearSesion.SESION_DESC
        sesion_desc_text = raw.strip()

    persona_id = context.user_data["persona_id"]
    juego_id = context.user_data.get("juego_id")
    nombre = context.user_data["premisa_nombre"]
    premisa_desc_text = context.user_data.get("premisa_desc")
    n = context.user_data["plazas"]

    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        premisa = await premisas_svc.crear_premisa(
            session,
            nombre=nombre,
            id_juego=juego_id,
            descripcion=premisa_desc_text,
        )
        sesion = await sesiones_svc.crear_sesion(
            session,
            id_dm=persona.id_master,
            id_juego=juego_id,
            fecha=context.user_data["fecha"],
            plazas_totales=n,
            nombre=nombre,                   # de momento mismo que la premisa
            descripcion=sesion_desc_text,
            id_premisa=premisa.id,
        )
        jugadores = []
        try:
           chat_id, thread_id, message_id  = await publicar_sesion(context.bot, sesion, jugadores, premisa=premisa)
        except RuntimeError as e:
            await update.effective_message.reply_text(
                f"Sesión creada (#{sesion.id}) pero no se pudo publicar: {e}"
            )
            return END
    await sesiones_svc.marcar_publicada(session, sesion,
                                        telegram_chat_id=chat_id,
                                        telegram_thread_id = thread_id,
                                        telegram_message_id = message_id)

    await update.effective_message.reply_text(
        f"✅ Sesión #{sesion.id} de '{nombre}' creada y publicada en el canal."
    )
    return END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(_entry, pattern=r"^(crear_sesion|caja_sesion_crear)$"),
            CommandHandler("crear_sesion", _entry),
        ],
        states={
            CrearSesion.DM_BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, dm_bio),
                CommandHandler("skip", dm_bio),
            ],
            CrearSesion.PREMISA_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, premisa_nombre),
            ],
            CrearSesion.PREMISA_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, premisa_desc),
                CommandHandler("skip", premisa_desc),
            ],
            CrearSesion.PREMISA_JUEGO: [
                CallbackQueryHandler(premisa_juego_pick, pattern=r"^juego_"),
            ],
            CrearSesion.NUEVO_JUEGO_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_juego_nombre),
            ],
            CrearSesion.CONFIRMAR_NUEVO_JUEGO: [
                CallbackQueryHandler(
                    confirmar_nuevo_juego, pattern=r"^nuevo_juego_(ok|no)$"
                ),
            ],
            CrearSesion.FECHA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fecha),
            ],
            CrearSesion.PLAZAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, plazas),
            ],
            CrearSesion.SESION_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sesion_desc),
                CommandHandler("skip", sesion_desc),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="crear_sesion",
        persistent=False,
    )
