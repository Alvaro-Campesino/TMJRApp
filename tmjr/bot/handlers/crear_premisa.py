"""Flujo: crear Premisa.

Pasos:
  1. Verificamos que la persona ya sea DM (si no, le pedimos /crear_sesion
     primero, que es donde se crea el perfil de DM).
  2. Pedimos el nombre de la premisa (título de la partida).
  3. Pedimos descripción de la premisa (opcional, /skip).
  4. Mostramos teclado con los juegos del DM + 'Añadir nuevo'.
       - Si elige existente → seguimos.
       - Si elige 'añadir nuevo' → pedimos nombre, lookup en catálogo:
            * Si existe → lo enlazamos al DM y seguimos.
            * Si no existe → confirmamos y lo creamos en catálogo + DM.
  5. Creamos la premisa y la enlazamos al DM (tabla `dm_premisas`).

Los callbacks de juego usan prefijos propios `pjuego_…` y `pnuevo_juego_…`
para no chocar con los del flujo de crear_sesion (que está registrado antes
en la application).
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tmjr.bot.states import CrearPremisa
from tmjr.db import async_session_maker
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc

END = ConversationHandler.END


# ─────────────────────── teclados específicos ─────────────────────
# Reimplementamos `juegos_del_dm` y `confirmar_juego_nuevo` con prefijos
# `pjuego_` / `pnuevo_juego_` para que el ConversationHandler de premisas
# pueda discriminar sus callbacks de los de crear_sesion.


def _juegos_del_dm_premisa(juegos: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Teclado de juegos del DM con callbacks `pjuego_<id>` / `pjuego_nuevo`."""
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"pjuego_{jid}")]
        for jid, nombre in juegos
    ]
    rows.append([InlineKeyboardButton("➕ Añadir nuevo", callback_data="pjuego_nuevo")])
    return InlineKeyboardMarkup(rows)


def _confirmar_juego_nuevo_premisa(nombre: str) -> InlineKeyboardMarkup:
    """Teclado de confirmación para crear un juego nuevo en el catálogo."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"✅ Crear '{nombre}'", callback_data="pnuevo_juego_ok"
                ),
                InlineKeyboardButton("❌ Cancelar", callback_data="pnuevo_juego_no"),
            ]
        ]
    )


# ─────────────────────────── entrypoint ───────────────────────────


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada del flujo de crear premisa.

    Asume que la persona ya está registrada y que es DM. Si no es DM,
    cierra el flujo pidiéndole que pase por /crear_sesion (que sí crea
    el perfil de DM).
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

        if persona.id_master is None:
            await update.effective_message.reply_text(
                "Aún no eres DM. Crea primero una sesión con /crear_sesion "
                "para activar tu perfil de DM."
            )
            return END

        context.user_data["persona_id"] = persona.id

    await _ask_nombre(update)
    return CrearPremisa.NOMBRE


# ─────────────────────────── premisa ──────────────────────────────


async def _ask_nombre(update: Update) -> None:
    """Pregunta por el título de la premisa."""
    await update.effective_message.reply_text(
        "¿Cómo se llama la premisa? (título corto, ≤100 caracteres)"
    )


async def premisa_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y valida el título de la premisa, pasa al estado DESC."""
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un título para la premisa no vacío de hasta 100 caracteres."
        )
        return CrearPremisa.NOMBRE
    context.user_data["premisa_nombre"] = nombre

    await update.effective_message.reply_text(
        "Descripción breve de la premisa (≤400 caracteres) o /skip si no quieres añadir."
    )
    return CrearPremisa.DESC


async def premisa_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la descripción opcional de la premisa y pasa al selector de juego."""
    raw = update.effective_message.text or ""
    desc = None if raw.strip().lower() in {"/skip", ""} else raw.strip()
    if desc and len(desc) > 400:
        await update.effective_message.reply_text(
            "Demasiado largo (máx. 400). Resúmelo o usa /skip."
        )
        return CrearPremisa.DESC
    context.user_data["premisa_desc"] = desc

    return await _ask_juego(update, context)


# ─────────────────────────── juego ────────────────────────────────


async def _ask_juego(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el teclado con los juegos del DM + opción de añadir nuevo."""
    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        juegos = await juegos_svc.list_juegos_for_dm(session, persona.id_master)

    if juegos:
        kb = _juegos_del_dm_premisa([(j.id, j.nombre) for j in juegos])
        await update.effective_message.reply_text(
            "¿Para qué sistema de rol? Elige uno o añade nuevo:",
            reply_markup=kb,
        )
    else:
        kb = _juegos_del_dm_premisa([])
        await update.effective_message.reply_text(
            "Aún no tienes juegos en tu lista. Añade el primero:",
            reply_markup=kb,
        )
    return CrearPremisa.JUEGO


