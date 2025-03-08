
import logging
import os
import uuid

from psycopg.errors import UniqueViolation

from kokoro_tts.kokoro_tts import create_audio_file_docker
from rss_llm.rss_summarizer import RSSSummarizer

from telegram import Update, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import AIORateLimiter, Application, CommandHandler, filters, MessageHandler, ContextTypes, ConversationHandler, CallbackContext


# Telegram-related settings
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", None)
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", None)

# Intervals and message send limits
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL", "900"))
SEND_INTERVAL = int(os.environ.get("SEND_INTERVAL", "60"))
MAX_SUMMARIES_PER_SEND = 10

# Logging settings
DEBUG_MESSAGES = os.environ.get("DEBUG_MESSAGES", None) == "True"

logger = logging.getLogger(__name__)

# Model provider classes
MODEL_PROVIDER_CLASSES = ["CloudflareAISummarizer", "OpenAISummarizer", "OllamaSummarizer", "OpenAISummarizerChunked"]

# New model conversation states
MODEL_NAME, MODEL_PROVIDER_NAME = range(2)

# New feed conversation states
FEED_NAME, FEED_URL = range(2)

def init_telegram_bot_application(
    bot_token: str, db_queries, read_timeout=60, write_timeout=60
) -> Application:
    # Create the Application and pass it your bot's token.
    bot_application = (
        Application.builder()
        .token(bot_token)
        .read_timeout(read_timeout)
        .write_timeout(write_timeout)
        .rate_limiter(AIORateLimiter())
        .build()
    )
    bot_application.bot_data['db_queries'] = db_queries
    return bot_application


def telegram_message_from_summary(summary):
    return f"Feed: {summary.feed_name}\n\nTitle: {[[summary.title]]}\n\nSummary:{summary.content}\n\nLink: {summary.feed_entry_id}"


async def reply_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Sending all new entries")
    await update.message.reply_text("Sending all new entries...")
    unsent_summaries = RSSSummarizer(context.bot_data['db_queries']).new_summaries()
    if len(unsent_summaries) > 0 or DEBUG_MESSAGES:
        await update.message.reply_text(
            text=f"{len(unsent_summaries)} new entries are available"
        )
    else:
        await update.message.reply_text(text="No new entries are available")
        return

    for summary in unsent_summaries[:MAX_SUMMARIES_PER_SEND]:
        logger.info(f"Sending summary of: {summary.feed_entry_id}")
        await update.message.reply_text(text=telegram_message_from_summary(summary))

        await update.message.reply_audio(summary.audio_file_path, title=summary.title, performer="Kokoro TTS")

        logger.info(f"Sent summary of: {summary.feed_entry_id}")
        context.bot_data['db_queries'].update_summary_sent(
            summary.feed_name, summary.model_name, summary.feed_entry_id
        )
        logger.info(f"Recorded send of: {summary.feed_entry_id}")


async def cron_send(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Sending all new entries")

    unsent_summaries = RSSSummarizer(context.bot_data['db_queries']).new_summaries()
    if len(unsent_summaries) > 0 or DEBUG_MESSAGES:
        await context.bot.send_message(
            chat_id=CHAT_ID, text=f"{len(unsent_summaries)} new summaries are available"
        )
    for summary in unsent_summaries[:MAX_SUMMARIES_PER_SEND]:
        logger.info(f"Sending summary of: {summary.feed_entry_id}")
        await context.bot.send_message(
            chat_id=CHAT_ID, text=telegram_message_from_summary(summary)
        )
        await context.bot.send_audio(chat_id=CHAT_ID, audio=summary.audio_file_path, title="TTS")

        logger.info(f"Sent summary of: {summary.feed_entry_id}")
        context.bot_data['db_queries'].update_summary_sent(summary.feed_name, summary.model_name, summary.feed_entry_id)
        logger.info(f"Recorded send of: {summary.feed_entry_id}")


async def reply_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Starting manually triggered RSS feed scan")
    await update.message.reply_text("Scanning RSS feeds...")

    await RSSSummarizer(context.bot_data['db_queries']).summarize_rss_feeds()
    await update.message.reply_text(f"Got new entries")


async def cron_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Starting scheduled RSS feed scan")
    if DEBUG_MESSAGES:
        await context.bot.send_message(
            chat_id=CHAT_ID, text="Starting scheduled RSS feed scan..."
        )
    await RSSSummarizer(context.bot_data['db_queries']).summarize_rss_feeds()


async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        feed_name = context.args[0]
        feed_url = context.args[1]

        logger.info(f"Adding a new feed named {feed_name} with url: {feed_url}")
        context.bot_data['db_queries'].insert_rss_feed(name=feed_name, url=feed_url)
        await update.message.reply_text(f"Added feed: {feed_name} with url: {feed_url}")
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Invalid parameters. Usage: add_feed <feed_name> <feed_url>"
        )
    except UniqueViolation:
        await update.message.reply_text("Feed already exists")


async def delete_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        feed_name = context.args[0]

        logger.info(f"Deleting feed named {feed_name} if it exists")
        context.bot_data['db_queries'].delete_rss_feed(name=feed_name)
        await update.message.reply_text(f"Deleted feed: {feed_name} if it existed")
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Invalid parameters. Usage: delete_feed <feed_name>"
        )


