from telegram import Update
from telegram.ext import CallbackContext
from services import partidas as ses, premisas as pre
from config.settings import logger
from config.states import States
from constants.enums.tables import TableName as tn
from constants.strings.partidas import *
from views.basic import mensaje_view, error_view
from views.partidas.leer import lista_view, detalle_view


async def partida_lista(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await mensaje_view(query, CARGANDO_LISTA)
    try:
        sesiones = ses.get_partidas(details=True, soon=True)
        titulos = []
        for sesion in sesiones:
            aventura = sesion[tn.AVENTURA.value]
            premisa = aventura[tn.PREMISA.value]
            title = f"{premisa['titulo']}, {premisa['sistema']}"
            titulos.append(title)
        if titulos:
            await lista_view(query, titulos)
        else:
            await mensaje_view(query, ZERO_RESULTS)
    except Exception as e:
        await error_view(query, ERROR_LISTA, e)
    return States.PARTIDA_LISTA.value


async def partida_detalle(update: Update, context: CallbackContext) -> int:
    partida_id = 1  # TODO: sacar esto de caché o algo así
    logger.info(f"Detalles de la partida: {partida_id}")
    query = update.callback_query
    await mensaje_view(query, CARGANDO_DETALLES)
    try:
        sesion = ses.get_partida(partida_id, details=True)[0]
        logger.info(f"Sesión id: {sesion['id']}")
        if not sesion:
            # TODO: esto debería llevar a una vista de error_view para poder volver
            await mensaje_view(query, NOT_FOUND)
        else:
            await detalle_view(query, sesion)
    except Exception as e:
        await error_view(query, ERROR_DETALLES, e)
    return States.PARTIDA_DETALLES.value


async def partida_unirse(update: Update, context: CallbackContext) -> int:
    logger.info("Unirse a partida")
    await mensaje_view("Todavía no puedes hacer esto :(")
    return States.PARTIDA_UNIRSE.value
