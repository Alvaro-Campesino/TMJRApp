"""Estados de los ConversationHandlers del bot."""
from enum import IntEnum, auto


class CrearSesion(IntEnum):
    DM_BIO = auto()       # si la persona no es DM, le pedimos biografía
    FECHA = auto()
    PLAZAS = auto()
    CONFIRMAR = auto()


class UnirseSesion(IntEnum):
    PJ_NOMBRE = auto()    # si la persona no es PJ, le pedimos nombre
    PJ_DESC = auto()
    CONFIRMAR = auto()
