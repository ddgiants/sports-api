from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import quote

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db.base import utcnow
from app.db.session import build_engine
from app.models import (
    Event,
    EventCompetitor,
    League,
    NewsArticle,
    Ranking,
    RankingEntry,
    Sport,
    SyncState,
    Team,
)
from app.services.catalog import LeagueSpec, league_catalog
from app.services.espn import ESPNClient, ESPNClientError
from app.services.parsers import (
    parse_news,
    parse_rankings,
    parse_scoreboard,
    parse_team,
    parse_team_detail,
    parse_team_list,
)


class LeagueSyncError(RuntimeError):
    pass


class ResourceSyncError(LeagueSyncError):
    def __init__(self, resource: str, message: str) -> None:
        super().__init__(message)
        self.resource = resource


@dataclass
class SyncOptions:
    dates: str | None = None
    calendar: str | None = None
    include_team_details: bool | None = None
    strict: bool | None = None

    def scoreboard_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.dates:
            params["dates"] = self.dates
        if self.calendar:
            params["calendar"] = self.calendar
        return params


@dataclass
class SyncResult:
    selector: str
    success: bool
    counts: dict[str, int] = field(default_factory=dict)
    source_urls: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class Fetched:
    payload: dict[str, Any]
    url: str


@dataclass
class LeagueSnapshot:
    league_update: dict[str, Any]
    teams: list[dict[str, Any]]
    events: list[dict[str, Any]]
    competitors: list[dict[str, Any]]
    news: list[dict[str, Any]]
    rankings: list[dict[str, Any]]
    source_urls: dict[str, str]
    resources: list[str]
    warnings_by_resource: dict[str, list[str]]

    @property
    def warnings(self) -> list[str]:
        return [warning for warnings in self.warnings_by_resource.values() for warning in warnings]


