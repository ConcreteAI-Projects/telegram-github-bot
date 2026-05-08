from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from middleware.auth import whitelist_only
from services.github_service import github_service

# Conversation states
TITLE, DESCRIPTION, SCREENSHOT, IMPACT, URGENCY = range(5)


@whitelist_only
async def start_feature(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the feature request conversation."""
    context.user_data["issue_type"] = "feature"
    await update.message.reply_text(
        "Let's create a new feature request!\n\n"
        "What's the title of your feature?\n"
        "(Send /cancel to stop)"
    )
    return TITLE


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and store the issue title."""
    context.user_data["title"] = update.message.text
    await update.message.reply_text(
        f"Title: *{update.message.text}*\n\n"
        "Now describe the feature in detail.\n"
        "What should it do? Why is it needed?",
        parse_mode="Markdown",
    )
    return DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and store the issue description."""
    context.user_data["description"] = update.message.text

    keyboard = [
        [InlineKeyboardButton("Skip screenshot", callback_data="skip_screenshot")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Got it!\n\n"
        "Now send a screenshot (optional).\n"
        "You can send an image or click 'Skip' to continue.",
        reply_markup=reply_markup,
    )
    return SCREENSHOT


async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and store the screenshot."""
    photo = update.message.photo[-1]
    file = await photo.get_file()

    image_bytes = await file.download_as_bytearray()
    context.user_data["screenshot"] = bytes(image_bytes)

    await update.message.reply_text("Screenshot received!")
    return await show_impact_selection(update, context)


async def skip_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle skipping the screenshot."""
    query = update.callback_query
    await query.answer()

    context.user_data["screenshot"] = None
    return await show_impact_selection(update, context, from_callback=True)


async def show_impact_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    from_callback: bool = False
) -> int:
    """Show business impact selection buttons."""
    keyboard = [
        [
            InlineKeyboardButton("High", callback_data="impact_high"),
            InlineKeyboardButton("Mid", callback_data="impact_mid"),
            InlineKeyboardButton("Low", callback_data="impact_low"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "What's the business impact?"

    if from_callback:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

    return IMPACT


async def receive_impact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive impact and show urgency selection."""
    query = update.callback_query
    await query.answer()

    impact = query.data.replace("impact_", "")
    context.user_data["impact"] = impact

    keyboard = [
        [
            InlineKeyboardButton("ASAP", callback_data="urgency_asap"),
            InlineKeyboardButton("Soon", callback_data="urgency_soon"),
            InlineKeyboardButton("Future", callback_data="urgency_future"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Business Impact: *{impact}*\n\nHow urgent is this?",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return URGENCY


async def receive_urgency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive urgency and create the GitHub issue."""
    query = update.callback_query
    await query.answer()

    urgency = query.data.replace("urgency_", "")
    context.user_data["urgency"] = urgency

    await query.edit_message_text("Creating issue on GitHub...")

    try:
        result = github_service.create_issue(
            title=context.user_data["title"],
            body=context.user_data["description"],
            impact=context.user_data["impact"],
            urgency=urgency,
            issue_type=context.user_data.get("issue_type", "feature"),
            image_data=context.user_data.get("screenshot"),
        )

        await query.edit_message_text(
            f"Issue created successfully!\n\n"
            f"*#{result['number']}* - {result['title']}\n"
            f"Impact: {context.user_data['impact']} | Urgency: {urgency}\n\n"
            f"[View on GitHub]({result['url']})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )

    except Exception as e:
        await query.edit_message_text(
            f"Failed to create issue: {str(e)}\n\n"
            "Please check your GitHub configuration and try again."
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    context.user_data.clear()
    await update.message.reply_text(
        "Operation cancelled. Use /feature or /bug to start again."
    )
    return ConversationHandler.END


# Build the conversation handler
feature_handler = ConversationHandler(
    entry_points=[CommandHandler("feature", start_feature)],
    states={
        TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
        DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
        SCREENSHOT: [
            MessageHandler(filters.PHOTO, receive_screenshot),
            CallbackQueryHandler(skip_screenshot, pattern="^skip_screenshot$"),
        ],
        IMPACT: [CallbackQueryHandler(receive_impact, pattern="^impact_")],
        URGENCY: [CallbackQueryHandler(receive_urgency, pattern="^urgency_")],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
