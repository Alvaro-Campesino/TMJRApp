"""Caja Campaña → Listar y gestionar campañas del DM.

Flujos:
  - PICK: picker con las campañas del DM (`cmppick_<id>`).
  - ACCION: submenú con 'Añadir sesión' / 'Gestionar PJs' / 'Ver info'.
  - Añadir sesión → cierra esta conversación y dispara el flujo de
    crear_sesion con `campania_existente_id` precargado en user_data.
  - Gestionar PJs → submenú Añadir / Eliminar:
      - Añadir: picker con PJs no fijos → callback `cmppjadd_<id>`.
      - Eliminar: picker con PJs fijos → callback `cmppjrm_<id>`. Borra
        de campania_pjs_fijos y de las sesiones futuras (no toca pasadas).
  - Ver info → ficha de la campaña (deep-link al objeto campania).
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from tmjr.bot.keyboards import (
    picker_campanias_dm,
    picker_pjs,
    submenu_gestionar_campania,
    submenu_gestionar_pjs,
)
from tmjr.bot.object_links import format_object
from tmjr.bot.states import GestionarCampania
from tmjr.db import async_session_maker
from tmjr.db.models import Premisa
from tmjr.services import campanias as campanias_svc
from tmjr.services import personas as personas_svc

END = ConversationHandler.END


# ─────────────────────────── entrypoint ───────────────────────────


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Carga las campañas del DM y muestra el picker."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_master is None:
            await update.effective_message.reply_text(
                "Solo los DMs pueden gestionar campañas."
            )
            return END
        campanias = await campanias_svc.list_campanias_for_dm(
            session, persona.id_master
        )
        # Cargamos también el nombre de la premisa para etiquetar la campaña.
        labels = []
        for c in campanias:
            premisa = await session.get(Premisa, c.id_premisa)
            label = premisa.nombre if premisa else f"Campaña #{c.id}"
            labels.append((c.id, label))
        context.user_data["campania_persona_id"] = persona.id

    if not labels:
        await update.effective_message.reply_text(
            "No tienes campañas. Crea una desde 🏰 Campaña → Crear."
        )
        return END

    await update.effective_message.reply_text(
        "Elige una campaña:",
        reply_markup=picker_campanias_dm(labels),
    )
    return GestionarCampania.PICK


async def pick_campania(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Guarda la campaña elegida y muestra el submenú de acciones."""
    query = update.callback_query
    await query.answer()
    campania_id = int(query.data.removeprefix("cmppick_"))
    context.user_data["gestionar_campania_id"] = campania_id

    await query.edit_message_text(
        "¿Qué quieres hacer?", reply_markup=submenu_gestionar_campania()
    )
    return GestionarCampania.ACCION


async def pick_accion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Despacha la acción elegida."""
    query = update.callback_query
    await query.answer()
    accion = query.data.removeprefix("cmpacc_")
    campania_id = context.user_data["gestionar_campania_id"]

    if accion == "info":
        async with async_session_maker() as session:
            info = await format_object(session, "campania", campania_id)
        if info:
            await query.edit_message_text(info, parse_mode="HTML")
        else:
            await query.edit_message_text("No encuentro esa campaña.")
        return END

    if accion == "addsesion":
        # Inyecta el id de la campaña en user_data y deja que el flujo de
        # crear_sesion arranque desde su entry point. Avisamos al usuario
        # con instrucciones para usar el comando.
        context.user_data["campania_existente_id"] = campania_id
        await query.edit_message_text(
            "Añadir sesión a la campaña: usa /crear_sesion para arrancar el "
            "flujo. Las preguntas son las de siempre; la sesión quedará "
            "asociada automáticamente a esta campaña."
        )
        return END

    if accion == "pjs":
        await query.edit_message_text(
            "Gestión de PJs:", reply_markup=submenu_gestionar_pjs()
        )
        return GestionarCampania.PJS

    await query.edit_message_text("Opción no reconocida.")
    return END


# ─────────────────────────── PJs (añadir / eliminar) ──────────────


async def pick_pjs_accion(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Despacha entre añadir o eliminar PJ y muestra el picker correspondiente."""
    query = update.callback_query
    await query.answer()
    accion = query.data.removeprefix("cmppj_")
    campania_id = context.user_data["gestionar_campania_id"]

    async with async_session_maker() as session:
        if accion == "add":
            pjs = await campanias_svc.list_pjs_no_fijos(session, campania_id)
            if not pjs:
                await query.edit_message_text(
                    "No hay PJs disponibles para añadir."
                )
                return END
            await query.edit_message_text(
                "Elige un PJ para añadir como fijo:",
                reply_markup=picker_pjs(
                    [(p.id, nombre) for p, nombre in pjs], prefix="cmppjadd"
                ),
            )
            return GestionarCampania.PJ_ADD_PICK

        if accion == "rm":
            pjs = await campanias_svc.list_pjs_fijos(session, campania_id)
            if not pjs:
                await query.edit_message_text(
                    "Esta campaña no tiene PJs fijos todavía."
                )
                return END
            await query.edit_message_text(
                "Elige un PJ para eliminar de la campaña "
                "(se quitará también de las sesiones futuras):",
                reply_markup=picker_pjs(
                    [(p.id, nombre) for p, nombre in pjs], prefix="cmppjrm"
                ),
            )
            return GestionarCampania.PJ_RM_PICK

    await query.edit_message_text("Opción no reconocida.")
    return END


async def add_pj(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Añade un PJ a `campania_pjs_fijos`."""
    query = update.callback_query
    await query.answer()
    pj_id = int(query.data.removeprefix("cmppjadd_"))
    campania_id = context.user_data["gestionar_campania_id"]

    async with async_session_maker() as session:
        added = await campanias_svc.add_pj_fijo(
            session, id_campania=campania_id, id_pj=pj_id
        )
    msg = "✅ PJ añadido a la campaña." if added else "Ese PJ ya era fijo."
    await query.edit_message_text(msg)
    return END


async def rm_pj(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Elimina un PJ de `campania_pjs_fijos` y de sesiones futuras."""
    query = update.callback_query
    await query.answer()
    pj_id = int(query.data.removeprefix("cmppjrm_"))
    campania_id = context.user_data["gestionar_campania_id"]

    async with async_session_maker() as session:
        removed = await campanias_svc.remove_pj_fijo(
            session, id_campania=campania_id, id_pj=pj_id
        )
    msg = (
        "✅ PJ eliminado de la campaña y de las sesiones futuras."
        if removed
        else "Ese PJ no era fijo."
    )
    await query.edit_message_text(msg)
    return END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback /cancelar."""
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_handler() -> ConversationHandler:
    """ConversationHandler de gestión de campañas."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(_entry, pattern=r"^caja_campania_listar$"),
        ],
        states={
            GestionarCampania.PICK: [
                CallbackQueryHandler(pick_campania, pattern=r"^cmppick_\d+$"),
            ],
            GestionarCampania.ACCION: [
                CallbackQueryHandler(
                    pick_accion, pattern=r"^cmpacc_(addsesion|pjs|info)$"
                ),
            ],
            GestionarCampania.PJS: [
                CallbackQueryHandler(pick_pjs_accion, pattern=r"^cmppj_(add|rm)$"),
            ],
            GestionarCampania.PJ_ADD_PICK: [
                CallbackQueryHandler(add_pj, pattern=r"^cmppjadd_\d+$"),
            ],
            GestionarCampania.PJ_RM_PICK: [
                CallbackQueryHandler(rm_pj, pattern=r"^cmppjrm_\d+$"),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="gestionar_campania",
        persistent=False,
    )
