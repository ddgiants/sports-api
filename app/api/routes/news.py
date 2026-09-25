from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import session_dependency
from app.api.time import to_naive_utc
from app.models import League, NewsArticle, Sport
from app.schemas.common import Page
from app.schemas.sports import NewsArticleDetail, NewsArticleOut

router = APIRouter(tags=["news"])
Session = Annotated[AsyncSession, Depends(session_dependency)]


@router.get("/news", response_model=Page[NewsArticleOut], summary="List current news")
async def list_news(
    session: Session,
    league_id: Annotated[int | None, Query(ge=1)] = None,
    sport: Annotated[str | None, Query(description="Filter by sport slug")] = None,
    source_id: Annotated[str | None, Query(max_length=191)] = None,
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    published_after: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[NewsArticleOut]:
    filters = []
    if league_id is not None:
        filters.append(NewsArticle.league_id == league_id)
    if sport:
        filters.append(Sport.slug == sport)
    if source_id:
        filters.append(NewsArticle.source_id == source_id)
    if query:
        pattern = f"%{query}%"
        filters.append(
            or_(
                NewsArticle.headline.ilike(pattern),
                NewsArticle.description.ilike(pattern),
            )
        )
    if published_after is not None:
        filters.append(NewsArticle.published_at >= to_naive_utc(published_after))

    total = await session.scalar(
        select(func.count(NewsArticle.id)).join(League).join(Sport).where(*filters)
    )
    result = await session.scalars(
        select(NewsArticle)
        .join(League)
        .join(Sport)
        .where(*filters)
        .order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page[NewsArticleOut](
        items=[NewsArticleOut.model_validate(article) for article in result],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/news/{article_id}", response_model=NewsArticleDetail, summary="Get a news article by ID"
)
async def get_news(article_id: int, session: Session) -> NewsArticleDetail:
    article = await session.scalar(select(NewsArticle).where(NewsArticle.id == article_id))
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News article not found")
    return NewsArticleDetail.model_validate(article)