async def premisa_juego_pick(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Resuelve la elección del teclado de juegos.

    Si el usuario pulsa 'Añadir nuevo' pasa al subflujo de alta. Si elige
    uno existente lo guarda y pasa directamente a crear la premisa.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "pjuego_nuevo":
        await query.edit_message_text(
            "Escribe el nombre del juego (p. ej. D&D 5e, Vampiro, Blades in the Dark)."
        )
        return CrearPremisa.NUEVO_JUEGO_NOMBRE

    # data == "pjuego_<id>"
    juego_id = int(data.split("_", 1)[1])
    context.user_data["juego_id"] = juego_id

    async with async_session_maker() as session:
        from tmjr.db.models import Juego
        juego = await session.get(Juego, juego_id)
        nombre = juego.nombre if juego else "?"

    await query.edit_message_text(f"Juego: *{nombre}*", parse_mode="Markdown")
    return await _crear_y_enlazar(update, context)


# ─────────────────── nuevo juego (subflujo) ───────────────────────


async def nuevo_juego_nombre(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Maneja el nombre escrito para un juego nuevo.

    Hace lookup case-insensitive en el catálogo global:
      - Si existe → lo enlaza al DM y avanza a crear la premisa.
      - Si no existe → pide confirmación antes de crearlo.
    """
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un nombre no vacío de hasta 100 caracteres."
        )
        return CrearPremisa.NUEVO_JUEGO_NOMBRE

    context.user_data["nuevo_juego_nombre"] = nombre
    persona_id = context.user_data["persona_id"]

    async with async_session_maker() as session:
        existing = await juegos_svc.find_juego_by_name(session, nombre)
        if existing is not None:
            persona = await personas_svc.get_persona(session, persona_id)
            await juegos_svc.add_juego_to_dm(
                session, id_dm=persona.id_master, id_juego=existing.id
            )
            context.user_data["juego_id"] = existing.id
            await update.effective_message.reply_text(
                f"✅ '{existing.nombre}' ya estaba en el catálogo, lo añado a tu lista."
            )
            return await _crear_y_enlazar(update, context)

    await update.effective_message.reply_text(
        f"'{nombre}' no está en el catálogo global. "
        "¿Lo creo y lo añado a tu lista?",
        reply_markup=_confirmar_juego_nuevo_premisa(nombre),
    )
    return CrearPremisa.CONFIRMAR_NUEVO_JUEGO


async def confirmar_nuevo_juego(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Resuelve la confirmación de creación del juego nuevo.

    `pnuevo_juego_no` vuelve a pedir el nombre; `pnuevo_juego_ok` crea
    la entrada en el catálogo global, la enlaza al DM y pasa a crear
    la premisa.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "pnuevo_juego_no":
        await query.edit_message_text(
            "Cancelado. Vuelve a escribir el nombre o usa /cancelar."
        )
        return CrearPremisa.NUEVO_JUEGO_NOMBRE

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
    return await _crear_y_enlazar(update, context)


# ─────────────────────────── persistir premisa ────────────────────


async def _crear_y_enlazar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Crea la premisa con los datos acumulados en `user_data` y la enlaza al DM.

    Cierra la conversación con un mensaje de confirmación.
    """
    persona_id = context.user_data["persona_id"]
    juego_id = context.user_data.get("juego_id")
    nombre = context.user_data["premisa_nombre"]
    desc = context.user_data.get("premisa_desc")

    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        premisa = await premisas_svc.crear_premisa(
            session,
            nombre=nombre,
            id_juego=juego_id,
            descripcion=desc,
        )
        await premisas_svc.link_premisa_to_dm(
            session, id_dm=persona.id_master, id_premisa=premisa.id
        )

    await update.effective_message.reply_text(
        f"✅ Premisa #{premisa.id} '{premisa.nombre}' creada y añadida a tus premisas."
    )
    return END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela el flujo en curso."""
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_handler() -> ConversationHandler:
    """Construye el ConversationHandler del flujo de crear premisa."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(_entry, pattern=r"^(crear_premisa|caja_premisa_crear)$"),
            CommandHandler("crear_premisa", _entry, filters=filters.ChatType.PRIVATE),
        ],
        states={
            CrearPremisa.NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, premisa_nombre),
            ],
            CrearPremisa.DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, premisa_desc),
                CommandHandler("skip", premisa_desc),
            ],
            CrearPremisa.JUEGO: [
                CallbackQueryHandler(premisa_juego_pick, pattern=r"^pjuego_"),
            ],
            CrearPremisa.NUEVO_JUEGO_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, nuevo_juego_nombre),
            ],
            CrearPremisa.CONFIRMAR_NUEVO_JUEGO: [
                CallbackQueryHandler(
                    confirmar_nuevo_juego, pattern=r"^pnuevo_juego_(ok|no)$"
                ),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="crear_premisa",
        persistent=False,
    )
