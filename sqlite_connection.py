import sqlite3


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
