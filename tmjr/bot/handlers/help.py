"""/help — explica el bot y los comandos disponibles."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = (
    "*TMJR — Organizador de partidas de rol*\n\n"
    "Objetivo: Este bot permite que nos coordienmos en Telegram para crear y apuntarnos a "
    "sesiones de rol sin perderse entre mensajes.\n\n"
    "*Cómo funciona*\n"
    "1. Usa /start para registrarte (creas tu perfil de *Persona* _Jugadora_).\n"
    "2. Si quieres dirigir, al crear una sesión damos de alta tu perfil de *DM*.\n"
    "3. Al crear una sesión te pediremos que uses una *Premisa* esto es el nombre de la aventura con su descripción.\n"    
    "4. Como *DM* tendrás tus juegos favoritos disponibles, puedes gestionar tu propia lista, quitando o añadiendo. \n"
    "5. También puedes dar de alta una campaña, si tu *Sesión* no va a ser un _oneshot_.\n"
    "6. Tenemos una lista de juegos de rol conocidos, si el tuyo no está, puedes añadirlo.\n"
    "7. Cualquiera puede consultar las próximas *Sesiones* de rol y apuntarse"
    "8. Cada sesión se publica como tarjeta en el canal con un botón "
    "🙋 Apuntarse.\n\n"
    "*Cómo navegar*\n"
    "• Cajas del teclado: 👤 Persona, 🎲 Sesión, 📜 Premisa, 🏰 Campaña, 🎮 Juegos. "
    "Cada caja abre un submenú con Crear / Listar / Editar.\n"
    "• Comandos directos (pulsa `/` para ver la lista completa).\n\n"
    "Las opciones marcadas con 🚧 todavía no están listas."
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT, parse_mode="Markdown")
