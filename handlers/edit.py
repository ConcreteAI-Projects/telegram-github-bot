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
SELECT_ISSUE, SELECT_ACTION, EDIT_TITLE, EDIT_DESCRIPTION, EDIT_IMPACT, EDIT_URGENCY = range(6)


@whitelist_only
async def start_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the edit issue conversation."""
    await update.message.reply_text("Loading open issues...")

    try:
        issues = github_service.list_issues(state="open", limit=10)

        if not issues:
            await update.message.reply_text(
                "No open issues found.\n"
                "Use /feature or /bug to create one first."
            )
            return ConversationHandler.END

        # Build keyboard with issues
        keyboard = []
        for issue in issues:
            button_text = f"#{issue['number']} {issue['title'][:35]}"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"edit_issue_{issue['number']}")
            ])

        keyboard.append([InlineKeyboardButton("Cancel", callback_data="edit_cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Select an issue to edit:",
            reply_markup=reply_markup,
        )
        return SELECT_ISSUE

    except Exception as e:
        await update.message.reply_text(f"Failed to load issues: {str(e)}")
        return ConversationHandler.END


async def select_issue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle issue selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "edit_cancel":
        await query.edit_message_text("Operation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    # Extract issue number
    issue_number = int(query.data.replace("edit_issue_", ""))
    context.user_data["issue_number"] = issue_number

    # Show edit options
    keyboard = [
        [
            InlineKeyboardButton("Edit Title", callback_data="action_title"),
            InlineKeyboardButton("Edit Description", callback_data="action_description"),
        ],
        [
            InlineKeyboardButton("Change Impact", callback_data="action_impact"),
            InlineKeyboardButton("Change Urgency", callback_data="action_urgency"),
        ],
        [
            InlineKeyboardButton("Close Issue", callback_data="action_close"),
            InlineKeyboardButton("Cancel", callback_data="action_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Editing issue #{issue_number}\n\nWhat would you like to do?",
        reply_markup=reply_markup,
    )
    return SELECT_ACTION


async def select_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle action selection."""
    query = update.callback_query
    await query.answer()

    action = query.data.replace("action_", "")

    if action == "cancel":
        await query.edit_message_text("Operation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    if action == "title":
        await query.edit_message_text(
            f"Editing issue #{context.user_data['issue_number']}\n\n"
            "Send the new title:"
        )
        return EDIT_TITLE

    if action == "description":
        await query.edit_message_text(
            f"Editing issue #{context.user_data['issue_number']}\n\n"
            "Send the new description:"
        )
        return EDIT_DESCRIPTION

    if action == "impact":
        keyboard = [
            [
                InlineKeyboardButton("High", callback_data="newimpact_high"),
                InlineKeyboardButton("Mid", callback_data="newimpact_mid"),
                InlineKeyboardButton("Low", callback_data="newimpact_low"),
            ],
            [InlineKeyboardButton("Cancel", callback_data="newimpact_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Editing issue #{context.user_data['issue_number']}\n\n"
            "Select new business impact:",
            reply_markup=reply_markup,
        )
        return EDIT_IMPACT

    if action == "urgency":
        keyboard = [
            [
                InlineKeyboardButton("ASAP", callback_data="newurgency_asap"),
                InlineKeyboardButton("Soon", callback_data="newurgency_soon"),
                InlineKeyboardButton("Future", callback_data="newurgency_future"),
            ],
            [InlineKeyboardButton("Cancel", callback_data="newurgency_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Editing issue #{context.user_data['issue_number']}\n\n"
            "Select new urgency:",
            reply_markup=reply_markup,
        )
        return EDIT_URGENCY

    if action == "close":
        try:
            result = github_service.edit_issue(
                issue_number=context.user_data["issue_number"],
                state="closed",
            )
            await query.edit_message_text(
                f"Issue #{result['number']} closed!\n\n"
                f"[View on GitHub]({result['url']})",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            await query.edit_message_text(f"Failed to close issue: {str(e)}")

        context.user_data.clear()
        return ConversationHandler.END

    return SELECT_ACTION


async def edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle title edit."""
    new_title = update.message.text

    try:
        result = github_service.edit_issue(
            issue_number=context.user_data["issue_number"],
            title=new_title,
        )
        await update.message.reply_text(
            f"Title updated!\n\n"
            f"*#{result['number']}* - {result['title']}\n\n"
            f"[View on GitHub]({result['url']})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to update title: {str(e)}")

    context.user_data.clear()
    return ConversationHandler.END


async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle description edit."""
    new_description = update.message.text

    try:
        result = github_service.edit_issue(
            issue_number=context.user_data["issue_number"],
            body=new_description,
        )
        await update.message.reply_text(
            f"Description updated!\n\n"
            f"*#{result['number']}* - {result['title']}\n\n"
            f"[View on GitHub]({result['url']})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to update description: {str(e)}")

    context.user_data.clear()
    return ConversationHandler.END


async def edit_impact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle impact edit."""
    query = update.callback_query
    await query.answer()

    impact = query.data.replace("newimpact_", "")

    if impact == "cancel":
        await query.edit_message_text("Operation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        result = github_service.edit_issue(
            issue_number=context.user_data["issue_number"],
            impact=impact,
        )
        await query.edit_message_text(
            f"Business impact updated to *{impact}*!\n\n"
            f"*#{result['number']}* - {result['title']}\n\n"
            f"[View on GitHub]({result['url']})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        await query.edit_message_text(f"Failed to update impact: {str(e)}")

    context.user_data.clear()
    return ConversationHandler.END


async def edit_urgency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle urgency edit."""
    query = update.callback_query
    await query.answer()

    urgency = query.data.replace("newurgency_", "")

    if urgency == "cancel":
        await query.edit_message_text("Operation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        result = github_service.edit_issue(
            issue_number=context.user_data["issue_number"],
            urgency=urgency,
        )
        await query.edit_message_text(
            f"Urgency updated to *{urgency}*!\n\n"
            f"*#{result['number']}* - {result['title']}\n\n"
            f"[View on GitHub]({result['url']})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        await query.edit_message_text(f"Failed to update urgency: {str(e)}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    context.user_data.clear()
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END


# Build the conversation handler
edit_handler = ConversationHandler(
    entry_points=[CommandHandler("edit", start_edit)],
    states={
        SELECT_ISSUE: [CallbackQueryHandler(select_issue, pattern="^edit_")],
        SELECT_ACTION: [CallbackQueryHandler(select_action, pattern="^action_")],
        EDIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_title)],
        EDIT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_description)],
        EDIT_IMPACT: [CallbackQueryHandler(edit_impact, pattern="^newimpact_")],
        EDIT_URGENCY: [CallbackQueryHandler(edit_urgency, pattern="^newurgency_")],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
