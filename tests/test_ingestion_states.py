from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import Event, NewsArticle, SyncState
from app.services import ingestion
from app.services.catalog import LeagueSpec
from app.services.ingestion import SportsIngestor, SyncOptions
from tests.test_ingestion import FailingTeamDetailClient, FakeESPNClient


class MalformedScoreboardClient(FakeESPNClient):
    async def get_json(
        self, path: str, *, params: Mapping[str, str | int] | None = None
    ) -> tuple[dict[str, Any], str]:
        if path.endswith("/scoreboard"):
            return {"leagues": []}, "https://example.test/scoreboard"
        return await super().get_json(path, params=params)


@pytest.mark.asyncio
async def test_malformed_payload_does_not_replace_previous_snapshot(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        database_url="sqlite+aiosqlite://",
        espn_include_team_details=False,
        espn_soccer_leagues="",
    )
    spec = LeagueSpec("football", "Football", "nfl", "NFL", "NFL", "28")
    monkeypatch.setattr(ingestion, "ESPNClient", FakeESPNClient)
    await SportsIngestor(settings, session_factory).sync_league(
        spec, SyncOptions(include_team_details=False)
    )

    monkeypatch.setattr(ingestion, "ESPNClient", MalformedScoreboardClient)
    result = await SportsIngestor(settings, session_factory).sync_league(
        spec, SyncOptions(include_team_details=False)
    )
    assert result.success is False
    async with session_factory() as session:
        assert await session.scalar(select(Event.id)) is not None
        assert await session.scalar(select(NewsArticle.id)) is not None


@pytest.mark.asyncio
async def test_partial_warnings_are_reported_per_resource(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingestion, "ESPNClient", FailingTeamDetailClient)
    settings = Settings(
        database_url="sqlite+aiosqlite://",
        espn_include_team_details=True,
        espn_strict_sync=False,
        espn_soccer_leagues="",
    )
    spec = LeagueSpec("football", "Football", "nfl", "NFL", "NFL", "28")

    result = await SportsIngestor(settings, session_factory).sync_league(
        spec, SyncOptions(include_team_details=True, strict=False)
    )

    assert result.success is True
    assert result.warnings
    async with session_factory() as session:
        states = {
            state.resource: state.status for state in await session.scalars(select(SyncState))
        }
    assert states["team-details"] == "partial"
    assert states["teams"] == "success"
    assert states["scoreboard"] == "success"
    assert states["news"] == "success"
