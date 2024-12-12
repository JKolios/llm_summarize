import datetime

import feedparser
from pydantic import BaseModel, ValidationError


class RSSSummarizer:
    class TextSummary(BaseModel):
        theme: str
        summary: str

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

    def __init__(self, rss_feed_url, summarizer, sqlite_connection):
        self.init_timestamp = datetime.datetime.now().isoformat()
        self.rss_feed_url = rss_feed_url
        self.summarizer = summarizer
        self.sqlite_connection = sqlite_connection
        self.sqlite_connection.init_sqlite_schema(self.SQLITE_SCHEMA_STATEMENTS)

    def _rss_feed_entries(self):
        parsed_feed = feedparser.parse(self.rss_feed_url)
        return parsed_feed.entries

    def process_rss_feed(self):
        feed_entries = self._rss_feed_entries()

        for entry in feed_entries:
            entry_guid = getattr(entry, "id", entry.link)
            guid_matches = self.sqlite_connection.query(
                self.SQLITE_SELECT_EXISTING_STATEMENT,
                (entry_guid, self.summarizer.model_name),
            )
            if guid_matches[0][0] != 0:
                print(
                    f"Found guid and model match, skipping pair {entry_guid} and {self.summarizer.model_name}"
                )
                continue

            try:
                text_summary = self.summarizer.summarize(
                    entry.description, self.__class__.TextSummary
                )
            except ValidationError as e:
                print(e)
                continue

            data = (
                self.init_timestamp,
                self.rss_feed_url,
                entry_guid,
                self.summarizer.model_name,
                entry.title,
                text_summary.theme,
                text_summary.summary,
                False,
            )
            self.sqlite_connection.execute_and_commit(
                self.SQLITE_INSERT_STATEMENT, data
            )
