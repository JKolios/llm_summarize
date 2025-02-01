import datetime
import logging

import feedparser
from pydantic import BaseModel, ValidationError
from requests.exceptions import HTTPError


class RSSSummarizer:
    class TextSummary(BaseModel):
        theme: str
        summary: str


    def __init__(self, db_connection, llm_summarizer):
        self.init_timestamp = datetime.datetime.now().isoformat()
        self.db_connection = db_connection
        self.db_connection.init_schema()

        self.llm_summarizer = llm_summarizer

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
            guid_matches = self.db_connection.count_of_existing_summaries((entry_guid, model_name))
            if guid_matches[0][0] != 0:
                logging.info(
                    f"Found guid and model match, skipping pair {entry_guid} and {model_name}"
                )
                continue

            try:
                text_summary = self.llm_summarizer(model_name).summarize(
                    entry.description, self.__class__.TextSummary
                )
            except ValidationError as e:
                logging.error(f"Got validation errors:{str(e)}")
                text_summary = self.__class__.TextSummary(
                    theme="",
                    summary="Failed to create a text summary, please check the bot's logs",
                )
            except HTTPError as e:
                logging.error(f"Got an HTTP error: {e.response}")
                text_summary = self.__class__.TextSummary(
                    theme="",
                    summary="Failed to create a text summary, please check the bot's logs",
                )

            insert_data = (
                self.init_timestamp,
                feed_url,
                entry_guid,
                model_name,
                entry.title,
                text_summary.summary,
                False,
            )
            self.db_connection.insert_summary(insert_data)
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
        unsent_summaries = self.db_connection.select_unsent_summaries()
        logging.info(f"Unsent summary count: {len(unsent_summaries)}")

        return unsent_summaries
