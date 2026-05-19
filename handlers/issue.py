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
SOURCE, MODULE, MODULE_CUSTOM, OUTCOME, TYPE, STATUS, IMPACT, URGENCY, CONTENT_WHAT, CONTENT_WHY, CONTENT_EXPECTED, SCREENSHOT = range(12)

# Source options
SOURCES = ["XY", "QY", "IS", "PE", "Wei Heng", "Nyew", "Michelle"]

# Module options
MODULES = ["crack", "1D", "3D", "1D/3D", "mix", "me", "app", "infra", "others"]

# Type options
TYPES = [
    ("feature-new", "Feature (New)"),
    ("feature-improved", "Feature (Improved)"),
    ("task", "Task"),
]

# Status options
STATUSES = [
    ("raw-idea", "Raw Idea"),
    ("need-design", "Need Design"),
    ("todo", "Todo"),
]


@whitelist_only
async def start_issue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the issue creation conversation."""
    context.user_data.clear()

    # Create source selection keyboard (2 per row)
    keyboard = []
    row = []
    for i, source in enumerate(SOURCES):
        row.append(InlineKeyboardButton(source, callback_data=f"source_{source}"))
        if len(row) == 2 or i == len(SOURCES) - 1:
            keyboard.append(row)
            row = []

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Let's create a new issue!\n\n"
        "*Step 1/9:* Who is the source?",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return SOURCE


async def receive_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive source and show module selection."""
    query = update.callback_query
    await query.answer()

    source = query.data.replace("source_", "")
    context.user_data["source"] = source

    # Create module selection keyboard (3 per row)
    keyboard = []
    row = []
    for i, module in enumerate(MODULES):
        row.append(InlineKeyboardButton(module, callback_data=f"module_{module}"))
        if len(row) == 3 or i == len(MODULES) - 1:
            keyboard.append(row)
            row = []

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Source: *{source}*\n\n"
        "*Step 2/9:* Select the module\n"
        "(Select 'others' to type a custom module)",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return MODULE


async def receive_module(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive module selection."""
    query = update.callback_query
    await query.answer()

    module = query.data.replace("module_", "")

    if module == "others":
        await query.edit_message_text(
            f"Source: *{context.user_data['source']}*\n\n"
            "*Step 2/9:* Type your custom module name:",
            parse_mode="Markdown",
        )
        return MODULE_CUSTOM

    context.user_data["module"] = module
    return await show_outcome_prompt(update, context, from_callback=True)


async def receive_module_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive custom module input."""
    context.user_data["module"] = update.message.text
    return await show_outcome_prompt(update, context, from_callback=False)


async def show_outcome_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    from_callback: bool = False
) -> int:
    """Show outcome input prompt."""
    source = context.user_data["source"]
    module = context.user_data["module"]

    message = (
        f"Source: *{source}*\n"
        f"Module: *{module}*\n\n"
        "*Step 3/9:* What's the outcome?\n"
        "Start with a verb: fix, add, show, decide, remove, update..."
    )

    if from_callback:
        await update.callback_query.edit_message_text(message, parse_mode="Markdown")
    else:
        await update.message.reply_text(message, parse_mode="Markdown")

    return OUTCOME


async def receive_outcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive outcome and show type selection."""
    context.user_data["outcome"] = update.message.text

    # Build title preview
    source = context.user_data["source"]
    module = context.user_data["module"]
    outcome = context.user_data["outcome"]
    context.user_data["title"] = f"[{source}] [{module}] {outcome}"

    # Create type selection keyboard
    keyboard = []
    for type_id, type_label in TYPES:
        keyboard.append([InlineKeyboardButton(type_label, callback_data=f"type_{type_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Title: *{context.user_data['title']}*\n\n"
        "*Step 4/9:* Select the issue type:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return TYPE


async def receive_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive type and show status selection."""
    query = update.callback_query
    await query.answer()

    issue_type = query.data.replace("type_", "")
    context.user_data["issue_type"] = issue_type

    # Get display name for type
    type_display = next((label for tid, label in TYPES if tid == issue_type), issue_type)

    # Create status selection keyboard
    keyboard = []
    for status_id, status_label in STATUSES:
        keyboard.append([InlineKeyboardButton(status_label, callback_data=f"status_{status_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Title: *{context.user_data['title']}*\n"
        f"Type: *{type_display}*\n\n"
        "*Step 5/9:* Select the status:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return STATUS


async def receive_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive status and show impact selection."""
    query = update.callback_query
    await query.answer()

    status = query.data.replace("status_", "")
    context.user_data["status"] = status

    # Get display names
    type_display = next((label for tid, label in TYPES if tid == context.user_data["issue_type"]), context.user_data["issue_type"])
    status_display = next((label for sid, label in STATUSES if sid == status), status)

    keyboard = [
        [
            InlineKeyboardButton("High", callback_data="impact_high"),
            InlineKeyboardButton("Mid", callback_data="impact_mid"),
            InlineKeyboardButton("Low", callback_data="impact_low"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Title: *{context.user_data['title']}*\n"
        f"Type: *{type_display}*\n"
        f"Status: *{status_display}*\n\n"
        "*Step 6/9:* What's the business impact?",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
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

    # Get display names
    type_display = next((label for tid, label in TYPES if tid == context.user_data["issue_type"]), context.user_data["issue_type"])
    status_display = next((label for sid, label in STATUSES if sid == context.user_data["status"]), context.user_data["status"])

    await query.edit_message_text(
        f"Title: *{context.user_data['title']}*\n"
        f"Type: *{type_display}*\n"
        f"Status: *{status_display}*\n"
        f"Impact: *{impact.capitalize()}*\n\n"
        "*Step 7/9:* How urgent is this?",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return URGENCY


async def receive_urgency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive urgency and ask for content - What."""
    query = update.callback_query
    await query.answer()

    urgency = query.data.replace("urgency_", "")
    context.user_data["urgency"] = urgency

    await query.edit_message_text(
        "*Step 8/9:* Now let's fill in the content.\n\n"
        "*What* is the issue about?\n"
        "(Describe what needs to be done)",
        parse_mode="Markdown",
    )
    return CONTENT_WHAT


async def receive_content_what(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive 'What' content and ask for 'Why'."""
    context.user_data["content_what"] = update.message.text

    await update.message.reply_text(
        "*Why* is this needed?\n"
        "(Explain the reason or motivation)",
        parse_mode="Markdown",
    )
    return CONTENT_WHY


async def receive_content_why(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive 'Why' content and ask for 'Expected Behaviour'."""
    context.user_data["content_why"] = update.message.text

    await update.message.reply_text(
        "*Expected Behaviour*\n"
        "(Describe what should happen when this is implemented)",
        parse_mode="Markdown",
    )
    return CONTENT_EXPECTED


async def receive_content_expected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive 'Expected Behaviour' and ask for screenshot."""
    context.user_data["content_expected"] = update.message.text

    keyboard = [
        [InlineKeyboardButton("Skip screenshot", callback_data="skip_screenshot")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "*Step 9/9:* Attach a screenshot (optional)\n\n"
        "Send an image or click 'Skip' to create the issue.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )
    return SCREENSHOT


async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive screenshot and create issue."""
    photo = update.message.photo[-1]
    file = await photo.get_file()

    image_bytes = await file.download_as_bytearray()
    context.user_data["screenshot"] = bytes(image_bytes)

    await update.message.reply_text("Screenshot received! Creating issue...")
    return await create_github_issue(update, context, from_callback=False)


async def skip_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skip screenshot and create issue."""
    query = update.callback_query
    await query.answer()

    context.user_data["screenshot"] = None
    await query.edit_message_text("Creating issue on GitHub...")
    return await create_github_issue(update, context, from_callback=True)


async def create_github_issue(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    from_callback: bool = False
) -> int:
    """Create the GitHub issue with all collected data."""
    # Build the body with template
    body = f"""## What
{context.user_data['content_what']}

## Why
{context.user_data['content_why']}

## Expected Behaviour
{context.user_data['content_expected']}

---
**Source:** {context.user_data['source']}
**Module:** {context.user_data['module']}
"""

    try:
        result = github_service.create_issue(
            title=context.user_data["title"],
            body=body,
            impact=context.user_data["impact"],
            urgency=context.user_data["urgency"],
            issue_type=context.user_data["issue_type"],
            status=context.user_data["status"],
            image_data=context.user_data.get("screenshot"),
        )

        # Get display names
        type_display = next((label for tid, label in TYPES if tid == context.user_data["issue_type"]), context.user_data["issue_type"])
        status_display = next((label for sid, label in STATUSES if sid == context.user_data["status"]), context.user_data["status"])

        success_message = (
            f"Issue created successfully!\n\n"
            f"*#{result['number']}* - {result['title']}\n\n"
            f"Type: {type_display}\n"
            f"Status: {status_display}\n"
            f"Impact: {context.user_data['impact'].capitalize()} | "
            f"Urgency: {context.user_data['urgency'].upper()}\n\n"
            f"[View on GitHub]({result['url']})"
        )

        if from_callback:
            await update.callback_query.edit_message_text(
                success_message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        else:
            await update.message.reply_text(
                success_message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

    except Exception as e:
        error_message = (
            f"Failed to create issue: {str(e)}\n\n"
            "Please check your GitHub configuration and try again."
        )

        if from_callback:
            await update.callback_query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    context.user_data.clear()
    await update.message.reply_text(
        "Operation cancelled. Use /issue to start again."
    )
    return ConversationHandler.END


# Build the conversation handler
issue_handler = ConversationHandler(
    entry_points=[CommandHandler("issue", start_issue)],
    states={
        SOURCE: [CallbackQueryHandler(receive_source, pattern="^source_")],
        MODULE: [CallbackQueryHandler(receive_module, pattern="^module_")],
        MODULE_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_module_custom)],
        OUTCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_outcome)],
        TYPE: [CallbackQueryHandler(receive_type, pattern="^type_")],
        STATUS: [CallbackQueryHandler(receive_status, pattern="^status_")],
        IMPACT: [CallbackQueryHandler(receive_impact, pattern="^impact_")],
        URGENCY: [CallbackQueryHandler(receive_urgency, pattern="^urgency_")],
        CONTENT_WHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_content_what)],
        CONTENT_WHY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_content_why)],
        CONTENT_EXPECTED: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_content_expected)],
        SCREENSHOT: [
            MessageHandler(filters.PHOTO, receive_screenshot),
            CallbackQueryHandler(skip_screenshot, pattern="^skip_screenshot$"),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
