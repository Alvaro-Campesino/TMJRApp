from telegram import Update
from telegram.ext import CallbackContext
from config.settings import logger
from config.states import States
from constants.strings.aventuras import *
from services.premisas import get_premisas
from views.aventuras.crear import dirigir_inicio_view
from views.premisas.leer import premisa_lista_view
from views.basic import mensaje_view, error_view


async def dirigir_inicio(update: Update, context: CallbackContext) -> None:
    logger.info(f"{update.effective_user.username} quiere dirigir")
    # TODO: Empezar a guardar cosas en caché?
    await dirigir_inicio_view(update.callback_query)
    return States.DIRIGIR


async def dirigir_titulo(update: Update, context: CallbackContext) -> None:
    logger.info("Escribir el título de la partida")
    query = update.callback_query
    await mensaje_view(query, CREAR_TITULO)
    try:
        # Aquí hacer que saque el texto que se escriba.
        await mensaje_view(query, "En proceso")
    except Exception as e:
        await error_view(query, ERROR_AVE, e)


async def dirigir_get_premisa(update: Update, context: CallbackContext) -> None:
    # Si ha dirigido antes, buscar en la base de datos
    logger.info("Lista de partidas dirigidas")
    query = update.callback_query
    await mensaje_view(query, CARGANDO_LISTA_DIRIGIDAS)
    try:
        premisas = get_premisas()
        logger.info(f"Cargadas: {premisas.size}")
        if not premisas:
            await mensaje_view(query, NOT_FOUND)
            # Aquí cargar botón de vuelta
        else:
            await premisa_lista_view(query, premisas)
    except Exception as e:
        await error_view(query, ERROR_LISTA, e)
    return States.DIRIGIR_PREMISA_LISTA.value