class SportsIngestor:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        engine: AsyncEngine | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        bound_engine = getattr(session_factory, "kw", {}).get("bind")
        self.engine = engine or (bound_engine if isinstance(bound_engine, AsyncEngine) else None)

    async def sync_league(self, spec: LeagueSpec, options: SyncOptions | None = None) -> SyncResult:
        options = options or SyncOptions()
        async with self.session_factory() as session:
            lock_name = f"sports-api:{hashlib.sha256(spec.selector.encode()).hexdigest()[:40]}"
            async with self._league_lock(lock_name) as locked:
                if not locked:
                    return SyncResult(
                        selector=spec.selector,
                        success=False,
                        error="Another synchronization for this league is already running",
                    )
                league_id = await self._ensure_league(session, spec)
                try:
                    await self._mark_attempt(session, league_id, spec, options)
                    try:
                        snapshot = await self._fetch_snapshot(session, spec, options)
                        await session.rollback()
                        await self._replace_snapshot(session, league_id, snapshot)
                    except Exception as exc:
                        await session.rollback()
                        failed_resource = (
                            exc.resource if isinstance(exc, ResourceSyncError) else None
                        )
                        await self._record_failure(
                            session,
                            league_id,
                            spec,
                            options,
                            str(exc),
                            failed_resource,
                        )
                        if isinstance(exc, (LeagueSyncError, ESPNClientError)):
                            return SyncResult(selector=spec.selector, success=False, error=str(exc))
                        raise
                    return SyncResult(
                        selector=spec.selector,
                        success=True,
                        counts={
                            "teams": len(snapshot.teams),
                            "events": len(snapshot.events),
                            "competitors": len(snapshot.competitors),
                            "news": len(snapshot.news),
                            "rankings": len(snapshot.rankings),
                            "ranking_entries": sum(
                                len(item["entries"]) for item in snapshot.rankings
                            ),
                        },
                        source_urls=snapshot.source_urls,
                        warnings=snapshot.warnings,
                    )
                finally:
                    await session.rollback()

    async def _fetch_snapshot(
        self, session: AsyncSession, spec: LeagueSpec, options: SyncOptions
    ) -> LeagueSnapshot:
        async with ESPNClient(
            self.settings.espn_base_url,
            timeout_seconds=self.settings.espn_timeout_seconds,
            max_retries=self.settings.espn_max_retries,
            user_agent=self.settings.espn_user_agent,
        ) as client:
            resource_names = [
                resource
                for resource in ("teams", "scoreboard", "news", "rankings")
                if spec.supports(resource)
            ]
            fetched = await self._fetch_base_resources(client, spec, resource_names, options)
            for resource, result in fetched.items():
                if isinstance(result, Exception):
                    raise ResourceSyncError(
                        resource, f"{spec.selector} {resource} failed: {result}"
                    ) from result

            league_id = await self._league_id(session, spec.slug)
            teams: dict[str, dict[str, Any]] = {}
            league_update: dict[str, Any] = {}
            team_result = fetched.get("teams")
            if isinstance(team_result, Fetched):
                metadata, parsed_teams = parse_team_list(team_result.payload, league_id, spec)
                league_update = metadata
                for team in parsed_teams:
                    teams[team["source_id"]] = team

            scoreboard: Any = None
            scoreboard_result = fetched.get("scoreboard")
            if isinstance(scoreboard_result, Fetched):
                scoreboard = parse_scoreboard(scoreboard_result.payload, league_id, spec)
                league_update = _prefer_metadata(scoreboard.league_update, league_update)
                for team in scoreboard.teams:
                    teams[team["source_id"]] = _merge_team(teams.get(team["source_id"]), team)

            summaries, summary_urls, summary_warnings = await self._fetch_summaries(
                client, spec, scoreboard, options.strict
            )
            if scoreboard:
                for event in scoreboard.events:
                    event["summary_payload"] = summaries.get(event["source_id"])

            include_details = (
                self.settings.espn_include_team_details
                if options.include_team_details is None
                else options.include_team_details
            )
            details, detail_urls, detail_warnings = await self._fetch_team_details(
                client, spec, teams, include_details, options.strict
            )
            for source_id, detail in details.items():
                if source_id in teams:
                    teams[source_id] = (
                        parse_team_detail(detail, league_id, teams[source_id]) or teams[source_id]
                    )

            ranking_result = fetched.get("rankings")
            if isinstance(ranking_result, Fetched):
                rankings = parse_rankings(ranking_result.payload, league_id)
                for ranking in rankings:
                    for entry in ranking["entries"]:
                        ranking_team = _ranking_team(entry["raw_payload"], league_id)
                        if ranking_team:
                            teams[ranking_team["source_id"]] = _merge_team(
                                teams.get(ranking_team["source_id"]), ranking_team
                            )
            else:
                rankings = []

            news_result = fetched.get("news")
            news = (
                parse_news(news_result.payload, league_id)
                if isinstance(news_result, Fetched)
                else []
            )
            source_urls = {
                resource: result.url
                for resource, result in fetched.items()
                if isinstance(result, Fetched)
            }
            source_urls.update(summary_urls)
            source_urls.update(detail_urls)
            if not scoreboard:
                scoreboard = parse_scoreboard({}, league_id, spec)
            return LeagueSnapshot(
                league_update=league_update,
                teams=list(teams.values()),
                events=scoreboard.events,
                competitors=scoreboard.competitors,
                news=news,
                rankings=rankings,
                source_urls=source_urls,
                resources=self._resources(spec, options),
                warnings_by_resource={
                    "summaries": summary_warnings,
                    "team-details": detail_warnings,
                },
            )

    async def _fetch_base_resources(
        self,
        client: ESPNClient,
        spec: LeagueSpec,
        resources: list[str],
        options: SyncOptions,
    ) -> dict[str, Fetched | Exception]:
        async def fetch(resource: str) -> Fetched | Exception:
            try:
                params: dict[str, str | int] = {}
                if resource == "scoreboard":
                    params.update(options.scoreboard_params())
                elif resource == "teams":
                    params["limit"] = self.settings.espn_team_limit
                elif resource == "news":
                    params["limit"] = self.settings.espn_news_limit
                payload, url = await client.get_json(
                    f"{spec.api_path}/{resource}", params=params or None
                )
                _validate_resource_payload(resource, payload)
                return Fetched(payload=payload, url=url)
            except Exception as exc:  # gathered and reported per resource
                return exc

        gathered = await asyncio.gather(*(fetch(resource) for resource in resources))
        return dict(zip(resources, gathered, strict=True))

    async def _fetch_summaries(
        self,
        client: ESPNClient,
        spec: LeagueSpec,
        scoreboard: Any,
        strict: bool | None = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[str]]:
        if not spec.include_summaries or not scoreboard or not scoreboard.events:
            return {}, {}, []

        semaphore = asyncio.Semaphore(self.settings.espn_concurrency)

        async def fetch(event_id: str) -> tuple[str, Fetched | Exception]:
            try:
                async with semaphore:
                    payload, url = await client.get_json(
                        f"{spec.api_path}/summary", params={"event": event_id}
                    )
                    _validate_resource_payload("summaries", payload)
                return event_id, Fetched(payload=payload, url=url)
            except Exception as exc:
                return event_id, exc

        results = await asyncio.gather(*(fetch(event["source_id"]) for event in scoreboard.events))
        summaries: dict[str, dict[str, Any]] = {}
        urls: dict[str, str] = {}
        warnings: list[str] = []
        for event_id, result in results:
            if isinstance(result, Fetched):
                summaries[event_id] = result.payload
                urls[f"summary:{event_id}"] = result.url
            else:
                warnings.append(f"summary {event_id}: {result}")
        if warnings and self._strict(strict):
            raise ResourceSyncError("summaries", "; ".join(warnings))
        return summaries, urls, warnings

    async def _fetch_team_details(
        self,
        client: ESPNClient,
        spec: LeagueSpec,
        teams: dict[str, dict[str, Any]],
        include_details: bool,
        strict: bool | None = None,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str], list[str]]:
        if not include_details or not spec.supports("teams") or not teams:
            return {}, {}, []
        items = list(teams.values())
        semaphore = asyncio.Semaphore(self.settings.espn_concurrency)

        async def fetch(team: dict[str, Any]) -> tuple[str, Fetched | Exception]:
            reference = team.get("source_id") or team.get("slug") or team.get("abbreviation")
            if not reference:
                return team["source_id"], ValueError("Team has no slug, abbreviation, or ID")
            path = f"{spec.api_path}/teams/{quote(str(reference), safe='')}"
            async with semaphore:
                try:
                    payload, url = await client.get_json(path)
                    _validate_resource_payload("team-details", payload)
                    return team["source_id"], Fetched(payload=payload, url=url)
                except Exception as exc:
                    return team["source_id"], exc

        results = await asyncio.gather(*(fetch(team) for team in items))
        details: dict[str, dict[str, Any]] = {}
        urls: dict[str, str] = {}
        warnings: list[str] = []
        for source_id, result in results:
            if isinstance(result, Fetched):
                details[source_id] = result.payload
                urls[f"team:{source_id}"] = result.url
            else:
                warnings.append(f"team {source_id}: {result}")
        if warnings and self._strict(strict):
            raise ResourceSyncError("team-details", "; ".join(warnings))
        return details, urls, warnings

    async def _replace_snapshot(
        self, session: AsyncSession, league_id: int, snapshot: LeagueSnapshot
    ) -> None:
        async with session.begin():
            league = await session.scalar(
                select(League).where(League.id == league_id).with_for_update()
            )
            if league is None:
                raise LeagueSyncError("League disappeared during synchronization")

            for key, value in snapshot.league_update.items():
                if key != "slug" and value is not None:
                    setattr(league, key, value)
            league.synced_at = utcnow()
            await session.flush()

            existing_events = list(
                await session.scalars(select(Event).where(Event.league_id == league_id))
            )
            existing_events_by_source = {event.source_id: event for event in existing_events}
            incoming_event_sources = {event["source_id"] for event in snapshot.events}
            stale_event_ids = [
                event.id
                for source_id, event in existing_events_by_source.items()
                if source_id not in incoming_event_sources and event.id is not None
            ]
            if stale_event_ids:
                await session.execute(
                    delete(EventCompetitor).where(EventCompetitor.event_id.in_(stale_event_ids))
                )
            for source_id, event in existing_events_by_source.items():
                if source_id not in incoming_event_sources:
                    await session.delete(event)

            existing_news = list(
                await session.scalars(select(NewsArticle).where(NewsArticle.league_id == league_id))
            )
            existing_news_by_source = {article.source_id: article for article in existing_news}
            incoming_news_sources = {article["source_id"] for article in snapshot.news}
            for source_id, article in existing_news_by_source.items():
                if source_id not in incoming_news_sources:
                    await session.delete(article)

            existing_rankings = list(
                await session.scalars(select(Ranking).where(Ranking.league_id == league_id))
            )
            existing_rankings_by_source = {
                ranking.source_id: ranking for ranking in existing_rankings
            }
            incoming_ranking_sources = {ranking["source_id"] for ranking in snapshot.rankings}
            stale_ranking_ids = [
                ranking.id
                for source_id, ranking in existing_rankings_by_source.items()
                if source_id not in incoming_ranking_sources and ranking.id is not None
            ]
            if stale_ranking_ids:
                await session.execute(
                    delete(RankingEntry).where(RankingEntry.ranking_id.in_(stale_ranking_ids))
                )
            for source_id, ranking in existing_rankings_by_source.items():
                if source_id not in incoming_ranking_sources:
                    await session.delete(ranking)
            await session.flush()

            retained_event_ids = [
                event.id
                for source_id, event in existing_events_by_source.items()
                if source_id in incoming_event_sources and event.id is not None
            ]
            if retained_event_ids:
                await session.execute(
                    delete(EventCompetitor).where(EventCompetitor.event_id.in_(retained_event_ids))
                )
            retained_ranking_ids = [
                ranking.id
                for source_id, ranking in existing_rankings_by_source.items()
                if source_id in incoming_ranking_sources and ranking.id is not None
            ]
            if retained_ranking_ids:
                await session.execute(
                    delete(RankingEntry).where(RankingEntry.ranking_id.in_(retained_ranking_ids))
                )

            existing_teams = list(
                await session.scalars(select(Team).where(Team.league_id == league_id))
            )
            existing_by_source = {team.source_id: team for team in existing_teams}
            incoming_sources = {team["source_id"] for team in snapshot.teams}
            for source_id, team in existing_by_source.items():
                if source_id not in incoming_sources:
                    await session.delete(team)
            await session.flush()

            team_objects: dict[str, Team] = {}
            for values in snapshot.teams:
                source_id = values["source_id"]
                existing_team = existing_by_source.get(source_id)
                if existing_team is None:
                    team = Team(**values)
                    session.add(team)
                else:
                    team = existing_team
                    for key, value in values.items():
                        setattr(team, key, value)
                    team.synced_at = utcnow()
                team_objects[source_id] = team
            await session.flush()
            team_ids = {
                source_id: int(team.id)
                for source_id, team in team_objects.items()
                if team.id is not None
            }

            event_ids: dict[str, int] = {}
            for values in snapshot.events:
                event_source_id = values["source_id"]
                existing_event = existing_events_by_source.get(event_source_id)
                event_obj: Event
                if existing_event is None:
                    event_obj = Event(**values)
                    session.add(event_obj)
                else:
                    event_obj = existing_event
                    for key, value in values.items():
                        setattr(event_obj, key, value)
                    event_obj.synced_at = utcnow()
                await session.flush()
                event_ids[event_source_id] = int(event_obj.id)

            for values in snapshot.competitors:
                competitor_values = dict(values)
                event_source_id = competitor_values.pop("event_source_id")
                team_source_id = competitor_values.pop("team_source_id")
                competitor_values["event_id"] = event_ids[event_source_id]
                competitor_values["team_id"] = team_ids.get(team_source_id)
                session.add(EventCompetitor(**competitor_values))

            for values in snapshot.news:
                article_source_id = values["source_id"]
                existing_article = existing_news_by_source.get(article_source_id)
                if existing_article is None:
                    session.add(NewsArticle(**values))
                else:
                    article_obj = existing_article
                    for key, value in values.items():
                        setattr(article_obj, key, value)
                    article_obj.synced_at = utcnow()

            for values in snapshot.rankings:
                ranking_values = dict(values)
                entries = ranking_values.pop("entries")
                ranking_source_id = ranking_values["source_id"]
                existing_ranking = existing_rankings_by_source.get(ranking_source_id)
                ranking_obj: Ranking
                if existing_ranking is None:
                    ranking_obj = Ranking(**ranking_values)
                    session.add(ranking_obj)
                else:
                    ranking_obj = existing_ranking
                    for key, value in ranking_values.items():
                        setattr(ranking_obj, key, value)
                    ranking_obj.synced_at = utcnow()
                await session.flush()
                for entry_values in entries:
                    entry = dict(entry_values)
                    team_source_id = entry.pop("team_source_id")
                    entry["ranking_id"] = ranking_obj.id
                    entry["team_id"] = team_ids.get(team_source_id)
                    session.add(RankingEntry(**entry))

            await self._mark_success(session, league_id, snapshot)

    async def _ensure_league(self, session: AsyncSession, spec: LeagueSpec) -> int:
        async with session.begin():
            sport = await session.scalar(select(Sport).where(Sport.slug == spec.sport_slug))
            if sport is None:
                sport = Sport(slug=spec.sport_slug, name=spec.sport_name)
                session.add(sport)
                await session.flush()
            league = await session.scalar(select(League).where(League.slug == spec.slug))
            if league is None:
                league = League(
                    sport_id=sport.id,
                    slug=spec.slug,
                    name=spec.name,
                    abbreviation=spec.abbreviation,
                    source_id=spec.source_id,
                    raw_payload=None,
                )
                session.add(league)
                await session.flush()
            return int(league.id)

    async def _league_id(self, session: AsyncSession, slug: str) -> int:
        value = await session.scalar(select(League.id).where(League.slug == slug))
        if value is None:
            raise LeagueSyncError(f"League {slug} was not registered")
        return value

    async def _mark_attempt(
        self, session: AsyncSession, league_id: int, spec: LeagueSpec, options: SyncOptions
    ) -> None:
        async with session.begin():
            now = utcnow()
            resources = self._resources(spec, options)
            for resource in resources:
                state = await self._state(session, league_id, resource)
                state.status = "running"
                state.last_attempt_at = now
                state.error_message = None
            if spec.supports("teams") and "team-details" not in resources:
                state = await self._state(session, league_id, "team-details")
                state.status = "skipped"
                state.source_url = None
                state.item_count = 0
                state.last_attempt_at = now
                state.last_successful_sync = None
                state.error_message = None

    async def _mark_success(
        self, session: AsyncSession, league_id: int, snapshot: LeagueSnapshot
    ) -> None:
        now = utcnow()
        counts = {
            "teams": len(snapshot.teams),
            "team-details": sum(1 for key in snapshot.source_urls if key.startswith("team:")),
            "scoreboard": len(snapshot.events),
            "summaries": sum(1 for key in snapshot.source_urls if key.startswith("summary:")),
            "news": len(snapshot.news),
            "rankings": len(snapshot.rankings),
            "ranking_entries": sum(len(ranking["entries"]) for ranking in snapshot.rankings),
        }
        resources = set(snapshot.resources)
        if any(key.startswith("team:") for key in snapshot.source_urls):
            resources.add("team-details")
        if any(key.startswith("summary:") for key in snapshot.source_urls):
            resources.add("summaries")
        for resource in resources:
            state = await self._state(session, league_id, resource)
            resource_warnings = snapshot.warnings_by_resource.get(resource, [])
            state.status = "partial" if resource_warnings else "success"
            source_url = snapshot.source_urls.get(resource)
            if source_url is None and resource == "team-details":
                source_url = next(
                    (
                        value
                        for key, value in snapshot.source_urls.items()
                        if key.startswith("team:")
                    ),
                    None,
                )
            if source_url is None and resource == "summaries":
                source_url = next(
                    (
                        value
                        for key, value in snapshot.source_urls.items()
                        if key.startswith("summary:")
                    ),
                    None,
                )
            state.source_url = source_url
            state.item_count = counts.get(resource, 0)
            state.last_attempt_at = now
            state.last_successful_sync = now
            state.error_message = "; ".join(resource_warnings)[:2000] or None

    async def _record_failure(
        self,
        session: AsyncSession,
        league_id: int,
        spec: LeagueSpec,
        options: SyncOptions,
        error: str,
        failed_resource: str | None = None,
    ) -> None:
        async with session.begin():
            for resource in self._resources(spec, options):
                state = await self._state(session, league_id, resource)
                state.last_attempt_at = utcnow()
                if failed_resource is None or resource == failed_resource:
                    state.status = "failed"
                    state.error_message = error[:2000]
                else:
                    state.status = "aborted"
                    state.error_message = (f"Sync aborted after {failed_resource} failed: {error}")[
                        :2000
                    ]

    async def _state(self, session: AsyncSession, league_id: int, resource: str) -> SyncState:
        state = await session.scalar(
            select(SyncState).where(
                SyncState.league_id == league_id, SyncState.resource == resource
            )
        )
        if state is None:
            state = SyncState(league_id=league_id, resource=resource)
            session.add(state)
            await session.flush()
        return state

    def _resources(self, spec: LeagueSpec, options: SyncOptions) -> list[str]:
        resources = [
            resource
            for resource in ("teams", "scoreboard", "news", "rankings")
            if spec.supports(resource)
        ]
        if spec.supports("teams") and (
            self.settings.espn_include_team_details
            if options.include_team_details is None
            else options.include_team_details
        ):
            resources.append("team-details")
        if spec.include_summaries:
            resources.append("summaries")
        return resources

    def _strict(self, override: bool | None = None) -> bool:
        return self.settings.espn_strict_sync if override is None else override

    @asynccontextmanager
    async def _league_lock(self, name: str) -> AsyncIterator[bool]:
        if self.engine is None or self.engine.dialect.name != "mysql":
            yield True
            return
        async with self.engine.connect() as connection:
            acquired = await connection.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": name})
            if not acquired:
                yield False
                return
            try:
                yield True
            finally:
                await connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})


