from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
)
from config.settings import TOKEN
from menus.menu_states import MENU_STATES
from views.start import start_view


def main():
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .read_timeout(10)
        .write_timeout(10)
        # .concurrent_updates(True)
        .build()
    )

    # ConversationHandler to handle the state machine
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("inicio", start_view)],
        states=MENU_STATES,
        fallbacks=[CommandHandler("inicio", start_view)],
    )

    application.add_handler(conv_handler)
    application.run_polling()
    application.idle()


if __name__ == "__main__":
    main()
