"""/help — explica el bot y los comandos disponibles."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = (
    "*TMJR — bot para organizar partidas de rol*\n\n"
    "Objetivo: que un grupo se coordine en Telegram para crear y apuntarse a "
    "sesiones de rol sin perderse entre mensajes.\n\n"
    "*Cómo funciona*\n"
    "1. Usa /start para registrarte (creas tu *Persona*).\n"
    "2. Si quieres dirigir, al crear una sesión damos de alta tu perfil de *DM*.\n"
    "3. Si te apuntas, damos de alta tu *PJ* (jugador).\n"
    "4. Cada sesión se publica como tarjeta en el canal con un botón "
    "🙋 Apuntarse.\n\n"
    "*Cómo navegar*\n"
    "• Cajas del teclado: 👤 Persona, 🎲 Sesión, 📜 Premisa, 🏰 Campaña, 🎮 Juegos. "
    "Cada caja abre un submenú con Crear / Listar / Editar.\n"
    "• Comandos directos (pulsa `/` para ver la lista completa).\n\n"
    "Las opciones marcadas con 🚧 todavía no están listas."
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT, parse_mode="Markdown")
