from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import session_dependency
from app.models import League, Sport, Team
from app.schemas.common import Page
from app.schemas.sports import TeamDetail, TeamOut

router = APIRouter(tags=["teams"])
Session = Annotated[AsyncSession, Depends(session_dependency)]


@router.get("/teams", response_model=Page[TeamOut], summary="List teams")
async def list_teams(
    session: Session,
    league_id: Annotated[int | None, Query(ge=1)] = None,
    sport: Annotated[str | None, Query(description="Filter by sport slug")] = None,
    source_id: Annotated[str | None, Query(max_length=191)] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TeamOut]:
    filters = []
    if league_id is not None:
        filters.append(Team.league_id == league_id)
    if sport:
        filters.append(Sport.slug == sport)
    if source_id:
        filters.append(Team.source_id == source_id)
    if search:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Team.name.ilike(pattern),
                Team.location.ilike(pattern),
                Team.display_name.ilike(pattern),
                Team.abbreviation.ilike(pattern),
            )
        )

    total = await session.scalar(
        select(func.count(Team.id)).join(League).join(Sport).where(*filters)
    )
    result = await session.scalars(
        select(Team)
        .join(League)
        .join(Sport)
        .where(*filters)
        .order_by(Team.name, Team.id)
        .limit(limit)
        .offset(offset)
    )
    return Page[TeamOut](
        items=[TeamOut.model_validate(item) for item in result],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/teams/{team_id}", response_model=TeamDetail, summary="Get a team by ID")
async def get_team(team_id: int, session: Session) -> TeamDetail:
    team = await session.scalar(
        select(Team)
        .where(Team.id == team_id)
        .options(selectinload(Team.league).selectinload(League.sport))
    )
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return TeamDetail.model_validate(team)
