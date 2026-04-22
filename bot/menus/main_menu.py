from telegram import Update
from telegram.ext import CallbackContext
from config.states import States
from config.settings import logger
from controllers.partida import partida_lista
from controllers.aventura import dirigir_inicio
from views.start import start_view
from menus.basic_options import desconocido


async def main_menu(update: Update, context: CallbackContext) -> int:
    logger.info("Main menu")
    query = update.callback_query
    match query.data:
        case States.MAIN_MENU.name:
            return await start_view(update, context)
        case States.PARTIDA_LISTA.name:
            return await partida_lista(update, context)
        case States.DIRIGIR.name:
            return await dirigir_inicio(update, context)
        case _:
            return await desconocido(update, context)
