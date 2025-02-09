import datetime
import logging

import db
import feedparser
import json
import llm_text_summarizer
from requests.exceptions import HTTPError
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)


class RSSSummarizer:

    def __init__(self, db_session: Session):
        self.db_session = db_session

        self.init_timestamp = datetime.datetime.now().isoformat()

    @staticmethod
    def _rss_feed_entries(feed_url):
        parsed_feed = feedparser.parse(feed_url)
        return parsed_feed.entries

    def _process_rss_feed(self, model: db.Model, feed: db.RssFeed) -> int:
        feed_entries = self._rss_feed_entries(feed.url)
        logger.info(f"Got {len(feed_entries)} feed entries")

        count_new_entries = 0

        for entry in feed_entries:
            entry_guid = getattr(entry, "id", entry.link)
            logger.info(f"Saving raw feed entry data for entry {entry_guid}")
            db.insert_rss_feed_entry(self.db_session, feed.name, entry_guid, json.dumps(entry))
            logger.info(f"Processing entry {entry_guid} ...")
            existing = db.select_existing_summary(
                self.db_session, feed_entry_id=entry_guid, model_name=model.name
            )

            if existing:
                logger.info(
                    f"Found guid and model match, skipping pair {entry_guid} and {model.name}"
                )
                continue

            try:
                model_provider_class = getattr(
                    llm_text_summarizer, model.provider_class
                )
                summarizer_model = model_provider_class(model.provider_specific_id)
                text_summary = summarizer_model.summarize(entry.description)
            except HTTPError as e:
                logger.error(
                    f"Got an HTTP error: {e.response} while processing {entry_guid}"
                )
                continue

            db.insert_summary(
                self.db_session,
                feed_name=feed.name,
                model_name=model.name,
                feed_entry_id=entry_guid,
                content=text_summary,
            )
            logger.info(f"Finished with entry {feed.name}-{model.name}")
            count_new_entries += 1
        return count_new_entries

    def summarize_rss_feeds(self) -> int:
        count_new_entries = 0
        active_models = db.select_active_models(self.db_session)

        for model in active_models:
            logger.info(
                f"Using model: {model.name} with provider: {model.provider_class} and identifier: {model.provider_specific_id}"
            )

            rss_feeds = db.select_active_rss_feeds(self.db_session)
            for feed in rss_feeds:
                logger.info(f"Processing feed: {feed.name}")
                count_new_entries_from_feed = self._process_rss_feed(model, feed)
                logger.info(
                    f"Processed feed: {feed.name}, got {count_new_entries_from_feed} new entries"
                )
                count_new_entries += count_new_entries_from_feed
        return count_new_entries

    def new_summaries(self):
        unsent_summaries = db.select_unsent_summaries(self.db_session)
        logger.info(f"Unsent summary count: {len(unsent_summaries)}")

        return unsent_summaries