async def run_sync(
    settings: Settings | None = None,
    *,
    selectors: list[str] | None = None,
    options: SyncOptions | None = None,
    fail_fast: bool = False,
) -> list[SyncResult]:
    settings = settings or get_settings()
    catalog = league_catalog(settings)
    requested = set(selectors or [])
    if requested:
        catalog = [spec for spec in catalog if spec.selector in requested or spec.slug in requested]
        missing = requested - {spec.selector for spec in catalog} - {spec.slug for spec in catalog}
        if missing:
            raise ValueError(f"Unknown league selector(s): {', '.join(sorted(missing))}")

    engine = build_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    ingestor = SportsIngestor(settings, session_factory, engine)
    results: list[SyncResult] = []
    try:
        for spec in catalog:
            result = await ingestor.sync_league(spec, options)
            results.append(result)
            if fail_fast and not result.success:
                break
    finally:
        await engine.dispose()
    return results


def _validate_resource_payload(resource: str, payload: dict[str, Any]) -> None:
    contracts: dict[str, dict[str, type | tuple[type, ...]]] = {
        "teams": {"sports": list},
        "scoreboard": {"events": list, "leagues": list},
        "news": {"articles": list},
        "rankings": {"rankings": list},
        "team-details": {"team": dict},
        "summaries": {"header": dict},
    }
    for field_name, expected_type in contracts.get(resource, {}).items():
        if not isinstance(payload.get(field_name), expected_type):
            expected_name = (
                expected_type.__name__
                if isinstance(expected_type, type)
                else "/".join(item.__name__ for item in expected_type)
            )
            raise ResourceSyncError(
                resource,
                f"{resource} response missing {field_name} with type {expected_name}",
            )
    if resource == "team-details" and not payload["team"].get("id"):
        raise ResourceSyncError("team-details", "team-details response has no team ID")


def _prefer_metadata(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    if primary.get("raw_payload") is None:
        return dict(fallback)
    merged = dict(fallback)
    merged.update({key: value for key, value in primary.items() if value is not None})
    return merged


def _merge_team(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    if existing is None:
        return incoming
    merged = dict(existing)
    for key, value in incoming.items():
        if value is not None:
            merged[key] = value
    return merged


def _ranking_team(entry: dict[str, Any], league_id: int) -> dict[str, Any] | None:
    team = entry.get("team")
    if not isinstance(team, dict):
        return None
    return parse_team(team, league_id, team)


def normalize_dates(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) == 8 and value.isdigit():
        normalized = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    elif len(value) == 10:
        normalized = value
    else:
        raise ValueError("dates must be YYYYMMDD or YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("dates must be YYYYMMDD or YYYY-MM-DD") from exc
    return parsed.strftime("%Y%m%d")
