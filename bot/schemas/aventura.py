AVENTURA_DEFAULT = {
    "Premisa": {
        "id": None,
        "titulo": "",
        "sistema": None,
        "descripcion": None,
        "aviso_contenido": None,
    },
    "lugar": None,
    "plazas_totales": 5,
    "plazas_ocupadas": 0,
    "plazas_sin_reserva": 1,
    "Sesion": [{"numero": 1, "fecha": None}],
}


def plazas_disponibles(aventura):
    plazas_totales = int(aventura["plazas_totales"])
    plazas_ocupadas = int(aventura["plazas_ocupadas"])
    plazas_sin_reserva = int(aventura["plazas_sin_reserva"])
    return plazas_totales - plazas_ocupadas - plazas_sin_reserva
