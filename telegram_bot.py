import asyncio
import logging
import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, AIORateLimiter

from rss_summarizer import RSSSummarizer
from db_connection import SQLiteConnection, PGConnection
import llm_text_summarizer

# RUN_MODE can be either PERSISTENT or ONESHOT
RUN_MODE = os.environ.get("RUN_MODE", "PERSISTENT")

# Telegram-related settings
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", None)
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", None)

DEBUG_MESSAGES = os.environ.get("DEBUG_MESSAGES", None) == "True"
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL", "900"))
MODEL_NAMES = os.environ.get("MODEL_NAMES", "").split(",")


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def init_db_connection():
    DB_CLASS = os.environ.get("DB_CLASS", "PGConnection")

    if DB_CLASS == "PGConnection":
        pg_connection_string = os.environ.get("DB_PG_CONNECTION_STRING", "dbname=test user=postgres")
        return PGConnection(pg_connection_string)
    elif DB_CLASS == "SQLiteConnection":
        return SQLiteConnection()
    else:
        raise ValueError("DB_CLASS can be either PGConnection or SQLiteConnection")

db_conn = init_db_connection()
db_conn.init_schema()


RSS_FEED_URLS = os.environ.get("RSS_FEED_URLS", "").split(",")


def init_text_summarizer():
    text_summarizer_class = os.environ.get("LLM_TEXT_SUMMARIZER_CLASS", "CloudflareAILLMTextSummarizer")
    if text_summarizer_class == "CloudflareAILLMTextSummarizer":
        return llm_text_summarizer.CloudflareAILLMTextSummarizer
    elif text_summarizer_class == "OpenRouterLLMTextSummarizer":
        return llm_text_summarizer.OpenRouterLLMTextSummarizer
    elif text_summarizer_class == "OllamaLLMTextSummarizer":
        return llm_text_summarizer.OllamaLLMTextSummarizer
    else:
        raise ValueError("DB_CLASS can be either PGConnection or SQLiteConnection")

text_summarizer = init_text_summarizer()

def telegram_message_from_summary(summary):
    return f"Feed: {summary[1]}\n\nTitle: {summary[4]}\n\nSummary:{summary[5]}\n\nLink: {summary[2]}"


async def send_new_summaries(context: ContextTypes.DEFAULT_TYPE):
    unsent_summaries = RSSSummarizer(db_conn, text_summarizer).new_summaries()
    if len(unsent_summaries) > 0 or DEBUG_MESSAGES:
        await context.bot.send_message(
            chat_id=CHAT_ID, text=f"{len(unsent_summaries)} new summaries are available"
        )
    for summary in unsent_summaries:
        logging.info(f"Sending summary of: {summary[2]}")
        await context.bot.send_message(
            chat_id=CHAT_ID, text=telegram_message_from_summary(summary)
        )
        logging.info(f"Sent summary of: {summary[2]}")
        db_conn.update_sent_summaries((summary[2], summary[3]))
        logging.info(f"Recorded send of: {summary[2]}")


async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Sending all new entries")
    await update.message.reply_text("Sending all new entries...")
    await send_new_summaries(context)


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Starting manually triggered RSS feed scan")
    await update.message.reply_text("Scanning RSS feeds...")
    count_new_entries = RSSSummarizer(db_conn, text_summarizer).summarize_rss_feeds(MODEL_NAMES)
    await update.message.reply_text(f"Got {count_new_entries} new entries")
    await send_new_summaries(context)


async def cron_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Starting scheduled RSS feed scan")
    if DEBUG_MESSAGES:
        await context.bot.send_message(
            chat_id=CHAT_ID, text="Starting scheduled RSS feed scan..."
        )
    RSSSummarizer(db_conn, text_summarizer).summarize_rss_feeds(MODEL_NAMES)
    await send_new_summaries(context)

async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        feed_name = context.args[0]
        feed_url = context.args[1]

        logger.info(f"Adding a new feed named {feed_name} with url: {feed_url}")
        db_conn.insert_rss_feed((feed_name, feed_url, True))
        await update.message.reply_text(f'Added feed: {feed_name} with url: {feed_url}')
    except (IndexError, ValueError):
        await update.message.reply_text('Invalid parameters. Usage: add_feed <feed_name> <feed_url>')

async def delete_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        feed_name = context.args[0]

        logger.info(f"Deleting feed named {feed_name} if it exists")
        db_conn.delete_rss_feed((feed_name,))
        await update.message.reply_text(f'Deleted feed: {feed_name} if it existed')
    except (IndexError, ValueError):
        await update.message.reply_text('Invalid parameters. Usage: delete_feed <feed_name>')


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Got a ping command")
    await update.message.reply_text("The bot is up and running!")


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


def main_persistent() -> None:
    """Run the bot in persistent mode."""
    logger.info("Starting in persistent mode")
    # Create the Application and pass it your bot's token.
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(600)
        .write_timeout(600)
        .rate_limiter(AIORateLimiter())
        .build()
    )

    job_queue = application.job_queue
    job_queue.run_repeating(cron_scan, interval=SCAN_INTERVAL, first=5)

    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("send", send))
    application.add_handler(CommandHandler("add_feed", add_feed))
    application.add_handler(CommandHandler("delete_feed", delete_feed))

    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


async def main_oneshot() -> None:
    """Run a single execution of "scan"."""

    logger.info("Starting in oneshot mode")
    # Create the Application and pass it your bot's token.
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .rate_limiter(AIORateLimiter())
        .build()
    )
    application.job_queue.run_once(cron_scan, when=1)
    await application.job_queue.get_jobs_by_name("cron_scan")[0].run(application)


if __name__ == "__main__":
    if RUN_MODE.lower() == "persistent":
        main_persistent()
    elif RUN_MODE.lower() == "oneshot":
        asyncio.run(main_oneshot())
