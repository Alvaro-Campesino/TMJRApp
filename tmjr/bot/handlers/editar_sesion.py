"""Editar una sesión existente del DM.

Flujo:
  1. PICK: picker con las sesiones futuras del DM (`edsespick_<id>`).
  2. CAMPO: submenú con los campos editables (`edsescampo_<campo>`).
  3. Según el campo, se entra en un estado específico para recoger el valor:
     NOMBRE / DESC (texto), LUGAR (ReplyKeyboard), FECHA → HORA → MINUTOS
     (calendario + pickers), PLAZAS (texto numérico).
  4. Se persiste con `sesiones.update_sesion` y, si la sesión está
     publicada, se republica la tarjeta en el canal.

Solo el DM dueño de la sesión puede editarla (filtrado en el picker).
Las plazas no pueden bajar por debajo de los apuntados (validado en el
servicio).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time
from html import escape

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tmjr.bot.keyboards import (
    calendario,
    confirmar_borrar_sesion,
    picker_hora,
    picker_minutos,
    picker_sesiones_dm,
    submenu_editar_sesion,
)

logger = logging.getLogger(__name__)
from tmjr.bot.publicador import publicar_sesion
from tmjr.bot.states import EditarSesion
from tmjr.db import async_session_maker
from tmjr.db.models import Premisa, Sesion
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc

END = ConversationHandler.END

_LUGAR_OTRO = "✏️ Escribe otro..."


# ─────────────────────────── entrypoint ───────────────────────────


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Carga las sesiones futuras del DM y muestra el picker."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text(
                "Solo los DMs pueden editar sesiones."
            )
            return END
        sesiones = await sesiones_svc.list_sesiones_for_dm(
            session, persona.id_master, only_future=True
        )

    if not sesiones:
        await update.effective_message.reply_text(
            "No tienes sesiones futuras para editar."
        )
        return END

    items = [
        (s.id, s.nombre or f"Sesión #{s.id}", s.fecha.strftime("%Y-%m-%d %H:%M"))
        for s in sesiones
    ]
    await update.effective_message.reply_text(
        "Elige la sesión a editar:",
        reply_markup=picker_sesiones_dm(items),
    )
    return EditarSesion.PICK


async def pick_sesion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la sesión elegida y muestra el submenú de campos."""
    query = update.callback_query
    await query.answer()
    sesion_id = int(query.data.removeprefix("edsespick_"))
    context.user_data["editar_sesion_id"] = sesion_id

    await query.edit_message_text("¿Qué quieres cambiar?",
                                  reply_markup=submenu_editar_sesion())
    return EditarSesion.CAMPO


async def pick_campo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Despacha al estado correspondiente según el campo elegido."""
    query = update.callback_query
    await query.answer()
    campo = query.data.removeprefix("edsescampo_")

    if campo == "nombre":
        await query.edit_message_text(
            "Escribe el nuevo nombre de la sesión (≤100 caracteres)."
        )
        return EditarSesion.NOMBRE
    if campo == "desc":
        await query.edit_message_text(
            "Escribe la nueva descripción (≤400 caracteres) o /skip para vaciarla."
        )
        return EditarSesion.DESC
    if campo == "lugar":
        await query.edit_message_text("Elige el nuevo lugar:")
        await update.effective_message.reply_text(
            "📍 ¿Dónde será?",
            reply_markup=ReplyKeyboardMarkup(
                [[
                    KeyboardButton("🏢 Biblioteca Rafael Azcona"),
                    KeyboardButton("📱 Online"),
                    KeyboardButton(_LUGAR_OTRO),
                ]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return EditarSesion.LUGAR
    if campo == "fecha":
        today = date.today()
        await query.edit_message_text("Elige la nueva fecha:")
        await update.effective_message.reply_text(
            "Calendario:",
            reply_markup=calendario(today.year, today.month, min_date=today),
        )
        return EditarSesion.FECHA
    if campo == "plazas":
        await query.edit_message_text("¿Cuántas plazas máximas? (1-10)")
        return EditarSesion.PLAZAS
    if campo == "plazas_min":
        async with async_session_maker() as session:
            sesion = await session.get(Sesion, context.user_data["editar_sesion_id"])
            plazas_max = sesion.plazas_totales if sesion else 10
        await query.edit_message_text(
            f"¿Cuántas plazas mínimas? (0-{plazas_max}, o /skip para 0 = sin mínimo)"
        )
        return EditarSesion.PLAZAS_MINIMAS
    if campo == "borrar":
        await query.edit_message_text(
            "⚠️ Esto borrará la sesión, su tarjeta del canal y notificará "
            "a los apuntados. ¿Seguro?",
            reply_markup=confirmar_borrar_sesion(),
        )
        return EditarSesion.CONFIRMAR_BORRAR

    # Fallback: campo desconocido.
    await query.edit_message_text("Opción no reconocida.")
    return END


# ─────────────────────────── nombre / desc ────────────────────────


async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Valida y guarda el nuevo nombre."""
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un nombre no vacío de hasta 100 caracteres."
        )
        return EditarSesion.NOMBRE
    return await _persistir(update, context, nombre=nombre)


