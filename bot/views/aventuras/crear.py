from config.states import States
from constants.strings.aventuras import CREAR_INICIO
from constants.strings.basic import SI, NO, NO_DISPONIBLE
from views.basic import new_button
from telegram import CallbackQuery
from telegram import (
    InlineKeyboardMarkup,
)


async def dirigir_inicio_view(query: CallbackQuery):
    keyboard = [
        [
            new_button(f"{SI} {NO_DISPONIBLE}", States.DIRIGIR_PREMISA_LISTA.value),
            new_button(NO, States.DIRIGIR_TITULO.value),
        ],
    ]
    await query.edit_message_text(
        text=CREAR_INICIO,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
