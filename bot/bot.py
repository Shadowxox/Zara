import asyncio
import logging
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    AIORateLimiter,
    filters
)

import config
import database
import openai_utils

db = database.Database()
logger = logging.getLogger(__name__)
user_semaphores = {}
user_tasks = {}

async def register_user_if_not_exists(update: Update, context: CallbackContext, user):
    if not db.check_if_user_exists(user.id):
        db.add_new_user(user.id, update.message.chat_id, username=user.username, first_name=user.first_name, last_name=user.last_name)
        db.start_new_dialog(user.id)
    if db.get_user_attribute(user.id, "current_dialog_id") is None:
        db.start_new_dialog(user.id)
    if user.id not in user_semaphores:
        user_semaphores[user.id] = asyncio.Semaphore(1)
    db.set_user_attribute(user.id, "current_model", config.models["available_text_models"][0])
    db.set_user_attribute(user.id, "current_chat_mode", "zara")

async def is_bot_mentioned(update: Update, context: CallbackContext):
    try:
        message = update.message
        if message.chat.type == "private":
            return True
        if message.text and ("@" + context.bot.username) in message.text:
            return True
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            return True
    except:
        return True
    return False

async def message_handle(update: Update, context: CallbackContext, message=None):
    text = update.message.text or ""
    user = update.message.from_user
    await register_user_if_not_exists(update, context, user)

    # Flirty Zara group reply
    if update.message.chat.type != "private" and "zara" in text.lower():
        await update.message.reply_text("Hehe~ did someone call me? Nyaa~ 😽💗", parse_mode=ParseMode.HTML)
        return

    if update.message.chat.type != "private" and not await is_bot_mentioned(update, context):
        return

    if await is_previous_message_not_answered_yet(update, context):
        return

    user_id = user.id

    # Auto-reset if 24h passed
    last_interaction = db.get_user_attribute(user_id, "last_interaction")
    now = datetime.now()
    if not last_interaction or (now - last_interaction).total_seconds() > 86400:
        db.start_new_dialog(user_id)
        await update.message.reply_text("Nyaa~ It's been a while! I'm starting fresh, senpai 💞", parse_mode=ParseMode.HTML)

    db.set_user_attribute(user_id, "last_interaction", now)
    _message = message or text

    async def message_handle_fn():
        placeholder = await update.message.reply_text("...")
        await update.message.chat.send_action("typing")
        dialog_messages = db.get_dialog_messages(user_id)
        chatgpt_instance = openai_utils.ChatGPT(model="gpt-3.5-turbo")
        answer, *_ = await chatgpt_instance.send_message(_message, dialog_messages=dialog_messages, chat_mode="zara")
        await context.bot.edit_message_text(answer[:4096], chat_id=placeholder.chat_id, message_id=placeholder.message_id, parse_mode=ParseMode.HTML)
        new_dialog_message = {"user": [{"type": "text", "text": _message}], "bot": answer, "date": datetime.now()}
        db.set_dialog_messages(user_id, dialog_messages + [new_dialog_message])

    async with user_semaphores[user_id]:
        task = asyncio.create_task(message_handle_fn())
        user_tasks[user_id] = task
        try:
            await task
        except asyncio.CancelledError:
            await update.message.reply_text("✅ Canceled", parse_mode=ParseMode.HTML)
        finally:
            user_tasks.pop(user_id, None)

async def is_previous_message_not_answered_yet(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_semaphores[user_id].locked():
        await update.message.reply_text("⏳ Wait a sec, I'm still replying~", parse_mode=ParseMode.HTML)
        return True
    return False

async def cancel_handle(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in user_tasks:
        user_tasks[user_id].cancel()
    else:
        await update.message.reply_text("<i>Nothing to cancel, senpai~</i>", parse_mode=ParseMode.HTML)

def run_bot():
    app = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .concurrent_updates(True)
        .rate_limiter(AIORateLimiter(max_retries=5))
        .http_version("1.1")
        .build()
    )
    app.add_handler(CommandHandler("cancel", cancel_handle))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handle))
    app.run_polling()

if __name__ == "__main__":
    run_bot()
