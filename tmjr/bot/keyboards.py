from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def menu_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎲 Crear sesión", callback_data="crear_sesion")],
            [InlineKeyboardButton("🙋 Unirse a una sesión", callback_data="unirse_sesion")],
        ]
    )


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
