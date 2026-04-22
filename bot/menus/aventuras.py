from telegram import Update
from telegram.ext import CallbackContext
from config.states import States
from controllers.aventura import *
from menus.basic_options import desconocido


async def crear(update: Update, context: CallbackContext) -> int:
    # Crear partida
    query = update.callback_query
    match query.data:
        case States.DIRIGIR_PREMISA_LISTA.name:
            return await dirigir_get_premisa(update, CallbackContext)
        case States.DIRIGIR_TITULO.name:
            return await dirigir_titulo(update, CallbackContext)
        case _:
            return await desconocido(update, context)
