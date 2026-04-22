from config.states import States
from constants.strings.aventuras import DIRIGIDO_LISTA
from utils.formater import *
from views.basic import new_button
from telegram import CallbackQuery
from telegram import (
    InlineKeyboardMarkup,
)


async def premisa_lista_view(query: CallbackQuery, premisas):
    keyboard = [[new_button(title, States.PARTIDA_DETALLES.name)] for title in premisas]
    await query.edit_message_text(
        text=DIRIGIDO_LISTA,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
