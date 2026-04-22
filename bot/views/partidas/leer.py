from config.states import States
from constants.enums.tables import TableName as tn
from constants.strings.format import SL
from constants.strings.partidas import PROXIMAS
from config.settings import logger
from config.states import States
from utils.formater import *
from datetime import datetime
from views.basic import new_button
from schemas.aventura import plazas_disponibles
from telegram import CallbackQuery
from telegram import (
    InlineKeyboardMarkup,
)


def partida_descripcion(sesion) -> str:
    """Genera la descripción de la partida."""
    aventura = sesion[tn.AVENTURA.value]
    premisa = aventura[tn.PREMISA.value]
    num_sesiones = len(aventura["Sesion"])
    text = bold(premisa["titulo"]) + SL
    if premisa["sistema"]:
        text += "Sistema: " + premisa["sistema"] + SL
    text += SL + "Lugar: " + aventura["lugar"] + SL
    fecha = datetime.strptime(sesion["fecha"], "%Y-%m-%dT%H:%M:%S")
    text += "Día y hora: " + fecha.strftime("%d/%m %H:%M") + SL
    if aventura["abierta_inscripcion"]:
        text += f"{plazas_disponibles(aventura)} plazas disponibles" + SL
    else:
        text += "*Inscripciones cerradas*" + SL
    if num_sesiones > 1:
        text += f"{num_sesiones} sesiones" + SL
    else:
        text += "Sesión única" + SL
    if premisa["descripcion"]:
        text += premisa["descripcion"] + SL
    return text


async def detalle_view(query: CallbackQuery, sesion):
    logger.info("vista detalle")
    descripcion = partida_descripcion(sesion)
    logger.info("vista detalle")
    await query.edit_message_text(descripcion, parse_mode="HTML")
    # botones para apuntarse o volver a la lista
    # TODO: guardar sesion['id'] en caché?
    keyboard = [
        [new_button("Apuntarse", States.PARTIDA_UNIRSE.name)],
        [new_button("Volver a la lista", States.PARTIDA_LISTA.name)],
    ]
    await query.message.reply_text(
        "¿Quieres apuntarte?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def lista_view(query: CallbackQuery, titles: list[str]):
    # TODO: Guardar sesion['id'] en caché al pulsar el botón? cómo?
    keyboard = [[new_button(title, States.PARTIDA_DETALLES.name)] for title in titles]
    await query.edit_message_text(
        PROXIMAS,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
