import logging
import sqlite3

import psycopg


class DBConnection:
    SCHEMA_STATEMENT = """CREATE TABLE IF NOT EXISTS summaries(
        summary_timestamp TIMESTAMP WITHOUT TIME ZONE,
        rss_feed TEXT,
        entry_guid TEXT,
        model TEXT,
        text_title TEXT,
        text_summary TEXT,
        sent BOOLEAN DEFAULT FALSE)
        """

    INSERT_STATEMENT = "INSERT INTO summaries VALUES(%s, %s, %s, %s, %s, %s, %s)"
    SELECT_EXISTING_STATEMENT = (
        "SELECT COUNT(*) FROM summaries WHERE entry_guid = %s AND model = %s"
    )

    UPDATE_SENT_STATEMENT = (
        "UPDATE summaries SET sent = true  WHERE entry_guid = %s AND model = %s"
    )

    SELECT_UNSENT_STATEMENT = "SELECT * FROM summaries WHERE sent = false"

    def __init__(self):
        self.db_con = None
        self.cursor = None
        self._connect()

    def _connect(self):
        pass

    def init_schema(self, schema_statement=SCHEMA_STATEMENT):
        logging.info(f"Schema init statement:{self.SCHEMA_STATEMENT}")
        self.cursor.execute(schema_statement)
        self.db_con.commit()

    def query(self, statement, data):
        res = self.cursor.execute(statement, data)
        return res.fetchall()

    def execute_and_commit(self, sql_statement, data):
        self.cursor.execute(sql_statement, data)
        self.db_con.commit()

    def insert_summary(self, insert_data):
        return self.execute_and_commit(self.INSERT_STATEMENT, insert_data)

    def select_unsent_summaries(self):
        return self.query(self.SELECT_UNSENT_STATEMENT, ())

    def count_of_existing_summaries(self, count_of_existing_data):
        return self.query(self.SELECT_EXISTING_STATEMENT, count_of_existing_data)

    def update_sent_summaries(self, update_sent_data):
        return self.execute_and_commit(self.UPDATE_SENT_STATEMENT, update_sent_data)

class SQLiteConnection(DBConnection):
    DEFAULT_SQLITE_FILE_NAME = "summaries.db"

    SCHEMA_STATEMENT = """
            CREATE TABLE IF NOT EXISTS summaries(
            summary_timestamp,
            rss_feed TEXT,
            entry_guid TEXT,
            model TEXT,
            text_title TEXT,
            text_summary TEXT,
            sent BOOLEAN DEFAULT FALSE)"""

    INSERT_STATEMENT = "INSERT INTO summaries VALUES(?, ?, ?, ?, ?, ?, ?)"
    SELECT_EXISTING_STATEMENT = (
        "SELECT COUNT(*) FROM summaries WHERE entry_guid == ? AND model == ?"
    )

    UPDATE_SENT_STATEMENT = (
        "UPDATE summaries SET sent = true  WHERE entry_guid == ? AND model == ?"
    )

    SELECT_UNSENT_STATEMENT = "SELECT * FROM summaries WHERE sent == false"

    def __init__(self, sqlite_file_name=DEFAULT_SQLITE_FILE_NAME):
        self.sqlite_file_name = sqlite_file_name
        super().__init__()

    def _connect(self):
        self.db_con = sqlite3.connect(self.sqlite_file_name)
        self.cursor = self.db_con.cursor()


class PGConnection(DBConnection):

    def __init__(self, pg_conn_string):
        self.pg_conn_string = pg_conn_string
        super().__init__()

    def _connect(self):
        self.db_con = psycopg.connect(self.pg_conn_string)
        self.cursor = self.db_con.cursor()

