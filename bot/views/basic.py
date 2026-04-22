from telegram import CallbackQuery, InlineKeyboardButton


def new_button(text: str, callback_name: str) -> InlineKeyboardButton:
    """Helper function to create a button."""
    return InlineKeyboardButton(text, callback_data=callback_name)


async def mensaje_view(query: CallbackQuery, message: str):
    await query.edit_message_text(text=message)


async def error_view(query: CallbackQuery, message: str, error: str):
    await mensaje_view(query, f"{message}: {error}")
