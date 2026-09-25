from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

BigIntPk = BigInteger().with_variant(Integer, "sqlite")


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    leagues: Mapped[list[League]] = relationship(
        back_populates="sport", cascade="all, delete-orphan"
    )


class League(Base):
    __tablename__ = "leagues"
    __table_args__ = (Index("ix_leagues_sport_id", "sport_id"),)

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    sport_id: Mapped[int] = mapped_column(
        ForeignKey("sports.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(String(191))
    uid: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(50))
    logo_url: Mapped[str | None] = mapped_column(Text)
    season_year: Mapped[int | None] = mapped_column(SmallInteger)
    season_type: Mapped[str | None] = mapped_column(String(50))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    sport: Mapped[Sport] = relationship(back_populates="leagues")
    teams: Mapped[list[Team]] = relationship(back_populates="league")
    events: Mapped[list[Event]] = relationship(
        back_populates="league", cascade="all, delete-orphan", passive_deletes=True
    )
    news_articles: Mapped[list[NewsArticle]] = relationship(
        back_populates="league", cascade="all, delete-orphan", passive_deletes=True
    )
    rankings: Mapped[list[Ranking]] = relationship(
        back_populates="league", cascade="all, delete-orphan", passive_deletes=True
    )
    sync_states: Mapped[list[SyncState]] = relationship(
        back_populates="league", cascade="all, delete-orphan", passive_deletes=True
    )


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("league_id", "source_id", name="uq_teams_league_source"),
        Index("ix_teams_league_id", "league_id"),
        Index("ix_teams_league_slug", "league_id", "slug"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(191), nullable=False)
    uid: Mapped[str | None] = mapped_column(String(255))
    slug: Mapped[str | None] = mapped_column(String(150))
    location: Mapped[str | None] = mapped_column(String(150))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(50))
    display_name: Mapped[str | None] = mapped_column(String(300))
    short_display_name: Mapped[str | None] = mapped_column(String(300))
    color: Mapped[str | None] = mapped_column(String(20))
    alternate_color: Mapped[str | None] = mapped_column(String(20))
    logo_url: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[str | None] = mapped_column(String(50))
    record: Mapped[str | None] = mapped_column(String(100))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    detail_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    league: Mapped[League] = relationship(back_populates="teams")
    event_competitors: Mapped[list[EventCompetitor]] = relationship(back_populates="team")
    ranking_entries: Mapped[list[RankingEntry]] = relationship(back_populates="team")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("league_id", "source_id", name="uq_events_league_source"),
        Index("ix_events_league_start_at", "league_id", "start_at"),
        Index("ix_events_status", "status_state", "completed"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(191), nullable=False)
    uid: Mapped[str | None] = mapped_column(String(255))
    start_at: Mapped[datetime | None] = mapped_column(DateTime)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(300))
    season_year: Mapped[int | None] = mapped_column(SmallInteger)
    season_type: Mapped[str | None] = mapped_column(String(50))
    season_name: Mapped[str | None] = mapped_column(String(100))
    week: Mapped[int | None] = mapped_column(SmallInteger)
    status_id: Mapped[str | None] = mapped_column(String(100))
    status_name: Mapped[str | None] = mapped_column(String(150))
    status_state: Mapped[str | None] = mapped_column(String(50))
    status_detail: Mapped[str | None] = mapped_column(String(300))
    status_short_detail: Mapped[str | None] = mapped_column(String(300))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    clock: Mapped[int | None] = mapped_column(Integer)
    period: Mapped[int | None] = mapped_column(Integer)
    neutral_site: Mapped[bool | None] = mapped_column(Boolean)
    conference_competition: Mapped[bool | None] = mapped_column(Boolean)
    venue_id: Mapped[str | None] = mapped_column(String(191))
    venue_name: Mapped[str | None] = mapped_column(String(500))
    venue_address: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    summary_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    league: Mapped[League] = relationship(back_populates="events")
    competitors: Mapped[list[EventCompetitor]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="EventCompetitor.sort_order, EventCompetitor.source_id",
    )


class EventCompetitor(Base):
    __tablename__ = "event_competitors"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "competition_id", "source_id", name="uq_event_competitors_source"
        ),
        Index("ix_event_competitors_team_id", "team_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    competition_id: Mapped[str | None] = mapped_column(String(191))
    source_id: Mapped[str] = mapped_column(String(191), nullable=False)
    uid: Mapped[str | None] = mapped_column(String(255))
    competitor_type: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[int | None] = mapped_column(SmallInteger)
    home_away: Mapped[str | None] = mapped_column(String(20))
    winner: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[str | None] = mapped_column(String(100))
    linescores: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    records: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    statistics: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    leaders: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    event: Mapped[Event] = relationship(back_populates="competitors")
    team: Mapped[Team | None] = relationship(back_populates="event_competitors")


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("league_id", "source_id", name="uq_news_articles_league_source"),
        Index("ix_news_articles_league_published", "league_id", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(191), nullable=False)
    uid: Mapped[str | None] = mapped_column(String(255))
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime)
    article_type: Mapped[str | None] = mapped_column(String(100))
    byline: Mapped[str | None] = mapped_column(String(500))
    link_url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    league: Mapped[League] = relationship(back_populates="news_articles")


class Ranking(Base):
    __tablename__ = "rankings"
    __table_args__ = (
        UniqueConstraint("league_id", "source_id", name="uq_rankings_league_source"),
        Index("ix_rankings_league_season_week", "league_id", "season_year", "week"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(191), nullable=False)
    uid: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(150))
    full_name: Mapped[str | None] = mapped_column(String(500))
    season_year: Mapped[int | None] = mapped_column(SmallInteger)
    week: Mapped[int | None] = mapped_column(SmallInteger)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    league: Mapped[League] = relationship(back_populates="rankings")
    entries: Mapped[list[RankingEntry]] = relationship(
        back_populates="ranking",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RankingEntry.rank, RankingEntry.source_id",
    )


class RankingEntry(Base):
    __tablename__ = "ranking_entries"
    __table_args__ = (
        UniqueConstraint("ranking_id", "source_id", name="uq_ranking_entries_ranking_source"),
        Index("ix_ranking_entries_team_id", "team_id"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    ranking_id: Mapped[int] = mapped_column(
        ForeignKey("rankings.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    source_id: Mapped[str] = mapped_column(String(191), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    previous_rank: Mapped[int | None] = mapped_column(Integer)
    first_rank: Mapped[int | None] = mapped_column(Integer)
    rank_delta: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    record: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    ranking: Mapped[Ranking] = relationship(back_populates="entries")
    team: Mapped[Team | None] = relationship(back_populates="ranking_entries")


class SyncState(Base):
    __tablename__ = "sync_states"
    __table_args__ = (
        UniqueConstraint("league_id", "resource", name="uq_sync_states_league_resource"),
    )

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_successful_sync: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)

    league: Mapped[League] = relationship(back_populates="sync_states")
