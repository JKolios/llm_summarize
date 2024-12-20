import datetime
import logging

import feedparser
from pydantic import BaseModel, ValidationError

import llm_text_summarizer

LLM_TEXT_SUMMARIZER_CLASS = llm_text_summarizer.CloudflareAILLMTextSummarizer


class RSSSummarizer:
    class TextSummary(BaseModel):
        theme: str
        summary: str

    SQLITE_FILE_NAME = "summaries.db"

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
    SQLITE_SELECT_UNSENT_STATEMENT = "SELECT * FROM summaries WHERE sent == false"

    def __init__(self, sqlite_connection):
        self.init_timestamp = datetime.datetime.now().isoformat()
        self.sqlite_connection = sqlite_connection
        self.sqlite_connection.init_sqlite_schema(self.SQLITE_SCHEMA_STATEMENTS)

    @staticmethod
    def _rss_feed_entries(feed_url):
        parsed_feed = feedparser.parse(feed_url)
        return parsed_feed.entries

    def _process_rss_feed(self, model_name, feed_url) -> int:
        feed_entries = self._rss_feed_entries(feed_url)
        logging.info(f"Got {len(feed_entries)} feed entries")

        count_new_entries = 0

        for entry in feed_entries:
            entry_guid = getattr(entry, "id", entry.link)
            logging.info(f"Processing entry {entry_guid} ...")
            guid_matches = self.sqlite_connection.query(
                self.SQLITE_SELECT_EXISTING_STATEMENT,
                (entry_guid, model_name),
            )
            if guid_matches[0][0] != 0:
                logging.info(
                    f"Found guid and model match, skipping pair {entry_guid} and {model_name}"
                )
                continue

            try:
                text_summary = LLM_TEXT_SUMMARIZER_CLASS(model_name).summarize(
                    entry.description, self.__class__.TextSummary
                )
            except ValidationError as e:
                logging.error(
                    f"Got a Validation error, continuing to next guid and model pair"
                )
                continue

            data = (
                self.init_timestamp,
                feed_url,
                entry_guid,
                model_name,
                entry.title,
                text_summary.theme,
                text_summary.summary,
                False,
            )
            self.sqlite_connection.execute_and_commit(
                self.SQLITE_INSERT_STATEMENT, data
            )
            logging.info(f"Finished with entry {entry_guid}")
            count_new_entries += 1
        return count_new_entries

    def summarize_rss_feeds(self, model_names, rss_feed_urls) -> int:
        count_new_entries = 0
        for model_name in model_names:
            logging.info(f"Using model: {model_name}")
            for feed_url in rss_feed_urls:
                logging.info(f"Processing feed: {feed_url}")
                count_new_entries_from_feed = self._process_rss_feed(
                    model_name, feed_url
                )
                logging.info(
                    f"Processed feed: {feed_url}, got {count_new_entries_from_feed} new entries"
                )
                count_new_entries += count_new_entries_from_feed
        return count_new_entries

    def new_summaries(self):
        unsent_summaries = self.sqlite_connection.query(
            self.SQLITE_SELECT_UNSENT_STATEMENT, ()
        )
        logging.info(f"Unsent summary count: {len(unsent_summaries)}")

        return unsent_summaries
