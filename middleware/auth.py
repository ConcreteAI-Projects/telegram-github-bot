from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_USERS


def whitelist_only(func):
    """Decorator to restrict bot commands to whitelisted users only."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id

        if user_id not in ALLOWED_USERS:
            await update.message.reply_text(
                "Sorry, you're not authorized to use this bot.\n"
                "Contact the administrator to get access."
            )
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper
