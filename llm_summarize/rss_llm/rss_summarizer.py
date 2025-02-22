import datetime
import logging
import json
import uuid

import feedparser

from requests.exceptions import HTTPError

import db
import rss_llm.llm_text_summarizer as llm_text_summarizer
from kokoro_tts.kokoro_tts import create_audio_file

logger = logging.getLogger(__name__)


class RSSSummarizer:

    def __init__(self, db_query):
        self.db_query = db_query

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
            logger.info(f"Processing entry {entry_guid} ...")
            existing_summary = self.db_query.select_existing_summary_from_model(
                 feed_entry_id=entry_guid, model_name=model.name
            )

            if existing_summary:
                logger.info(
                    f"Found guid and model match, skipping pair {entry_guid} and {model.name}"
                )
                continue

            existing_raw_feed_content = self.db_query.select_existing_raw_feed_content(
                feed_entry_id=entry_guid, feed_name=feed.name
            )

            if not existing_raw_feed_content:
                logger.info(f"Saving raw feed entry data for entry {entry_guid}")
                self.db_query.insert_rss_feed_entry(
                    feed.name, entry_guid, json.dumps(entry)
                )

            else:
                logger.info(
                    f"Raw feed entry for {feed.name}-{entry_guid} already exists"
                )

            count_new_entries += 1

            try:
                model_provider_class = getattr(
                    llm_text_summarizer, model.provider_class
                )
                summarizer_model = model_provider_class(model.provider_specific_id)
                entry_content = "".join([content_part.value for content_part in entry.content])
                text_summary = summarizer_model.summarize(entry_content)
            except HTTPError as e:
                logger.error(
                    f"Got an HTTP error: {e.response} while processing {entry_guid}"
                )
                continue

            transcript_text = f"Title:{entry.title}. {text_summary} "
            audio_file_path = create_audio_file(transcript_text, uuid.uuid4().hex)

            self.db_query.insert_summary(
                feed_name=feed.name,
                model_name=model.name,
                feed_entry_id=entry_guid,
                content=text_summary,
                title=entry.title,
                audio_file_path=audio_file_path,
            )
            logger.info(f"Finished with entry {feed.name}-{entry_guid}-{model.name}")
            count_new_entries += 1
        return count_new_entries

    def summarize_rss_feeds(self) -> int:
        count_new_entries = 0
        active_models = self.db_query.select_active_models()

        for model in active_models:
            logger.info(
                f"Using model: {model.name} with provider: {model.provider_class} and identifier: {model.provider_specific_id}"
            )

            rss_feeds = self.db_query.select_active_rss_feeds()
            for feed in rss_feeds:
                logger.info(f"Processing feed: {feed.name}")
                count_new_entries_from_feed = self._process_rss_feed(model, feed)
                logger.info(
                    f"Processed feed: {feed.name}, got {count_new_entries_from_feed} new entries"
                )
                count_new_entries += count_new_entries_from_feed
        return count_new_entries

    def new_summaries(self):
        unsent_summaries = self.db_query.select_unsent_summaries()
        logger.info(f"Unsent summary count: {len(unsent_summaries)}")

        return unsent_summaries
