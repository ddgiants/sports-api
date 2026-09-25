from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Event,
    EventCompetitor,
    League,
    NewsArticle,
    Ranking,
    RankingEntry,
    Sport,
    Team,
)


@pytest.mark.asyncio
async def test_normalized_api_reads_seeded_database(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _seed(session)

    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}

    response = await api_client.get("/api/v1/leagues", params={"sport": "football"})
    assert response.status_code == 200
    leagues = response.json()
    assert leagues["total"] == 1
    assert leagues["items"][0]["slug"] == "nfl"

    response = await api_client.get("/api/v1/events", params={"sport": "football"})
    assert response.status_code == 200
    events = response.json()
    assert events["total"] == 1
    assert events["items"][0]["source_id"] == "event-1"
    competitor_teams = {
        competitor["team"]["abbreviation"]
        for competitor in events["items"][0]["competitors"]
        if competitor["team"]
    }
    assert competitor_teams == {"GB", "CHI"}

    response = await api_client.get("/api/v1/events", params={"source_id": "event-1"})
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = await api_client.get(
        "/api/v1/events",
        params={"starts_after": "2026-09-24T23:00:00-05:00"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0

    response = await api_client.get("/api/v1/events/1")
    assert response.status_code == 200
    assert response.json()["league"]["slug"] == "nfl"


@pytest.mark.asyncio
async def test_api_returns_not_found_for_missing_resource(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/teams/999")
    assert response.status_code == 404


async def _seed(session: AsyncSession) -> None:
    sport = Sport(slug="football", name="Football")
    session.add(sport)
    await session.flush()
    league = League(
        sport_id=sport.id,
        source_id="28",
        slug="nfl",
        name="National Football League",
        abbreviation="NFL",
        synced_at=datetime(2026, 9, 24),
    )
    session.add(league)
    await session.flush()
    home = Team(
        league_id=league.id,
        source_id="9",
        name="Packers",
        abbreviation="GB",
        display_name="Green Bay Packers",
        synced_at=datetime(2026, 9, 24),
    )
    away = Team(
        league_id=league.id,
        source_id="20",
        name="Bears",
        abbreviation="CHI",
        display_name="Chicago Bears",
        synced_at=datetime(2026, 9, 24),
    )
    event = Event(
        league_id=league.id,
        source_id="event-1",
        name="Bears at Packers",
        start_at=datetime(2026, 9, 25),
        completed=False,
        synced_at=datetime(2026, 9, 24),
    )
    session.add_all([home, away, event])
    await session.flush()
    session.add_all(
        [
            EventCompetitor(
                event_id=event.id,
                team_id=home.id,
                source_id="9",
                competition_id="event-1",
                home_away="home",
                score="0",
                synced_at=datetime(2026, 9, 24),
            ),
            EventCompetitor(
                event_id=event.id,
                team_id=away.id,
                source_id="20",
                competition_id="event-1",
                home_away="away",
                score="0",
                synced_at=datetime(2026, 9, 24),
            ),
            NewsArticle(
                league_id=league.id,
                source_id="123",
                headline="A headline",
                published_at=datetime(2026, 9, 24),
                synced_at=datetime(2026, 9, 24),
            ),
        ]
    )
    ranking = Ranking(
        league_id=league.id,
        source_id="1",
        name="AP Poll",
        season_year=2026,
        week=4,
        synced_at=datetime(2026, 9, 24),
    )
    session.add(ranking)
    await session.flush()
    session.add(
        RankingEntry(
            ranking_id=ranking.id,
            team_id=home.id,
            source_id="9",
            rank=1,
            points=Decimal("1706"),
            synced_at=datetime(2026, 9, 24),
        )
    )
    await session.commit()
