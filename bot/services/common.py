from config.settings import logger, API_BASE_URL
import requests
from enum import Enum


def api_request(method: str, endpoint: str, data=None):
    """Realiza una solicitud a la API y maneja la respuesta."""
    url = f"{API_BASE_URL}/{endpoint}"
    response = requests.request(method, url, json=data)
    logger.info(f"Response: {response}")
    if response.ok:
        return response.json()["data"]
    else:
        raise Exception(f"Error en la solicitud: {response.status_code}")


class Methods(Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
