from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ─────────────────────── ReplyKeyboard persistente ────────────────────────


CAJA_PERSONA = "👤 Persona"
CAJA_SESION = "🎲 Sesión"
CAJA_PREMISA = "📜 Premisa"
CAJA_CAMPANIA = "🏰 Campaña"
CAJA_JUEGOS = "🎮 Juegos"

CAJAS = (CAJA_PERSONA, CAJA_SESION, CAJA_PREMISA, CAJA_CAMPANIA, CAJA_JUEGOS)


def menu_cajas() -> ReplyKeyboardMarkup:
    """ReplyKeyboard persistente con las 5 cajas de objetos."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(CAJA_PERSONA), KeyboardButton(CAJA_SESION)],
            [KeyboardButton(CAJA_PREMISA), KeyboardButton(CAJA_CAMPANIA)],
            [KeyboardButton(CAJA_JUEGOS)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ─────────────────────── Submenú inline por objeto ────────────────────────
# Cada acción es (label, action, disponible).
# El callback que se emite es `caja_<obj>_<action>`.

_SUBMENUS: dict[str, list[tuple[str, str, bool]]] = {
    "persona":  [("Ver mi perfil", "ver", True),  ("Editar", "editar", False)],
    "sesion":   [("Crear", "crear", True),  ("Listar", "listar", True),  ("Editar", "editar", False)],
    "premisa":  [("Crear", "crear", False), ("Listar", "listar", False), ("Editar", "editar", False)],
    "campania": [("Crear", "crear", False), ("Listar", "listar", False), ("Editar", "editar", False)],
    "juegos":   [("Listar", "listar", True), ("Crear", "crear", False), ("Editar", "editar", False)],
}


def submenu_objeto(obj: str) -> InlineKeyboardMarkup:
    """Submenú con Crear / Listar / Editar para el objeto. Marca 🚧 las no disponibles."""
    rows = []
    for label, action, disponible in _SUBMENUS[obj]:
        text = label if disponible else f"{label} 🚧"
        rows.append(
            [InlineKeyboardButton(text, callback_data=f"caja_{obj}_{action}")]
        )
    return InlineKeyboardMarkup(rows)


# ─────────────────────── Inline keyboards específicos ─────────────────────


def tarjeta_sesion(sesion_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🙋 Apuntarse", callback_data=f"apuntar_{sesion_id}")],
        ]
    )


def confirmar_cancelar(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data=f"{prefix}_ok"),
                InlineKeyboardButton("❌ Cancelar", callback_data=f"{prefix}_no"),
            ]
        ]
    )


def juegos_del_dm(juegos: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """Teclado con los juegos del DM + opción 'Añadir nuevo'.

    `juegos`: lista de tuples (id, nombre).
    Callbacks: `juego_<id>` para los existentes, `juego_nuevo` para añadir.
    """
    rows = [
        [InlineKeyboardButton(nombre, callback_data=f"juego_{jid}")]
        for jid, nombre in juegos
    ]
    rows.append([InlineKeyboardButton("➕ Añadir nuevo", callback_data="juego_nuevo")])
    return InlineKeyboardMarkup(rows)


def confirmar_juego_nuevo(nombre: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"✅ Crear '{nombre}'", callback_data="nuevo_juego_ok"
                ),
                InlineKeyboardButton("❌ Cancelar", callback_data="nuevo_juego_no"),
            ]
        ]
    )
