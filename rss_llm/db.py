import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy import Boolean, Column, ForeignKey, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import TEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import false, true
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

logger = logging.getLogger(__name__)


class RssFeed(Base):
    __tablename__ = "rss_feeds"

    name = Column(String(128), primary_key=True)
    url = Column(String(512), nullable=False)
    active = Column(Boolean(), default=True)


class RSSEntry(Base):
    __tablename__ = "rss_entries"

    feed_name = Column(ForeignKey("rss_feeds.name"), nullable=False)
    feed_entry_id = Column(TEXT, nullable=False)
    raw_content = Column(JSONB, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("feed_name", "feed_entry_id"),)


class Model(Base):
    __tablename__ = "models"

    name = Column(String(128), primary_key=True)
    provider_class = Column(String(512), nullable=False)
    provider_specific_id = Column(String(512), nullable=False)
    active = Column(Boolean(), default=True)


class Summary(Base):
    __tablename__ = "summaries"

    feed_name = Column(ForeignKey("rss_feeds.name"), nullable=False)
    model_name = Column(ForeignKey("models.name"), nullable=False)
    feed_entry_id = Column(TEXT, nullable=False)
    content = Column(TEXT)
    sent = Column(Boolean(), default=False)

    __table_args__ = (PrimaryKeyConstraint("feed_name", "model_name", "feed_entry_id"),)


def insert_summary(
    session: Session, feed_name: str, feed_entry_id: str, model_name: str, content: str
):
    try:
        new_summary = Summary(
            feed_name=feed_name,
            model_name=model_name,
            content=content,
            feed_entry_id=feed_entry_id,
        )
        session.add(new_summary)
        session.commit()
    except Exception as e:
        session.rollback()
        raise Exception(f"Error inserting summary: {str(e)}")


def select_existing_summary(
    session: Session, feed_entry_id: str, model_name: str
) -> bool:
    summary = (
        session.query(Summary)
        .filter(
            Summary.model_name == model_name, Summary.feed_entry_id == feed_entry_id
        )
        .first()
    )

    return summary is not None


def update_summary_sent(
    session: Session, feed_name: str, model_name: int, feed_entry_id: str
):
    summary = (
        session.query(Summary)
        .filter(
            Summary.feed_name == feed_name,
            Summary.model_name == model_name,
            Summary.feed_entry_id == feed_entry_id,
        )
        .first()
    )

    if summary:
        summary.sent = True
        session.commit()


def select_unsent_summaries(session: Session) -> list:
    unsent_summaries = session.query(Summary).filter(Summary.sent == false()).all()

    return unsent_summaries


def insert_rss_feed(session: Session, name: str, url: str):
    try:
        new_feed = RssFeed(name=name, url=url)
        session.add(new_feed)
        session.commit()
    except Exception as e:
        session.rollback()
        raise Exception(f"Error inserting RSS feed: {str(e)}")


def delete_rss_feed(session: Session, name: str):
    rss_feed = session.query(RssFeed).filter(RssFeed.name == name).first()

    if rss_feed:
        rss_feed.active = False
        session.commit()


def select_active_rss_feeds(session: Session) -> list:
    active_feeds = session.query(RssFeed).filter(RssFeed.active == true()).all()

    return active_feeds


def insert_model(
    session: Session, name: str, provider_class: str, provider_specific_id: str
):
    try:
        new_model = Model(
            name=name,
            provider_class=provider_class,
            provider_specific_id=provider_specific_id,
        )
        session.add(new_model)
        session.commit()
    except Exception as e:
        session.rollback()
        raise Exception(f"Error inserting model: {str(e)}")


def delete_model(session: Session, name: str):
    model = session.query(Model).filter(Model.name == name).first()

    if model:
        model.active = False
        session.commit()


def select_active_models(session: Session) -> list:
    active_models = session.query(Model).filter(Model.active == true()).all()

    return active_models


def insert_rss_feed_entry(
    session: Session, feed_name: str, feed_entry_id: str, content: str
):
    try:
        new_rss_feed_entry = RSSEntry(
            feed_name=feed_name, feed_entry_id=feed_entry_id, raw_content=content
        )
        session.add(new_rss_feed_entry)
        session.commit()
    except IntegrityError:
        session.rollback()
        logger.info(
            f"RSS feed entry {feed_name}-{feed_entry_id} already exists in the DB"
        )