async def recibir_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Valida y guarda la nueva descripción (o la vacía con /skip)."""
    raw = update.effective_message.text or ""
    if raw.strip().lower() in {"/skip", ""}:
        desc = ""
    else:
        if len(raw) > 400:
            await update.effective_message.reply_text(
                "Demasiado largo (máx. 400). Resúmelo o usa /skip."
            )
            return EditarSesion.DESC
        desc = raw.strip()
    return await _persistir(update, context, descripcion=desc)


# ─────────────────────────── lugar ────────────────────────────────


async def recibir_lugar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recoge el lugar (botón o texto libre)."""
    lugar = (update.effective_message.text or "").strip()
    if lugar == _LUGAR_OTRO:
        await update.effective_message.reply_text(
            "Escribe la dirección o lugar:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return EditarSesion.LUGAR
    return await _persistir(update, context, lugar=lugar, _quitar_kb=True)


# ─────────────────────────── fecha + hora + minutos ───────────────


async def fecha_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    raw = query.data.removeprefix("cal_nav_")
    year, month = (int(x) for x in raw.split("-"))
    await query.edit_message_reply_markup(
        reply_markup=calendario(year, month, min_date=date.today())
    )
    return EditarSesion.FECHA


async def fecha_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    raw = query.data.removeprefix("cal_pick_")
    f = date.fromisoformat(raw)
    if f < date.today():
        await query.answer("Esa fecha ya pasó.", show_alert=True)
        return EditarSesion.FECHA
    await query.answer()
    context.user_data["editar_fecha_dia"] = f
    await query.edit_message_text(f"📅 Fecha: *{f.isoformat()}*", parse_mode="Markdown")
    await query.message.reply_text("¿A qué hora?", reply_markup=picker_hora())
    return EditarSesion.HORA


async def fecha_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
    return EditarSesion.FECHA


async def hora_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    h = int(query.data.removeprefix("cshora_"))
    context.user_data["editar_hora"] = h
    await query.edit_message_text(f"🕐 Hora: *{h:02d}:??*", parse_mode="Markdown")
    await query.message.reply_text("¿Y los minutos?", reply_markup=picker_minutos())
    return EditarSesion.MINUTOS


async def minutos_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    m = int(query.data.removeprefix("csmin_"))
    h = context.user_data["editar_hora"]
    d = context.user_data["editar_fecha_dia"]
    fecha_dt = datetime.combine(d, time(hour=h, minute=m))
    await query.edit_message_text(
        f"📅 Nueva fecha y hora: *{fecha_dt.strftime('%Y-%m-%d %H:%M')}*",
        parse_mode="Markdown",
    )
    return await _persistir(update, context, fecha=fecha_dt)


# ─────────────────────────── plazas ───────────────────────────────


async def recibir_plazas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text or "").strip()
    try:
        n = int(raw)
        assert 1 <= n <= 10
    except (ValueError, AssertionError):
        await update.effective_message.reply_text("Tiene que ser un número entre 1 y 10.")
        return EditarSesion.PLAZAS
    return await _persistir(update, context, plazas_totales=n)


