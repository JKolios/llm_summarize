from sqlite_connection import SQLiteConnection
from rss_summarizer import RSSSummarizer
from llm_text_summarizer import OllamaLLMTextSummarizer, OpenRouterLLMTextSummarizer

import os
import logging

MODEL_NAMES = os.environ.get("MODEL_NAMES", "").split(",")
RSS_FEED_URLS = os.environ.get("RSS_FEED_URLS", "").split(",")

SQLITE_FILE_NAME = "summaries.db"

SQLITE_SELECT_UNSENT_STATEMENT = "SELECT * FROM summaries WHERE sent == false"


LLM_TEXT_SUMMARIZER_CLASS = OpenRouterLLMTextSummarizer


def summarize_rss_feeds(sqlite_conn) -> int:
    count_new_entries = 0
    for model_name in MODEL_NAMES:
        logging.info(f"Using model: {model_name}")
        for feed_url in RSS_FEED_URLS:
            logging.info(f"Processing feed: {feed_url}")
            rss_summarizer = RSSSummarizer(
                feed_url,
                LLM_TEXT_SUMMARIZER_CLASS(model_name),
                sqlite_conn,
            )
            count_new_entries_from_feed = rss_summarizer.process_rss_feed()
            logging.info(
                f"Processed feed: {feed_url}, got {count_new_entries_from_feed} new entries"
            )
            count_new_entries += count_new_entries_from_feed
    return count_new_entries


def new_summaries(sqlite_conn):
    unsent_summaries = sqlite_conn.query(SQLITE_SELECT_UNSENT_STATEMENT, ())
    logging.info(f"Unsent summary count: {len(unsent_summaries)}")

    return unsent_summaries


if __name__ == "__main__":

    sqlite_connection = SQLiteConnection(SQLITE_FILE_NAME)
    logging.info("Opened SQLite Connection")
    summarize_rss_feeds(sqlite_connection)
