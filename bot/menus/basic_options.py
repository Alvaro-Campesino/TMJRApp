from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from config.states import States


async def desconocido(update: Update, context: CallbackContext) -> int:
    await update.callback_query.message.reply_text(
        text="Opción desconocida",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Volver al menú", callback_data=States.MAIN_MENU.name
                    )
                ]
            ]
        ),
    )
    return States.MAIN_MENU.value


async def cancelar(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text(
        "Operación cancelada.\nVuelve a escribir /inicio para comenzar"
    )
    return ConversationHandler.END
