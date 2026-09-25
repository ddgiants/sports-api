from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import session_dependency
from app.models import League, Sport, SyncState
from app.schemas.common import Page
from app.schemas.sports import LeagueOut, SyncStateOut

router = APIRouter(tags=["leagues"])
Session = Annotated[AsyncSession, Depends(session_dependency)]


@router.get("/leagues", response_model=Page[LeagueOut], summary="List leagues")
async def list_leagues(
    session: Session,
    sport: Annotated[str | None, Query(description="Filter by sport slug")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[LeagueOut]:
    filters = []
    if sport:
        filters.append(Sport.slug == sport)

    total = await session.scalar(select(func.count(League.id)).join(Sport).where(*filters))
    result = await session.scalars(
        select(League)
        .join(Sport)
        .where(*filters)
        .options(selectinload(League.sport))
        .order_by(Sport.slug, League.slug)
        .limit(limit)
        .offset(offset)
    )
    return Page[LeagueOut](
        items=[LeagueOut.model_validate(item) for item in result],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/leagues/{league_id}", response_model=LeagueOut, summary="Get a league by ID")
async def get_league(league_id: int, session: Session) -> LeagueOut:
    league = await session.scalar(
        select(League).where(League.id == league_id).options(selectinload(League.sport))
    )
    if league is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    return LeagueOut.model_validate(league)


@router.get(
    "/sync-status",
    response_model=list[SyncStateOut],
    summary="List source synchronization states",
)
async def list_sync_states(session: Session) -> list[SyncStateOut]:
    states = await session.scalars(
        select(SyncState).order_by(SyncState.league_id, SyncState.resource)
    )
    return [SyncStateOut.model_validate(state) for state in states]
