"""/start — registra a la persona y muestra el menú principal.

Payloads de deep-link soportados:
- `obj_<kind>_<id>`  → muestra la ficha del objeto referenciado.
- `apuntar_<id>`     → llega cuando el usuario pulsó "Apuntarse" en el
  canal sin estar registrado. Tras crearle la Persona, le explicamos
  cómo seguir (volver al canal y pulsar de nuevo Apuntarse).
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.bot.object_links import format_object, parse_object_payload
from tmjr.db import async_session_maker
from tmjr.services import personas as svc

from ..keyboards import menu_cajas


def _parse_apuntar_payload(payload: str) -> int | None:
    """Devuelve el sesion_id si el payload es `apuntar_<int>`, si no None."""
    if not payload.startswith("apuntar_"):
        return None
    try:
        return int(payload.removeprefix("apuntar_"))
    except ValueError:
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja /start con o sin payload.

    - Sin payload → registra (idempotente) y enseña el menú de cajas.
    - Con `obj_<kind>_<id>` → registra silenciosamente y muestra la ficha
      del objeto.
    - Con `apuntar_<id>` → registra y le pide volver al canal a pulsar
      Apuntarse de nuevo.
    """
    user = update.effective_user
    if user is None:
        return

    nombre = user.full_name or user.username or f"persona_{user.id}"
    async with async_session_maker() as session:
        persona, created = await svc.get_or_create_persona(
            session, telegram_id=user.id, nombre=nombre
        )

        args = context.args or []
        if args:
            payload = args[0]

            # apuntar_<id> → viene del toast del botón Apuntarse en canal.
            sesion_id = _parse_apuntar_payload(payload)
            if sesion_id is not None:
                cabecera = (
                    f"¡Hola, {persona.nombre}! Te he registrado."
                    if created
                    else f"¡Hola de nuevo, {persona.nombre}!"
                )
                await update.effective_message.reply_text(
                    f"{cabecera}\n\n"
                    f"Ya estás registrado/a. Vuelve a la tarjeta de la "
                    f"sesión #{sesion_id} en el canal y pulsa "
                    f"<b>🙋 Apuntarse</b> otra vez para inscribirte.",
                    parse_mode="HTML",
                    reply_markup=menu_cajas(),
                )
                return

            # obj_<kind>_<id> → ficha de objeto.
            parsed = parse_object_payload(payload)
            if parsed is not None:
                kind, obj_id = parsed
                info = await format_object(session, kind, obj_id)
                if info is not None:
                    await update.effective_message.reply_text(
                        info, parse_mode="HTML"
                    )
                    return
                # Objeto no encontrado: continuamos al saludo normal con aviso.
                await update.effective_message.reply_text(
                    f"No he podido encontrar ese {kind}."
                )

    saludo = (
        f"¡Hola, {persona.nombre}! Te he registrado."
        if created
        else f"¡Hola de nuevo, {persona.nombre}!"
    )
    await update.effective_message.reply_text(
        f"{saludo}\n\nElige una caja del teclado o usa /help para ver qué puedo hacer.",
        reply_markup=menu_cajas(),
    )
