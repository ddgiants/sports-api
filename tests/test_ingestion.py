from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import Event, NewsArticle, Team
from app.services import ingestion
from app.services.catalog import LeagueSpec
from app.services.ingestion import (
    ResourceSyncError,
    SportsIngestor,
    SyncOptions,
    _validate_resource_payload,
)
from tests.fixtures import NEWS, SCOREBOARD, TEAM_LIST


class FakeESPNClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> FakeESPNClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get_json(
        self, path: str, *, params: Mapping[str, str | int] | None = None
    ) -> tuple[dict[str, Any], str]:
        payloads = {
            "football/nfl/teams": TEAM_LIST,
            "football/nfl/scoreboard": SCOREBOARD,
            "football/nfl/news": NEWS,
        }
        return payloads[path], f"https://example.test/{path}"


class FailingTeamDetailClient(FakeESPNClient):
    async def get_json(
        self, path: str, *, params: Mapping[str, str | int] | None = None
    ) -> tuple[dict[str, Any], str]:
        if "/teams/" in path:
            raise RuntimeError("detail unavailable")
        return await super().get_json(path, params=params)


def test_malformed_resource_envelope_is_rejected() -> None:
    with pytest.raises(ResourceSyncError, match="events"):
        _validate_resource_payload("scoreboard", {"leagues": []})


@pytest.mark.asyncio
async def test_ingestor_persists_a_complete_atomic_snapshot(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingestion, "ESPNClient", FakeESPNClient)
    settings = Settings(
        database_url="sqlite+aiosqlite://",
        espn_include_team_details=False,
        espn_strict_sync=True,
        espn_soccer_leagues="",
    )
    spec = LeagueSpec("football", "Football", "nfl", "NFL", "NFL", "28")

    result = await SportsIngestor(settings, session_factory).sync_league(
        spec, SyncOptions(include_team_details=False)
    )

    assert result.success is True
    assert result.counts == {
        "teams": 2,
        "events": 1,
        "competitors": 2,
        "news": 1,
        "rankings": 0,
        "ranking_entries": 0,
    }
    async with session_factory() as session:
        assert await session.scalar(select(func.count(Team.id))) == 2
        assert await session.scalar(select(func.count(Event.id))) == 1
        assert await session.scalar(select(func.count(NewsArticle.id))) == 1
        first_event_id = await session.scalar(select(Event.id))
        first_article_id = await session.scalar(select(NewsArticle.id))

    second_result = await SportsIngestor(settings, session_factory).sync_league(
        spec, SyncOptions(include_team_details=False)
    )
    assert second_result.success is True
    async with session_factory() as session:
        assert await session.scalar(select(Event.id)) == first_event_id
        assert await session.scalar(select(NewsArticle.id)) == first_article_id
