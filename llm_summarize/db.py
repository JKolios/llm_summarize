import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy import Boolean, Column, ForeignKey, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import TEXT
from sqlalchemy.ext.declarative import declarative_base
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
    title = Column(TEXT)
    audio_file_path = Column(TEXT)
    sent = Column(Boolean(), default=False)

    __table_args__ = (PrimaryKeyConstraint("feed_name", "model_name", "feed_entry_id"),)


class Queries:
    def __init__(self, session):
        self.session = session

    def insert_summary(self, feed_name: str, feed_entry_id: str, model_name: str, content: str, title: str, audio_file_path: str):
        try:
            new_summary = Summary(
                feed_name=feed_name,
                model_name=model_name,
                content=content,
                feed_entry_id=feed_entry_id,
                title=title,
                audio_file_path=audio_file_path
            )
            self.session.add(new_summary)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise Exception(f"Error inserting summary: {str(e)}")


    def select_existing_summary_from_model(self, feed_entry_id: str, model_name: str
    ) -> bool:
        summary = (
            self.session.query(Summary)
            .filter(
                Summary.model_name == model_name, Summary.feed_entry_id == feed_entry_id
            )
            .first()
        )

        return summary is not None

    def select_existing_raw_feed_content(
        self, feed_name: str, feed_entry_id: str,
    ) -> bool:
        summary = (
            self.session.query(RSSEntry)
            .filter(
                RSSEntry.feed_name == feed_name, RSSEntry.feed_entry_id == feed_entry_id
            )
            .first()
        )

        return summary is not None


    def update_summary_sent(self, feed_name: str, model_name: int, feed_entry_id: str
    ):
        summary = (
            self.session.query(Summary)
            .filter(
                Summary.feed_name == feed_name,
                Summary.model_name == model_name,
                Summary.feed_entry_id == feed_entry_id,
            )
            .first()
        )

        if summary:
            summary.sent = True
            self.session.commit()


    def select_unsent_summaries(self) -> list:
        unsent_summaries = self.session.query(Summary).filter(Summary.sent == false()).all()

        return unsent_summaries


    def insert_rss_feed(self, name: str, url: str):
        try:
            new_feed = RssFeed(name=name, url=url)
            self.session.add(new_feed)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise Exception(f"Error inserting RSS feed: {str(e)}")


    def delete_rss_feed(self, name: str):
        rss_feed = self.session.query(RssFeed).filter(RssFeed.name == name).first()

        if rss_feed:
            rss_feed.active = False
            self.session.commit()


    def select_active_rss_feeds(self) -> list:
        active_feeds = self.session.query(RssFeed).filter(RssFeed.active == true()).all()

        return active_feeds


    def insert_model(self, name: str, provider_class: str, provider_specific_id: str
    ):
        try:
            new_model = Model(
                name=name,
                provider_class=provider_class,
                provider_specific_id=provider_specific_id,
            )
            self.session.add(new_model)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise Exception(f"Error inserting model: {str(e)}")


    def delete_model(self, name: str):
        model = self.session.query(Model).filter(Model.name == name).first()

        if model:
            model.active = False
            self.session.commit()


    def select_active_models(self) -> list:
        active_models = self.session.query(Model).filter(Model.active == true()).all()

        return active_models


    def insert_rss_feed_entry(self, feed_name: str, feed_entry_id: str, content: str
    ):
        try:
            new_rss_feed_entry = RSSEntry(
                feed_name=feed_name, feed_entry_id=feed_entry_id, raw_content=content
            )
            self.session.add(new_rss_feed_entry)
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            logger.info(
                f"RSS feed entry {feed_name}-{feed_entry_id} already exists in the DB"
            )