async def recibir_plazas_minimas(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Recoge el nuevo mínimo. `/skip` o vacío → 0 (sin mínimo)."""
    raw = (update.effective_message.text or "").strip()
    sesion_id = context.user_data["editar_sesion_id"]
    async with async_session_maker() as session:
        sesion = await session.get(Sesion, sesion_id)
    plazas_max = sesion.plazas_totales if sesion else 10

    if raw.lower() in {"/skip", ""}:
        n_min = 0
    else:
        try:
            n_min = int(raw)
            assert 0 <= n_min <= plazas_max
        except (ValueError, AssertionError):
            await update.effective_message.reply_text(
                f"Tiene que ser un número entre 0 y {plazas_max}."
            )
            return EditarSesion.PLAZAS_MINIMAS
    return await _persistir(update, context, plazas_minimas=n_min)


# ─────────────────────────── persistir + republicar ───────────────


async def _persistir(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, _quitar_kb: bool = False, **fields
) -> int:
    """Aplica los cambios a la sesión y republica la tarjeta si está publicada."""
    sesion_id = context.user_data["editar_sesion_id"]
    async with async_session_maker() as session:
        sesion = await session.get(Sesion, sesion_id)
        if sesion is None:
            await update.effective_message.reply_text("Esa sesión ya no existe.")
            return END
        try:
            await sesiones_svc.update_sesion(session, sesion, **fields)
        except ValueError as e:
            await update.effective_message.reply_text(f"❌ {e}")
            return END

        premisa = (
            await session.get(Premisa, sesion.id_premisa)
            if sesion.id_premisa is not None else None
        )
        jugadores = await sesiones_svc.nombre_pjs_en_sesion(session, sesion.id)

    kwargs = {"reply_markup": ReplyKeyboardRemove()} if _quitar_kb else {}
    await update.effective_message.reply_text("✅ Cambio guardado.", **kwargs)

    if sesion.telegram_message_id is not None:
        try:
            await publicar_sesion(
                context.bot, sesion, premisa=premisa, jugadores=jugadores
            )
        except TelegramError as e:
            await update.effective_message.reply_text(
                f"Guardado, pero no pude actualizar la tarjeta del canal: {e}"
            )

    return END


async def confirmar_borrar(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Resuelve el callback de confirmación: si sí, borra todo; si no, cancela.

    Antes de borrar la sesión captura: lista de apuntados (telegram_id +
    pj.nombre), chat_id + message_id de la tarjeta, título y fecha. Tras
    borrar: elimina la tarjeta del canal (best-effort) y notifica a cada
    apuntado por DM (best-effort, captura `TelegramError`).
    """
    query = update.callback_query
    await query.answer()

    if query.data == "edborrar_no":
        await query.edit_message_text("Cancelado.")
        return END

    sesion_id = context.user_data["editar_sesion_id"]
    async with async_session_maker() as session:
        sesion = await session.get(Sesion, sesion_id)
        if sesion is None:
            await query.edit_message_text("Esa sesión ya no existe.")
            return END

        # Captura ANTES de borrar (después no podremos leer estos campos).
        apuntados = await sesiones_svc.apuntados_telegram(session, sesion.id)
        chat_id = sesion.telegram_chat_id
        msg_id = sesion.telegram_message_id
        titulo = sesion.nombre or f"Sesión #{sesion.id}"
        fecha_str = sesion.fecha.strftime("%Y-%m-%d %H:%M")

        await sesiones_svc.borrar_sesion(session, sesion)

    # Borrar la tarjeta del canal (best-effort).
    if chat_id and msg_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except TelegramError as e:
            logger.warning("No pude borrar la tarjeta del canal: %s", e)

    # Notificar a cada apuntado (best-effort).
    notificados = 0
    for telegram_id, pj_nombre in apuntados:
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"⚠️ Hola <b>{escape(pj_nombre)}</b>, la sesión "
                    f"<b>{escape(titulo)}</b> del {fecha_str} ha sido "
                    f"cancelada por el DM."
                ),
                parse_mode="HTML",
            )
            notificados += 1
        except TelegramError as e:
            logger.warning(
                "No pude notificar a telegram_id=%s: %s", telegram_id, e
            )

    msg = f"✅ Sesión #{sesion_id} borrada."
    if apuntados:
        msg += f" Notificados {notificados}/{len(apuntados)} apuntados."
    await query.edit_message_text(msg)
    return END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback /cancelar para cerrar el flujo."""
    await update.effective_message.reply_text(
        "Cancelado.", reply_markup=ReplyKeyboardRemove()
    )
    return END


def build_handler() -> ConversationHandler:
    """ConversationHandler de editar sesión.

    Entry: el botón ✏️ Editar de la tarjeta listada en 'Mis sesiones'
    emite `edsespick_<id>` y se salta el picker (el id ya viene en el
    callback). El antiguo flujo `caja_sesion_editar` ya no se usa: el
    submenú dinámico de Sesión (`submenu_sesion`) ya no ofrece ese botón.
    """
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pick_sesion, pattern=r"^edsespick_\d+$"),
        ],
        states={
            EditarSesion.PICK: [
                CallbackQueryHandler(pick_sesion, pattern=r"^edsespick_\d+$"),
            ],
            EditarSesion.CAMPO: [
                CallbackQueryHandler(pick_campo, pattern=r"^edsescampo_"),
            ],
            EditarSesion.NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre),
            ],
            EditarSesion.DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_desc),
                CommandHandler("skip", recibir_desc),
            ],
            EditarSesion.LUGAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_lugar),
            ],
            EditarSesion.FECHA: [
                CallbackQueryHandler(fecha_nav, pattern=r"^cal_nav_\d{4}-\d{2}$"),
                CallbackQueryHandler(fecha_pick, pattern=r"^cal_pick_\d{4}-\d{2}-\d{2}$"),
                CallbackQueryHandler(fecha_noop, pattern=r"^cal_noop$"),
            ],
            EditarSesion.HORA: [
                CallbackQueryHandler(hora_pick, pattern=r"^cshora_\d{2}$"),
            ],
            EditarSesion.MINUTOS: [
                CallbackQueryHandler(minutos_pick, pattern=r"^csmin_\d{2}$"),
            ],
            EditarSesion.PLAZAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_plazas),
            ],
            EditarSesion.PLAZAS_MINIMAS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, recibir_plazas_minimas
                ),
                CommandHandler("skip", recibir_plazas_minimas),
            ],
            EditarSesion.CONFIRMAR_BORRAR: [
                CallbackQueryHandler(
                    confirmar_borrar, pattern=r"^edborrar_(si|no)$"
                ),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="editar_sesion",
        persistent=False,
    )