async def delete_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        model_name = context.args[0]

        logger.info(f"Deleting model named {model_name} if it exists")
        context.bot_data['db_queries'].delete_model(name=model_name)
        await update.message.reply_text(f"Deleted model: {model_name} if it existed")
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Invalid parameters. Usage: delete_model <model_name>"
        )


async def send_tts_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        tts_text = " ".join(context.args)

        logger.info(f"Replying with voiced text: {tts_text} ")
        audio_file_path = await create_audio_file_docker(tts_text, uuid.uuid4().hex)
        await update.message.reply_audio(audio_file_path, title="TTS")
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Invalid parameters. Usage: tts <text>"
        )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Got a ping command")
    await update.message.reply_text("The bot is up and running!")

async def add_model_convo(update: Update, context: CallbackContext) -> int:
    """Start the conversation and ask user for input."""

    await update.message.reply_text(
        "Please select the model provider:",
        reply_markup=ReplyKeyboardMarkup([MODEL_PROVIDER_CLASSES], one_time_keyboard=True, resize_keyboard= True)
    )

    return MODEL_PROVIDER_NAME


async def handle_model_provider_choice(update: Update, context: CallbackContext) -> int:
    user_choice = update.message.text

    if user_choice in MODEL_PROVIDER_CLASSES:
        # Store the user's choice in context.user_data
        context.user_data['model_provider_class'] = user_choice

        # Ask the user for the name of the model
        await update.message.reply_text("Great! Now, please provide the name of the model:")

        # Transition to the DONE_ADDING_MODEL state
        return MODEL_NAME
    else:
        # Handle invalid input
        await update.message.reply_text("Invalid choice. Please choose one of the providers in the list.")
        return ConversationHandler.END


# Handle the user's model name input
async def handle_model_name(update: Update, context: CallbackContext) -> int:
    model_name = update.message.text

    # Retrieve the user's choice from context.user_data
    provider_class = context.user_data.get('model_provider_class', None)

    if model_name:
        # Thank the user for their input
        try:
            context.bot_data['db_queries'].insert_model(
                name=f'{model_name}-{provider_class}',
                provider_class=provider_class,
                provider_specific_id=model_name,
            )
        except UniqueViolation:
            await update.message.reply_text("Model already exists")
        await update.message.reply_text(
            f"Added model: {model_name} with provider: {provider_class} and identifier: {model_name}"
        )
        # End the conversation
        return ConversationHandler.END
    else:
        await update.message.reply_text(f"Please give a valid model name")
        return MODEL_NAME

async def add_feed_convo(update: Update, context: CallbackContext) -> int:
    """Start the conversation and ask user for input."""

    await update.message.reply_text(
        "Please give a name for the RSS/Atom feed:"
    )

    return FEED_NAME


async def handle_feed_name(update: Update, context: CallbackContext) -> int:
    feed_name = update.message.text

    # Store the user's choice in context.user_data
    context.user_data['feed_name'] = feed_name

    # Ask the user for the URL of the feed
    await update.message.reply_text("Great! Now, please provide the URL of the feed:")

    # Transition to the FEED_URL state
    return FEED_URL


async def handle_feed_url(update: Update, context: CallbackContext) -> int:
    feed_url = update.message.text

    # Retrieve the user's choice from context.user_data
    feed_name = context.user_data.get('feed_name', None)

    if feed_name and feed_url:
        try:
            context.bot_data['db_queries'].insert_rss_feed(name=feed_name, url=feed_url)
        except UniqueViolation:
            await update.message.reply_text("Feed already exists")
            # End the conversation
            return ConversationHandler.END
        await update.message.reply_text(f"Added feed: {feed_name} with url: {feed_url}")
        # End the conversation
        return ConversationHandler.END


# Cancel command to end a conversation
async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Conversation canceled.")
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096-character limit.
    message = f"An exception was raised: {context.error}"

    # Finally, send the message
    await context.bot.send_message(
        chat_id=CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )


def run_persistent(db_queries) -> None:
    """Run the bot in persistent mode."""
    logger.info("Starting in persistent mode")

    application = init_telegram_bot_application(BOT_TOKEN, db_queries)

    job_queue = application.job_queue
    job_queue.run_repeating(cron_scan, interval=SCAN_INTERVAL, first=5)
    job_queue.run_repeating(cron_send, interval=SEND_INTERVAL, first=30)


    add_model_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add_model", add_model_convo)],
        states={
            MODEL_PROVIDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_model_provider_choice)],
            MODEL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_model_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(add_model_conv_handler)

    add_feed_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add_feed", add_feed_convo)],
        states={
            FEED_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feed_name)],
            FEED_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feed_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(add_feed_conv_handler)

    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("scan", reply_scan))
    application.add_handler(CommandHandler("send", reply_send))
    application.add_handler(CommandHandler("delete_feed", delete_feed))
    application.add_handler(CommandHandler("delete_model", delete_model))
    application.add_handler(CommandHandler("tts", send_tts_audio))

    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def run_oneshot(db_queries) -> None:
    """Run a single execution of "scan"."""
    logger.info("Starting in oneshot mode")
    application = init_telegram_bot_application(BOT_TOKEN, db_queries)
    application.job_queue.run_once(cron_scan, when=1)
    await application.job_queue.get_jobs_by_name("cron_scan")[0].run(application)
