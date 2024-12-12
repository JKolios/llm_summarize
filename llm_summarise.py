from sqlite_connection import SQLiteConnection
from rss_summarizer import RSSSummarizer
from ollama_llm_text_summarizer import OllamaLLMTextSummarizer
from telegram_bot import send_message

from time import sleep
import os

MODEL_NAMES = os.environ.get("MODEL_NAMES", "").split(",")
RSS_FEED_URLS = os.environ.get("RSS_FEED_URLS", "").split(",")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", None)
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", None)

SQLITE_FILE_NAME = "summaries.db"

SQLITE_SELECT_UNSENT_STATEMENT = "SELECT * FROM summaries WHERE sent == false"

SQLITE_UPDATE_SENT_STATEMENT = (
    "UPDATE summaries SET sent = true  WHERE entry_guid == ? AND model == ?"
)


def telegram_message_from_summary(summary):
    return f"Feed: {summary[1]}\n\nTitle: {summary[4]}\n\nSummary:{summary[6]}\n\nLink: {summary[2]}"


def main():
    sqlite_connection = SQLiteConnection(SQLITE_FILE_NAME)

    for model_name in MODEL_NAMES:
        for feed_url in RSS_FEED_URLS:
            rss_summarizer = RSSSummarizer(
                feed_url,
                OllamaLLMTextSummarizer(model_name),
                sqlite_connection,
            )
            rss_summarizer.process_rss_feed()

    unsent_summaries = sqlite_connection.query(SQLITE_SELECT_UNSENT_STATEMENT, ())
    print(unsent_summaries)

    for summary in unsent_summaries:
        send_message(telegram_message_from_summary(summary), BOT_TOKEN, CHAT_ID)
        result = sqlite_connection.execute_and_commit(
            SQLITE_UPDATE_SENT_STATEMENT, (summary[2], summary[3])
        )
        print(result)
        sleep(5)


if __name__ == "__main__":
    main()
