"""/start — registra a la persona y muestra el menú principal.

Reglas de seguridad:
- El registro NUEVO sólo se acepta con payload `invitacion_<token>`
  válido (token activo, no revocado, no caducado). Sin token o con
  token inválido, se muestra el mensaje "pide la invitación del pin".
- Los demás payloads (`obj_<kind>_<id>`, `apuntar_<id>`) sólo aplican
  a personas YA registradas — no se auto-registra a nadie por ellos.
"""
from __future__ import annotations



from telegram import Update
from telegram.ext import ContextTypes

from tmjr.bot.menu_dm import fijar_menu_principal
from tmjr.bot.object_links import format_object, parse_object_payload
from tmjr.db import async_session_maker
from tmjr.services import personas as svc
from tmjr.services import suscripciones as sub_svc
from tmjr.services import tokens as tokens_svc

from ..keyboards import boton_suscripcion_premisa, menu_cajas
import logging


_PIDE_INVITACION = (
    "🔒 Para usar este bot necesitas la invitación que el admin tiene "
    "fijada en el canal. Pulsa el botón <b>🔑 Unirme al bot</b> del "
    "mensaje fijado y vuelve."
)


def _parse_apuntar_payload(payload: str) -> int | None:
    """Devuelve el sesion_id si el payload es `apuntar_<int>`, si no None."""
    if not payload.startswith("apuntar_"):
        return None
    try:
        return int(payload.removeprefix("apuntar_"))
    except ValueError:
        return None


def _parse_invitacion_payload(payload: str) -> str | None:
    """Devuelve el token si el payload es `invitacion_<token>`, si no None."""
    if not payload.startswith("invitacion_"):
        return None
    token = payload.removeprefix("invitacion_")
    return token or None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja /start con o sin payload.

    Flujo según estado:
    - Persona registrada → ignora la falta de token; saluda y aplica el
      payload (`obj_*` muestra ficha, `apuntar_*` pide volver al canal).
    - Persona NO registrada:
        * `invitacion_<token>` válido → registra + saluda + menú.
        * Cualquier otro payload o ninguno → "pide la invitación".
    """
    logging.basicConfig(level = logging.DEBUG)
    logging.error("⭐⭐⭐ EL HANDLER DE START SE HA EJECUTADO ⭐⭐⭐")
    await update.effective_message.reply_text("DEBUG: /start recibido")
    user = update.effective_user
    if user is None:
        return

    nombre = user.full_name or user.username or f"persona_{user.id}"
    args = context.args or []
    payload = args[0] if args else None

    async with async_session_maker() as session:
        persona = await svc.get_persona_by_telegram(session, user.id)

        if persona is None:
            # Solo el deep-link de invitación crea persona.
            token_str = _parse_invitacion_payload(payload) if payload else None
            if token_str is None:
                await update.effective_message.reply_text(
                    _PIDE_INVITACION, parse_mode="HTML"
                )
                return
            tok = await tokens_svc.validar(session, token_str)
            if tok is None:
                await update.effective_message.reply_text(
                    "🔒 Ese enlace de invitación ya no es válido. "
                    "Vuelve al pin del canal para obtener uno nuevo.",
                )
                return
            persona, _created = await svc.get_or_create_persona(
                session, telegram_id=user.id, nombre=nombre
            )
            persona.registrado_via_token_id = tok.id
            await session.commit()
            await session.refresh(persona)
            await update.effective_message.reply_text(
                f"¡Hola, {persona.nombre}! Te he registrado.\n\n"
                f"Elige una caja del teclado o usa el botón ❓ Ayuda del "
                f"mensaje fijado para ver qué puedo hacer.",
                reply_markup=menu_cajas(),
            )
            await fijar_menu_principal(context.bot, persona)
            return

        # A partir de aquí la persona ya está registrada.
        if payload is not None:
            sesion_id = _parse_apuntar_payload(payload)
            if sesion_id is not None:
                await update.effective_message.reply_text(
                    f"¡Hola de nuevo, {persona.nombre}!\n\n"
                    f"Ya estás registrado/a. Vuelve a la tarjeta de la "
                    f"sesión #{sesion_id} en el canal y pulsa "
                    f"<b>🙋 Apuntarse</b> otra vez para inscribirte.",
                    parse_mode="HTML",
                    reply_markup=menu_cajas(),
                )
                return

            parsed = parse_object_payload(payload)
            if parsed is not None:
                kind, obj_id = parsed
                info = await format_object(session, kind, obj_id)
                if info is None:
                    await update.effective_message.reply_text(
                        f"No he podido encontrar ese {kind}."
                    )
                    return
                # Para premisas, añadimos el botón toggle de suscripción
                # (mismo callback que en el listado público de premisas).
                reply_markup = None
                if kind == "premisa":
                    sub_actual = await sub_svc.is_subscribed(
                        session, persona.id, obj_id
                    )
                    reply_markup = boton_suscripcion_premisa(
                        obj_id, suscrito=sub_actual is not None
                    )
                await update.effective_message.reply_text(
                    info, parse_mode="HTML", reply_markup=reply_markup
                )
                return

            # Payload `invitacion_<token>` de alguien ya registrado: solo
            # saludamos. No revalidamos ni reasignamos el token.

    await update.effective_message.reply_text(
        f"¡Hola de nuevo, {persona.nombre}!\n\n"
        "Elige una caja del teclado o usa el botón ❓ Ayuda del mensaje "
        "fijado para ver qué puedo hacer.",
        reply_markup=menu_cajas(),
    )
    await fijar_menu_principal(context.bot, persona)
