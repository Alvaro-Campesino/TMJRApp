"""Estados de los ConversationHandlers del bot."""
from enum import IntEnum, auto


class CrearSesion(IntEnum):
    DM_BIO = auto()                # si no es DM, pedimos biografía
    PREMISA_NOMBRE = auto()        # título de la partida
    PREMISA_DESC = auto()          # descripción (opcional, /skip)
    PREMISA_JUEGO = auto()         # selección de juego del catálogo del DM
    NUEVO_JUEGO_NOMBRE = auto()    # texto del nombre del juego nuevo
    CONFIRMAR_NUEVO_JUEGO = auto() # confirmación antes de crear en catálogo
    FECHA = auto()
    PLAZAS = auto()
    SESION_DESC = auto()           # nota opcional específica de esta sesión


class UnirseSesion(IntEnum):
    PJ_NOMBRE = auto()    # si la persona no es PJ, le pedimos nombre
    PJ_DESC = auto()
    CONFIRMAR = auto()
