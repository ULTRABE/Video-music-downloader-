import logging
from pyrogram import Client, filters

logging.basicConfig(level=logging.INFO)

app = Client(
    "railway_minimal",
    api_id=int("YOUR_API_ID"),
    api_hash="YOUR_API_HASH",
    bot_token="YOUR_BOT_TOKEN"
)

@app.on_message(filters.command("start"))
async def start(_, message):
    logging.info("START COMMAND RECEIVED")
    await message.reply("Bot is alive ✅")

@app.on_message(filters.text)
async def echo(_, message):
    logging.info(f"TEXT RECEIVED: {message.text}")
    await message.reply("I received your message")

app.run()
