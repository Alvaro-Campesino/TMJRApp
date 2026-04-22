from telegram import Update
from telegram.ext import CallbackContext
from config.states import States
from controllers.partida import *
from menus.basic_options import desconocido


async def lista(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    match query.data:
        case States.PARTIDA_DETALLES.name:
            return await partida_detalle(update, context)
        case _:
            return await desconocido(update, context)


async def detalles(update: Update, context: CallbackContext) -> int:
    # Apuntarse o volver a lista
    query = update.callback_query
    match query.data:
        case States.PARTIDA_UNIRSE.name:
            return await partida_unirse(update, context)
        case States.PARTIDA_LISTA.name:
            return await partida_lista(update, context)
        case _:
            return await desconocido(update, context)
