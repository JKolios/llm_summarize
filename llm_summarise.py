import ollama
from pydantic import BaseModel, ValidationError
import sqlite3
import feedparser

import datetime

from pydantic.json_schema import model_json_schema


class OllamaLLMTextSummarizer:
    def __init__(self, model_name):
        self.model_name = model_name

    def summarize(self, text, summary_schema_class):

        prompt = {"role": "user", "content": f"Please summarize this text in 5 sentences at maximum: {text}"}

        response = ollama.chat(
            self.model_name, messages=[prompt], format=summary_schema_class.model_json_schema()
        )

        print(response)
        try:
            text_summary = summary_schema_class.model_validate_json(
                response.message.content
            )
        except ValidationError as e:
            print(
                f"Response content does not match the expected schema: {response.content}"
            )
            raise e
        return text_summary


class SQLiteConnection:
    def __init__(self, sqlite_file_name):
        self.sqlite_file_name = sqlite_file_name
        self.db_con = None
        self.cursor = None
        self._connect_sqlite()

    def _connect_sqlite(self):
        self.db_con = sqlite3.connect(self.sqlite_file_name)
        self.cursor = self.db_con.cursor()

    def init_sqlite_schema(self, schema_statements):
        for statement in schema_statements:
            self.cursor.execute(statement)

    def query(self, statement, data):
        res = self.cursor.execute(statement, data)
        return res.fetchall()

    def execute_and_commit(self, sql_statement, data):
        self.cursor.execute(sql_statement, data)
        self.db_con.commit()


class RSSSummarizer:
    class TextSummary(BaseModel):
        theme: str
        summary: str

    SQLITE_SCHEMA_STATEMENTS = [
        "CREATE TABLE IF NOT EXISTS summaries(summary_timestamp, rss_feed, entry_guid, model, text_title, text_theme, text_summary)"
    ]
    SQLITE_INSERT_STATEMENT = "INSERT INTO summaries VALUES(?, ?, ?, ?, ?, ?, ?)"
    SQLITE_SELECT_STATEMENT = "SELECT COUNT(*) FROM summaries WHERE entry_guid == ? AND model == ?"

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
            entry_guid =  getattr(entry, "id", entry.link)
            guid_matches = self.sqlite_connection.query(self.SQLITE_SELECT_STATEMENT, (entry_guid, self.summarizer.model_name))
            if guid_matches[0][0] != 0:
                print(f"Found guid and model match, skipping pair {entry_guid} and {self.summarizer.model_name}")
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
                entry_guid ,
                self.summarizer.model_name,
                entry.title,
                text_summary.theme,
                text_summary.summary,
            )
            self.sqlite_connection.execute_and_commit(self.SQLITE_INSERT_STATEMENT, data)


def main():
    model_names = ["llama3.2", "gemma2", "mistral", "codellama"]
    sqlite_file_name = "summaries.db"
    rss_feed_urls = ["https://computer.rip/rss.xml", "https://www.filfre.net/feed/rss/", "https://blog.plover.com/index.rss", "https://medium.com/feed/@admiralcloudberg"]
    sqlite_connection = SQLiteConnection(sqlite_file_name)

    for model_name in model_names:
        for feed_url in rss_feed_urls:
            rss_summarizer = RSSSummarizer(
                feed_url,
                OllamaLLMTextSummarizer(model_name),
               sqlite_connection,
            )
            rss_summarizer.process_rss_feed()


if __name__ == "__main__":
    main()
