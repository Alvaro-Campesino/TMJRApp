from pydantic import BaseModel
import random


class FiltroContenido(BaseModel):
    lineas: list[str] | None = None
    velos: list[str] | None = None


class Usuaria(BaseModel):
    id: int = 0
    telegram_id: int
    filtro_contenido: FiltroContenido | None = None
    peticion: str | None = None


class UsuariaUpdate(Usuaria):
    telegram_id: int | None = None


class UsuariaSelect(BaseModel):
    id: int = 0
    filtro_contenido: FiltroContenido | None = None
    peticion: str | None = None


generos = [
    ["la", "usuaria", "las", "usuarias"],
    ["el", "usuario", "los", "usuarios"],
    ["le", "usuarie", "les", "usuaries"],
]


def random_user_gender(
    has_article: bool = True, is_capital: bool = True, is_plural: bool = False
) -> str:
    gender = random.choice(generos)
    plural_mod = 2 if is_plural else 0
    display = (
        f"{gender[0 + plural_mod]} {display}" if has_article else gender[1 + plural_mod]
    )
    return display.capitalize() if is_capital else display
