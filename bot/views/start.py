from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from config.states import States
from config.settings import logger


async def start_view(update: Update, context: CallbackContext) -> int:
    keyboard = [
        [
            InlineKeyboardButton(
                "Ver próximas partidas", callback_data=States.PARTIDA_LISTA.name
            )
        ],
        [InlineKeyboardButton("Dirigir partida", callback_data=States.DIRIGIR.name)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    logger.info("Iniciando bot")
    logger.info("Usuario: %s", update.message.from_user.username)
    await update.message.reply_text(
        "¡Hola! Elige una opción", reply_markup=reply_markup
    )
    return States.MAIN_MENU.value
