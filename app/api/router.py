from fastapi import APIRouter

from app.api.routes import events, health, leagues, news, rankings, teams

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(leagues.router)
api_router.include_router(teams.router)
api_router.include_router(events.router)
api_router.include_router(news.router)
api_router.include_router(rankings.router)
