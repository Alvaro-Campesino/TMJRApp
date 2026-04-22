from services.common import api_request


# Métodos crud para partidas
def get_partidas(details: bool = False, soon: bool = False):
    endpoint = f"sesion?details={details}&soon={soon}"
    return api_request("GET", endpoint)


def get_partidas_week(details: bool = False):
    """Lista de partidas de la semana."""
    endpoint = f"sesion/this-week?details={details}"
    return api_request("GET", endpoint)


def get_partida(id: int, details: bool = False):
    endpoint = f"sesion/{id}?details={details}"
    return api_request("GET", endpoint)
