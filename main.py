from telegram.ext import *
from config import BOT_TOKEN
from handlers.messages import handle_message
from handlers.start import start
from handlers.admin import chatid, premium
from handlers.callbacks import handle_callback

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("chatid", chatid))
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
