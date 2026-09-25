from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import session_dependency
from app.models import Ranking, RankingEntry
from app.schemas.common import Page
from app.schemas.sports import RankingDetail, RankingListOut

router = APIRouter(tags=["rankings"])
Session = Annotated[AsyncSession, Depends(session_dependency)]
entry_load = selectinload(Ranking.entries).selectinload(RankingEntry.team)


@router.get("/rankings", response_model=Page[RankingListOut], summary="List current rankings")
async def list_rankings(
    session: Session,
    league_id: Annotated[int | None, Query(ge=1)] = None,
    source_id: Annotated[str | None, Query(max_length=191)] = None,
    season: Annotated[int | None, Query(ge=1900, le=2200)] = None,
    week: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RankingListOut]:
    filters = []
    if league_id is not None:
        filters.append(Ranking.league_id == league_id)
    if source_id:
        filters.append(Ranking.source_id == source_id)
    if season is not None:
        filters.append(Ranking.season_year == season)
    if week is not None:
        filters.append(Ranking.week == week)

    total = await session.scalar(select(func.count(Ranking.id)).where(*filters))
    rankings = await session.scalars(
        select(Ranking)
        .where(*filters)
        .options(entry_load)
        .order_by(Ranking.season_year.desc(), Ranking.name, Ranking.id)
        .limit(limit)
        .offset(offset)
    )
    return Page[RankingListOut](
        items=[RankingListOut.model_validate(ranking) for ranking in rankings],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/rankings/{ranking_id}", response_model=RankingDetail, summary="Get ranking by ID")
async def get_ranking(ranking_id: int, session: Session) -> RankingDetail:
    ranking = await session.scalar(
        select(Ranking).where(Ranking.id == ranking_id).options(entry_load)
    )
    if ranking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ranking not found")
    return RankingDetail.model_validate(ranking)
