import asyncio
import datetime
import logging
import json
import uuid

import feedparser

from requests.exceptions import HTTPError

import db
import rss_llm.llm_text_summarizer as llm_text_summarizer
from kokoro_tts.kokoro_tts import create_audio_file_docker

logger = logging.getLogger(__name__)

VIABLE_SUMMARY_LENGTH = 100

class RSSSummarizer:

    def __init__(self, db_query):
        self.db_query = db_query

        self.init_timestamp = datetime.datetime.now().isoformat()

    @staticmethod
    def _rss_feed_entries(feed_url):
        parsed_feed = feedparser.parse(feed_url)
        return parsed_feed.entries

    async def _process_rss_feed_entry(self, model: db.Model, feed: db.RssFeed, entry) -> bool:
        entry_guid = getattr(entry, "id", entry.link)
        logger.info(f"Processing entry {entry_guid} ...")
        existing_summary = self.db_query.select_existing_summary_from_model(
            feed_entry_id=entry_guid, model_name=model.name
        )

        if existing_summary:
            logger.info(
                f"Found guid and model match, skipping pair {entry_guid} and {model.name}"
            )
            return False

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

        try:
            model_provider_class = getattr(
                llm_text_summarizer, model.provider_class
            )
            summarizer_model = model_provider_class(model.provider_specific_id)
            if "content" in entry:
                entry_content = "".join([content_part.value for content_part in entry.content])
            elif "summary" in entry and len(entry.summary) > VIABLE_SUMMARY_LENGTH :
                entry_content = entry.summary
            else:
                logger.info(f" Could not find content to summarize in {entry_guid}")
                return False
            text_summary = await summarizer_model.summarize(entry_content)
        except HTTPError as e:
            logger.error(
                f"Got an HTTP error: {e.response} while processing {entry_guid}"
            )
            return False

        transcript_text = f"Title:{entry.title}. {text_summary} "
        audio_file_path = await create_audio_file_docker(transcript_text, uuid.uuid4().hex)

        self.db_query.insert_summary(
            feed_name=feed.name,
            model_name=model.name,
            feed_entry_id=entry_guid,
            content=text_summary,
            title=entry.title,
            audio_file_path=audio_file_path,
        )
        logger.info(f"Finished with entry {feed.name}-{entry_guid}-{model.name}")
        return True

    async def _process_rss_feed(self, model: db.Model, feed: db.RssFeed):
        feed_entries = self._rss_feed_entries(feed.url)
        logger.info(f"Got {len(feed_entries)} feed entries")

        coroutines = []
        for entry in feed_entries:
            coroutines.append(asyncio.Task(self._process_rss_feed_entry(model, feed, entry)))

        await asyncio.gather(*coroutines)


    async def summarize_rss_feeds(self):
        active_models = self.db_query.select_active_models()

        for model in active_models:
            logger.info(
                f"Using model: {model.name} with provider: {model.provider_class} and identifier: {model.provider_specific_id}"
            )

            rss_feeds = self.db_query.select_active_rss_feeds()
            coroutines = []
            for feed in rss_feeds:
                logger.info(f"Processing feed: {feed.name}")
                coroutines.append(asyncio.Task(self._process_rss_feed(model, feed)))

            await asyncio.gather(*coroutines)
        return

    def new_summaries(self):
        unsent_summaries = self.db_query.select_unsent_summaries()
        logger.info(f"Unsent summary count: {len(unsent_summaries)}")

        return unsent_summaries
