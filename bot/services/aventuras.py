from services.common import api_request


# Métodos crud para aventuras
def get_aventuras():
    """Obtiene la lista de aventuras"""
    endpoint = f"aventura"
    return api_request("GET", endpoint)


def get_aventura(id: int):
    """Obtiene una aventura dado su id."""
    endpoint = f"aventura/{id}"
    return api_request("GET", endpoint)
