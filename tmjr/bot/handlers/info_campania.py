"""Caja Campaña → Info: explica brevemente cómo funcionan las campañas."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


INFO_CAMPANIA = (
    "🏰 <b>Cómo funcionan las campañas</b>\n\n"
    "Una <b>campaña</b> es una serie de sesiones que comparten una misma "
    "<b>premisa</b> y un grupo de PJs fijos.\n\n"
    "<b>Crear</b>\n"
    "1. 🏰 Campaña → Crear.\n"
    "2. Eliges (o creas) la premisa.\n"
    "3. Configuras la <b>primera sesión</b> (juego, fecha, hora, lugar, "
    "plazas, descripción) — sigue el flujo normal de crear sesión.\n"
    "4. La sesión se publica como tarjeta en el canal con el indicador "
    "🏰 Campaña.\n\n"
    "<b>PJs fijos</b>\n"
    "• Quienes pulsan 🙋 Apuntarse en la <b>primera sesión</b> quedan "
    "automáticamente como PJs fijos de la campaña.\n"
    "• Cuando publicas una <b>nueva sesión</b> de la campaña, los PJs fijos "
    "quedan pre-apuntados y reciben un DM avisándoles. Si alguno no puede "
    "acudir, basta con pulsar 🚪 Borrarme en esa tarjeta — solo se borra de "
    "esa sesión, sigue siendo fijo.\n"
    "• Como DM puedes añadir o eliminar PJs fijos manualmente desde "
    "🏰 Campaña → Listar → Gestionar PJs.\n\n"
    "<b>Añadir nueva sesión</b>\n"
    "🏰 Campaña → Listar → elige campaña → ➕ Añadir sesión, y luego usa "
    "/crear_sesion: la sesión se asocia automáticamente a la campaña."
)


async def info_campania(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el texto explicativo de cómo funcionan las campañas."""
    query = update.callback_query
    if query is not None:
        await query.answer()
    await update.effective_message.reply_text(
        INFO_CAMPANIA, parse_mode="HTML"
    )
