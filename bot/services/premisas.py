from services.common import api_request, Methods


def get_premisas():
    """Obtiene una premisa dado su id"""
    endpoint = f"premisa"
    api_request(Methods.GET, endpoint)


def get_premisa(id: int):
    """Obtiene una premisa dado su id"""
    endpoint = f"premisa/{id}"
    api_request(Methods.GET, endpoint)
