"""Estados de los ConversationHandlers del bot."""
from enum import IntEnum, auto


class CrearSesion(IntEnum):
    DM_BIO = auto()                # si no es DM, pedimos biografía
    ELEGIR_PREMISA = auto()        # 3 botones: mis premisas / almacenadas / crear nueva
    PICK_PREMISA_PROPIA = auto()   # picker de premisas del DM
    PICK_PREMISA_GLOBAL = auto()   # picker de premisas globales (no del DM)
    CONFIRMAR_JUEGO = auto()       # heredamos el juego de la premisa, opción a cambiar
    PREMISA_NOMBRE = auto()        # título de la partida (rama "crear nueva")
    CONFIRMAR_DUP_PREMISA = auto() # picker de candidatos similares (premisa)
    PREMISA_DESC = auto()          # descripción (opcional, /skip)
    PREMISA_JUEGO = auto()         # selección de juego del catálogo del DM
    NUEVO_JUEGO_NOMBRE = auto()    # texto del nombre del juego nuevo
    CONFIRMAR_DUP_JUEGO = auto()   # picker de candidatos similares (juego)
    CONFIRMAR_NUEVO_JUEGO = auto() # confirmación antes de crear en catálogo
    SESION_NOMBRE_PICK = auto()    # 2 botones: usar nombre de premisa / poner otro
    SESION_NOMBRE_OTRO = auto()    # esperamos texto con nombre alternativo
    FECHA = auto()
    HORA = auto()                  # picker de hora (12-23) tras elegir fecha
    MINUTOS = auto()               # picker de minutos (00/15/30/45) tras hora
    PLAZAS = auto()
    PLAZAS_MINIMAS = auto()        # mínimo de jugadores para que la sesión "se haga" (0..plazas)
    LUGAR_RESPUESTA = auto()       # esperamos texto/botón con el lugar de la sesión
    SESION_DESC = auto()           # nota opcional específica de esta sesión


class UnirseSesion(IntEnum):
    PJ_DESC = auto()      # descripción del PJ + límites de contenido (1ª vez)
    CONFIRMAR = auto()


class CrearPremisa(IntEnum):
    NOMBRE = auto()                # título de la premisa
    CONFIRMAR_DUP_PREMISA = auto() # picker de candidatos similares (premisa)
    DESC = auto()                  # descripción (opcional, /skip)
    JUEGO = auto()                 # selección de juego del catálogo del DM
    NUEVO_JUEGO_NOMBRE = auto()    # texto del nombre del juego nuevo
    CONFIRMAR_DUP_JUEGO = auto()   # picker de candidatos similares (juego)
    CONFIRMAR_NUEVO_JUEGO = auto() # confirmación antes de crear en catálogo


class EditarPerfil(IntEnum):
    NOMBRE = auto()    # nuevo nombre de la persona


class CrearPerfilDM(IntEnum):
    BIO = auto()       # biografía inicial del DM (o /skip)


class EditarPerfilDMBio(IntEnum):
    BIO = auto()       # nueva biografía del DM (o /skip para vaciarla)


class EditarSesion(IntEnum):
    PICK = auto()              # picker con las sesiones futuras del DM
    CAMPO = auto()             # submenú con los campos editables
    NOMBRE = auto()
    DESC = auto()
    LUGAR = auto()
    FECHA = auto()
    HORA = auto()
    MINUTOS = auto()
    PLAZAS = auto()
    PLAZAS_MINIMAS = auto()
    CONFIRMAR_BORRAR = auto()  # confirmación antes de borrar la sesión


class GestionarCampania(IntEnum):
    PICK = auto()              # picker con las campañas del DM
    ACCION = auto()             # submenú de acciones
    PJS = auto()                # submenú gestión PJs
    PJ_ADD_PICK = auto()       # picker para añadir PJ
    PJ_RM_PICK = auto()        # picker para eliminar PJ


class EditarPremisa(IntEnum):
    PICK = auto()              # picker con las premisas del DM
    CAMPO = auto()             # submenú con los campos editables
    NOMBRE = auto()
    DESC = auto()
    AVISO = auto()
    JUEGO = auto()             # picker juegos del DM + 'Añadir nuevo'
    NUEVO_JUEGO_NOMBRE = auto()
    CONFIRMAR_NUEVO_JUEGO = auto()
