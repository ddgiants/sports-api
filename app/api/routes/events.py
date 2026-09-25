from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import session_dependency
from app.api.time import to_naive_utc
from app.models import Event, EventCompetitor, League, Sport
from app.schemas.common import Page
from app.schemas.sports import EventDetail, EventListOut

router = APIRouter(tags=["events"])
Session = Annotated[AsyncSession, Depends(session_dependency)]


@router.get("/events", response_model=Page[EventListOut], summary="List current events")
async def list_events(
    session: Session,
    league_id: Annotated[int | None, Query(ge=1)] = None,
    sport: Annotated[str | None, Query(description="Filter by sport slug")] = None,
    source_id: Annotated[str | None, Query(max_length=191)] = None,
    team_id: Annotated[int | None, Query(ge=1)] = None,
    status_state: Annotated[str | None, Query(max_length=50)] = None,
    completed: bool | None = None,
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EventListOut]:
    filters = []
    if league_id is not None:
        filters.append(Event.league_id == league_id)
    if sport:
        filters.append(Sport.slug == sport)
    if source_id:
        filters.append(Event.source_id == source_id)
    if status_state:
        filters.append(Event.status_state == status_state)
    if completed is not None:
        filters.append(Event.completed == completed)
    if starts_after is not None:
        filters.append(Event.start_at >= to_naive_utc(starts_after))
    if starts_before is not None:
        filters.append(Event.start_at <= to_naive_utc(starts_before))

    count_stmt = select(func.count(func.distinct(Event.id))).join(League).join(Sport)
    result_stmt = select(Event).join(League).join(Sport)
    if team_id is not None:
        count_stmt = count_stmt.join(EventCompetitor)
        result_stmt = result_stmt.join(EventCompetitor).distinct()
        filters.append(EventCompetitor.team_id == team_id)

    total = await session.scalar(count_stmt.where(*filters))
    events = await session.scalars(
        result_stmt.where(*filters)
        .options(selectinload(Event.competitors).selectinload(EventCompetitor.team))
        .order_by(Event.start_at.desc(), Event.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page[EventListOut](
        items=[EventListOut.model_validate(event) for event in events],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}", response_model=EventDetail, summary="Get an event by ID")
async def get_event(event_id: int, session: Session) -> EventDetail:
    event = await session.scalar(
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.league).selectinload(League.sport),
            selectinload(Event.competitors).selectinload(EventCompetitor.team),
        )
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventDetail.model_validate(event)
