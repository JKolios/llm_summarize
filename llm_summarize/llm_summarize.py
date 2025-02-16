import asyncio
import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from telegram_ui.telegram_bot import run_persistent, run_oneshot

import db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# RUN_MODE can be either PERSISTENT or ONESHOT
RUN_MODE = os.environ.get("RUN_MODE", "PERSISTENT")

def init_db_session() -> Session:
    engine = create_engine(os.getenv("DB_CONNECTION_STRING", "NONE"))
    db.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    return session()


db_session = init_db_session()

if __name__ == "__main__":
    if RUN_MODE.lower() == "persistent":
        run_persistent(db.Queries(db_session))
    elif RUN_MODE.lower() == "oneshot":
        asyncio.run(run_oneshot(db.Queries(db_session)))