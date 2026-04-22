from enum import Enum, auto, unique


@unique
class States(Enum):
    MAIN_MENU = auto()
    # VER PARTIDAS
    PARTIDA_LISTA = auto()
    PARTIDA_DETALLES = auto()
    PARTIDA_UNIRSE = auto()
    # CREAR PARTIDAS
    DIRIGIR = auto()
    DIRIGIR_PREMISA_LISTA = auto()
    DIRIGIR_PREMISA_DETALLE = auto()
    DIRIGIR_PREMISA_EDITAR = auto()
    DIRIGIR_TITULO = auto()
    DIRIGIR_SISTEMA = auto()
    DIRIGIR_DESCRIPCION = auto()
    DIRIGIR_AVISO_CONTENIDO = auto()
    DIRIGIR_DETALLES = auto()
    DIRIGIR_EDITAR_DATO = auto()
    DIRIGIR_LUGAR = auto()
    DIRIGIR_PLAZAS = auto()
    DIRIGIR_PLAZAS_EDITAR = auto()
    DIRIGIR_NUM_SESIONES = auto()
    DIRIGIR_FECHAS_DETALLE = auto()
    DIRIGIR_FECHAS_EDITAR = auto()
    DIRIGIR_FECHAS_UNA = auto()
    DIRIGIR_SUBIR = auto()
