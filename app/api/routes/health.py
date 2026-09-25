from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import session_dependency

router = APIRouter(tags=["health"])
Session = Annotated[AsyncSession, Depends(session_dependency)]


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthOut, summary="Check API and database health")
async def health(session: Session) -> HealthOut:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    return HealthOut()
