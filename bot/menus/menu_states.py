from config.states import States
from telegram.ext import CallbackQueryHandler
from menus.main_menu import main_menu
from menus.partidas import lista, detalles
from menus.aventuras import crear

# Todos los estados que puede tener el bot y sus métodos controladores que manejan las respuestas
MENU_STATES = {
    States.MAIN_MENU.value: [CallbackQueryHandler(main_menu)],
    States.PARTIDA_LISTA.value: [CallbackQueryHandler(lista)],
    States.PARTIDA_DETALLES.value: [CallbackQueryHandler(detalles)],
    States.DIRIGIR.value: [CallbackQueryHandler(crear)],
}
