from sqlite_connection import SQLiteConnection
from rss_summarizer import RSSSummarizer
from llm_text_summarizer import OllamaLLMTextSummarizer, OpenRouterLLMTextSummarizer
from telegram_bot import send_message

from time import sleep
import os
import logging

MODEL_NAMES = os.environ.get("MODEL_NAMES", "").split(",")
RSS_FEED_URLS = os.environ.get("RSS_FEED_URLS", "").split(",")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", None)
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", None)

SQLITE_FILE_NAME = "summaries.db"

SQLITE_SELECT_UNSENT_STATEMENT = "SELECT * FROM summaries WHERE sent == false"

SQLITE_UPDATE_SENT_STATEMENT = (
    "UPDATE summaries SET sent = true  WHERE entry_guid == ? AND model == ?"
)

LLM_TEXT_SUMMARIZER_CLASS = OpenRouterLLMTextSummarizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def telegram_message_from_summary(summary):
    return f"Feed: {summary[1]}\n\nTitle: {summary[4]}\n\nSummary:{summary[6]}\n\nLink: {summary[2]}"


def main():
    sqlite_connection = SQLiteConnection(SQLITE_FILE_NAME)
    logging.info("Opened SQLite Connection")

    for model_name in MODEL_NAMES:
        logging.info(f"Using model: {model_name}")
        for feed_url in RSS_FEED_URLS:
            logging.info(f"Processing feed: {feed_url}")
            rss_summarizer = RSSSummarizer(
                feed_url,
                LLM_TEXT_SUMMARIZER_CLASS(model_name),
                sqlite_connection,
            )
            rss_summarizer.process_rss_feed()
            logging.info(f"Processed feed: {feed_url}")

    unsent_summaries = sqlite_connection.query(SQLITE_SELECT_UNSENT_STATEMENT, ())
    logging.info(f"Unsent summary count: {len(unsent_summaries)}")

    for summary in unsent_summaries:
        logging.info(f"Sending summary of: {summary[2]}")
        send_message(telegram_message_from_summary(summary), BOT_TOKEN, CHAT_ID)
        logging.info(f"Sent summary of: {summary[2]}")
        result = sqlite_connection.execute_and_commit(
            SQLITE_UPDATE_SENT_STATEMENT, (summary[2], summary[3])
        )
        logging.info(f"Recorded send of: {summary[2]}, sleeping")
        sleep(5)


if __name__ == "__main__":
    main()
