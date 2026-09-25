from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "synced_at",
        "start_at",
        "published_at",
        "last_modified_at",
        "last_attempt_at",
        "last_successful_sync",
        check_fields=False,
    )
    def serialize_utc_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class SportOut(ORMModel):
    id: int
    slug: str
    name: str


class LeagueOut(ORMModel):
    id: int
    source_id: str | None
    uid: str | None
    slug: str
    name: str
    abbreviation: str | None
    logo_url: str | None
    season_year: int | None
    season_type: str | None
    synced_at: datetime
    sport: SportOut


class TeamOut(ORMModel):
    id: int
    league_id: int
    source_id: str
    uid: str | None
    slug: str | None
    location: str | None
    name: str
    abbreviation: str | None
    display_name: str | None
    short_display_name: str | None
    color: str | None
    alternate_color: str | None
    logo_url: str | None
    rank: str | None
    record: str | None
    synced_at: datetime


class TeamDetail(TeamOut):
    league: LeagueOut
    raw_payload: dict[str, Any] | None
    detail_payload: dict[str, Any] | None


class CompetitorOut(ORMModel):
    id: int
    source_id: str
    competition_id: str | None
    uid: str | None
    competitor_type: str | None
    sort_order: int | None
    home_away: str | None
    winner: bool | None
    score: str | None
    linescores: list[dict[str, Any]] | None
    records: list[dict[str, Any]] | None
    statistics: list[dict[str, Any]] | None
    leaders: list[dict[str, Any]] | None
    team: TeamOut | None


class CompetitorListOut(ORMModel):
    id: int
    source_id: str
    competition_id: str | None
    home_away: str | None
    winner: bool | None
    score: str | None
    team: TeamOut | None


class EventOut(ORMModel):
    id: int
    league_id: int
    source_id: str
    uid: str | None
    start_at: datetime | None
    name: str
    short_name: str | None
    season_year: int | None
    season_type: str | None
    season_name: str | None
    week: int | None
    status_id: str | None
    status_name: str | None
    status_state: str | None
    status_detail: str | None
    status_short_detail: str | None
    completed: bool
    clock: int | None
    period: int | None
    neutral_site: bool | None
    conference_competition: bool | None
    venue_id: str | None
    venue_name: str | None
    venue_address: dict[str, Any] | None
    synced_at: datetime
    competitors: list[CompetitorOut] = Field(default_factory=list)


class EventListOut(EventOut):
    competitors: list[CompetitorListOut] = Field(  # type: ignore[assignment]
        default_factory=list
    )


class EventDetail(EventOut):
    league: LeagueOut
    raw_payload: dict[str, Any] | None
    summary_payload: dict[str, Any] | None


class NewsArticleOut(ORMModel):
    id: int
    league_id: int
    source_id: str
    uid: str | None
    headline: str
    description: str | None
    published_at: datetime | None
    last_modified_at: datetime | None
    article_type: str | None
    byline: str | None
    link_url: str | None
    image_url: str | None
    synced_at: datetime


class NewsArticleDetail(NewsArticleOut):
    categories: list[dict[str, Any]] | None
    raw_payload: dict[str, Any] | None


class RankingEntryOut(ORMModel):
    id: int
    source_id: str
    rank: int | None
    previous_rank: int | None
    first_rank: int | None
    rank_delta: int | None
    points: float | None
    record: str | None
    note: str | None
    team: TeamOut | None


class RankingEntryListOut(ORMModel):
    id: int
    source_id: str
    rank: int | None
    points: float | None
    team: TeamOut | None


class RankingOut(ORMModel):
    id: int
    league_id: int
    source_id: str
    uid: str | None
    name: str
    short_name: str | None
    full_name: str | None
    season_year: int | None
    week: int | None
    synced_at: datetime
    entries: list[RankingEntryOut] = Field(default_factory=list)


class RankingListOut(RankingOut):
    entries: list[RankingEntryListOut] = Field(  # type: ignore[assignment]
        default_factory=list
    )


class RankingDetail(RankingOut):
    raw_payload: dict[str, Any] | None


class SyncStateOut(ORMModel):
    id: int
    league_id: int
    resource: str
    status: str
    source_url: str | None
    item_count: int
    last_attempt_at: datetime | None
    last_successful_sync: datetime | None
    error_message: str | None
