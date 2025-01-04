import asyncio
import html
import json
import logging
import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, AIORateLimiter

from rss_summarizer import RSSSummarizer
from sqlite_connection import SQLiteConnection

# RUN_MODE can be either PERSISTENT or ONESHOT
RUN_MODE = os.environ.get("RUN_MODE", "PERSISTENT")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", None)
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", None)

DEBUG_MESSAGES = os.environ.get("DEBUG_MESSAGES", None) == "True"
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL", "900"))
MODEL_NAMES = os.environ.get("MODEL_NAMES", "").split(",")
RSS_FEED_URLS = os.environ.get("RSS_FEED_URLS", "").split(",")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

SQLITE_SCHEMA_STATEMENTS = [
    "CREATE TABLE IF NOT EXISTS summaries("
    "summary_timestamp,"
    "rss_feed TEXT,"
    "entry_guid TEXT,"
    "model TEXT,"
    "text_title TEXT,"
    "text_theme TEXT,"
    "text_summary TEXT,"
    "sent BOOLEAN DEFAULT FALSE)"
]
SQLITE_INSERT_STATEMENT = "INSERT INTO summaries VALUES(?, ?, ?, ?, ?, ?, ?, ?)"
SQLITE_SELECT_EXISTING_STATEMENT = (
    "SELECT COUNT(*) FROM summaries WHERE entry_guid == ? AND model == ?"
)

SQLITE_UPDATE_SENT_STATEMENT = (
    "UPDATE summaries SET sent = true  WHERE entry_guid == ? AND model == ?"
)

sqlite_conn = SQLiteConnection("summaries.db")
sqlite_conn.init_sqlite_schema(SQLITE_SCHEMA_STATEMENTS)


def telegram_message_from_summary(summary):
    return f"Feed: {summary[1]}\n\nTitle: {summary[4]}\n\nSummary:{summary[6]}\n\nLink: {summary[2]}"


async def send_new_summaries(context: ContextTypes.DEFAULT_TYPE):
    unsent_summaries = RSSSummarizer(sqlite_conn).new_summaries()
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
        sqlite_conn.execute_and_commit(
            SQLITE_UPDATE_SENT_STATEMENT, (summary[2], summary[3])
        )
        logging.info(f"Recorded send of: {summary[2]}")


async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Sending all new entries")
    await update.message.reply_text("Sending all new entries...")
    await send_new_summaries(context)


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Starting manually triggered RSS feed scan")
    await update.message.reply_text("Scanning RSS feeds...")
    count_new_entries = RSSSummarizer(sqlite_conn).summarize_rss_feeds(
        MODEL_NAMES, RSS_FEED_URLS
    )
    await update.message.reply_text(f"Got {count_new_entries} new entries")
    await send_new_summaries(context)


async def cron_scan(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Starting scheduled RSS feed scan")
    if DEBUG_MESSAGES:
        await context.bot.send_message(
            chat_id=CHAT_ID, text="Starting scheduled RSS feed scan..."
        )
    RSSSummarizer(sqlite_conn).summarize_rss_feeds(MODEL_NAMES, RSS_FEED_URLS)
    await send_new_summaries(context)


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Got a check command")
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

    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("send", send))

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
