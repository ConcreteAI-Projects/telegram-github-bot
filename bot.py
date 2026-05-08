import logging
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

from config import TELEGRAM_BOT_TOKEN, validate_config
from handlers import feature_handler, bug_handler, edit_handler
from middleware.auth import whitelist_only

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@whitelist_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"Hi {user.first_name}! Welcome to the GitHub Issue Bot.\n\n"
        "Use these commands to manage issues:\n\n"
        "/feature - Create a new feature request\n"
        "/bug - Report a bug\n"
        "/edit - Edit or close an existing issue\n"
        "/cancel - Cancel current operation\n\n"
        "Each issue can include:\n"
        "- Title\n"
        "- Description\n"
        "- Screenshot (optional)\n"
        "- Priority (High/Mid/Low)"
    )


@whitelist_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    await update.message.reply_text(
        "GitHub Issue Bot Help\n"
        "─────────────────────\n\n"
        "/start - Welcome message\n"
        "/feature - Create a feature request\n"
        "/bug - Report a bug\n"
        "/edit - Edit/close an issue\n"
        "/cancel - Cancel current operation\n\n"
        "Priority Levels:\n"
        "- High: Critical features/bugs\n"
        "- Mid: Important but not urgent\n"
        "- Low: Nice to have\n\n"
        "Screenshots are optional but recommended for bugs."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify user."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "An error occurred. Please try again or contact the administrator."
        )


async def post_init(application: Application) -> None:
    """Set bot commands after initialization."""
    commands = [
        BotCommand("start", "Welcome message and instructions"),
        BotCommand("feature", "Create a new feature request"),
        BotCommand("bug", "Report a bug"),
        BotCommand("edit", "Edit or close an existing issue"),
        BotCommand("cancel", "Cancel current operation"),
        BotCommand("help", "Show help message"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    """Start the bot."""
    # Validate configuration
    validate_config()

    # Create the Application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(feature_handler)
    application.add_handler(bug_handler)
    application.add_handler(edit_handler)

    # Add error handler
    application.add_error_handler(error_handler)

    # Run the bot until Ctrl-C
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
