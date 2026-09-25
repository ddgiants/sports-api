from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.catalog import LeagueSpec


@dataclass
class ParsedScoreboard:
    league_update: dict[str, Any]
    teams: list[dict[str, Any]]
    events: list[dict[str, Any]]
    competitors: list[dict[str, Any]]


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def parse_league_payload(payload: dict[str, Any], spec: LeagueSpec) -> dict[str, Any]:
    candidate = _first_league(payload) or {}
    logos = _as_list(candidate.get("logos"))
    logo = _first_string(logos, "href") or _first_string(logos, "url")
    season = _as_dict(candidate.get("season"))
    if not season and candidate.get("year") is not None:
        season = {"year": candidate.get("year")}
    source_id = _string_or_none(candidate.get("id")) or spec.source_id
    return {
        "source_id": source_id,
        "uid": _string_or_none(candidate.get("uid")),
        "slug": _string_or_none(candidate.get("slug")) or spec.slug,
        "name": _string_or_none(candidate.get("name")) or spec.name,
        "abbreviation": _string_or_none(candidate.get("abbreviation")) or spec.abbreviation,
        "logo_url": logo,
        "season_year": _as_int(season.get("year")),
        "season_type": _season_type(season.get("type")),
        "raw_payload": candidate or None,
    }


def parse_team_list(
    payload: dict[str, Any], league_id: int, spec: LeagueSpec
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    wrappers: list[dict[str, Any]] = []
    for sport_payload in _as_list(payload.get("sports")):
        for league_payload in _as_list(sport_payload.get("leagues")):
            wrappers.extend(
                wrapper
                for wrapper in _as_list(league_payload.get("teams"))
                if isinstance(wrapper, dict)
            )

    teams = []
    for wrapper in wrappers:
        team = _as_dict(wrapper.get("team"))
        parsed = parse_team(team, league_id, wrapper)
        if parsed:
            teams.append(parsed)
    return parse_league_payload(payload, spec), teams


def parse_team_detail(
    payload: dict[str, Any], league_id: int, existing: dict[str, Any]
) -> dict[str, Any] | None:
    team = _as_dict(payload.get("team"))
    parsed = parse_team(team, league_id, team)
    if not parsed:
        return existing
    parsed["detail_payload"] = payload
    record = _as_dict(team.get("record"))
    record_items = _as_list(record.get("items"))
    parsed["record"] = (
        _first_string([record], "summary")
        or _first_string(record_items, "summary")
        or existing.get("record")
    )
    parsed["rank"] = _record_stat(record_items, "rank") or parsed.get("rank")
    parsed["raw_payload"] = team or existing.get("raw_payload")
    for key, value in existing.items():
        if parsed.get(key) is None:
            parsed[key] = value
    return parsed


def parse_team(
    team: dict[str, Any], league_id: int, raw_payload: dict[str, Any]
) -> dict[str, Any] | None:
    source_id = _string_or_none(team.get("id"))
    name = _string_or_none(team.get("name")) or _string_or_none(team.get("displayName"))
    if not source_id or not name:
        return None

    logos = _as_list(team.get("logos"))
    logo = team.get("logo")
    if isinstance(logo, dict):
        logos.append(logo)
    elif isinstance(logo, list):
        logos.extend(item for item in logo if isinstance(item, dict))
    logo_url = _first_string(logos, "href") or _first_string(logos, "url")
    if logo_url is None and isinstance(logo, str):
        logo_url = logo
    return {
        "league_id": league_id,
        "source_id": source_id,
        "uid": _string_or_none(team.get("uid")),
        "slug": _string_or_none(team.get("slug")),
        "location": _string_or_none(team.get("location")),
        "name": name,
        "abbreviation": _string_or_none(team.get("abbreviation")),
        "display_name": _string_or_none(team.get("displayName")),
        "short_display_name": _string_or_none(team.get("shortDisplayName")),
        "color": _string_or_none(team.get("color")),
        "alternate_color": _string_or_none(team.get("alternateColor")),
        "logo_url": logo_url,
        "rank": _first_string([team], "rank"),
        "record": None,
        "raw_payload": raw_payload,
        "detail_payload": None,
    }


def parse_news(payload: dict[str, Any], league_id: int) -> list[dict[str, Any]]:
    articles = []
    for raw_article in _as_list(payload.get("articles")):
        article = _as_dict(raw_article)
        headline = _string_or_none(article.get("headline"))
        if not headline:
            continue
        source_id = _stable_source_id(article.get("id"), article.get("nowId"), headline)
        links = _as_dict(article.get("links"))
        web_link = _as_dict(links.get("web"))
        image = _first_dict(article.get("images")) or _as_dict(article.get("image"))
        link_url = _string_or_none(article.get("link")) or _string_or_none(web_link.get("href"))
        articles.append(
            {
                "league_id": league_id,
                "source_id": source_id,
                "uid": (
                    _string_or_none(article.get("uid"))
                    or _string_or_none(article.get("nowId"))
                    or _string_or_none(article.get("dataSourceIdentifier"))
                ),
                "headline": headline,
                "description": _string_or_none(article.get("description")),
                "published_at": parse_datetime(article.get("published")),
                "last_modified_at": parse_datetime(article.get("lastModified")),
                "article_type": _string_or_none(article.get("type")),
                "byline": _string_or_none(article.get("byline")),
                "link_url": link_url,
                "image_url": _string_or_none(image.get("url"))
                or _string_or_none(image.get("href")),
                "categories": [
                    category
                    for category in _as_list(article.get("categories"))
                    if isinstance(category, dict)
                ]
                or None,
                "raw_payload": article,
            }
        )
    return articles


def parse_scoreboard(
    payload: dict[str, Any],
    league_id: int,
    spec: LeagueSpec,
    summaries: dict[str, dict[str, Any]] | None = None,
) -> ParsedScoreboard:
    teams: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    competitors: list[dict[str, Any]] = []

    for raw_event in _as_list(payload.get("events")):
        event = _as_dict(raw_event)
        event_source_id = _string_or_none(event.get("id"))
        if not event_source_id:
            continue
        competitions = [
            competition
            for competition in _as_list(event.get("competitions"))
            if isinstance(competition, dict)
        ]
        primary = competitions[0] if competitions else {}
        status = _as_dict(event.get("status")) or _as_dict(primary.get("status"))
        status_type = _as_dict(status.get("type"))
        venue = _as_dict(primary.get("venue"))
        season = _as_dict(event.get("season")) or _as_dict(payload.get("season"))
        week_value = event.get("week")
        if isinstance(week_value, dict):
            week_value = week_value.get("number")
        venue_address = _as_dict(venue.get("address"))
        events.append(
            {
                "league_id": league_id,
                "source_id": event_source_id,
                "uid": _string_or_none(event.get("uid")),
                "start_at": parse_datetime(primary.get("date") or event.get("date")),
                "name": _string_or_none(event.get("name")) or event_source_id,
                "short_name": _string_or_none(event.get("shortName")),
                "season_year": _as_int(season.get("year")),
                "season_type": _season_type(season.get("type")),
                "season_name": _string_or_none(season.get("name")),
                "week": _as_int(week_value),
                "status_id": _string_or_none(status_type.get("id")),
                "status_name": _string_or_none(status_type.get("name")),
                "status_state": _string_or_none(status_type.get("state")),
                "status_detail": _string_or_none(status_type.get("detail")),
                "status_short_detail": _string_or_none(status_type.get("shortDetail")),
                "completed": bool(status_type.get("completed", False)),
                "clock": _as_int(status.get("clock")),
                "period": _as_int(status.get("period")),
                "neutral_site": _optional_bool(primary.get("neutralSite")),
                "conference_competition": _optional_bool(primary.get("conferenceCompetition")),
                "venue_id": _string_or_none(venue.get("id")),
                "venue_name": _first_string([venue], "fullName") or _first_string([venue], "name"),
                "venue_address": venue_address or None,
                "raw_payload": event,
                "summary_payload": (summaries or {}).get(event_source_id),
            }
        )

        for competition in competitions:
            competition_id = _string_or_none(competition.get("id")) or "default"
            for raw_competitor in _as_list(competition.get("competitors")):
                competitor = _as_dict(raw_competitor)
                team = _as_dict(competitor.get("team"))
                team_source_id = _string_or_none(team.get("id")) or _string_or_none(
                    competitor.get("id")
                )
                if not team_source_id:
                    continue
                team_record = parse_team(team, league_id, team)
                if team_record:
                    teams.setdefault(team_source_id, team_record)
                competitors.append(
                    {
                        "event_source_id": event_source_id,
                        "competition_id": competition_id,
                        "team_source_id": team_source_id,
                        "source_id": _string_or_none(competitor.get("id")) or team_source_id,
                        "uid": _string_or_none(competitor.get("uid")),
                        "competitor_type": _string_or_none(competitor.get("type")),
                        "sort_order": _as_int(competitor.get("order")),
                        "home_away": _string_or_none(competitor.get("homeAway")),
                        "winner": _optional_bool(competitor.get("winner")),
                        "score": _string_value(competitor.get("score")),
                        "linescores": _object_list(competitor.get("linescores")),
                        "records": _object_list(competitor.get("records")),
                        "statistics": _object_list(competitor.get("statistics")),
                        "leaders": _object_list(competitor.get("leaders")),
                    }
                )

    return ParsedScoreboard(
        league_update=parse_league_payload(payload, spec),
        teams=list(teams.values()),
        events=events,
        competitors=competitors,
    )


def parse_rankings(payload: dict[str, Any], league_id: int) -> list[dict[str, Any]]:
    rankings = []
    payload_season = _as_dict(payload.get("latestSeason"))
    for raw_ranking in _as_list(payload.get("rankings")):
        ranking = _as_dict(raw_ranking)
        name = _string_or_none(ranking.get("name"))
        if not name:
            continue
        ranking_source_id = _stable_source_id(
            ranking.get("id"),
            f"{ranking.get('season')}:{ranking.get('week')}:{name}",
            name,
        )
        season = _as_dict(ranking.get("season")) or payload_season
        week_value = ranking.get("week")
        if isinstance(week_value, dict):
            week_value = week_value.get("number")
        if week_value is None:
            week_value = _as_dict(ranking.get("occurrence")).get("number")
        if week_value is None:
            week_value = _as_dict(payload.get("latestWeek")).get("number")

        raw_entries: list[dict[str, Any]] = []
        raw_entries.extend(
            item for item in _as_list(ranking.get("ranks")) if isinstance(item, dict)
        )
        raw_entries.extend(
            item for item in _as_list(ranking.get("others")) if isinstance(item, dict)
        )
        for raw_group in _as_list(ranking.get("groups")):
            group = _as_dict(raw_group)
            raw_entries.extend(
                item for item in _as_list(group.get("teams")) if isinstance(item, dict)
            )

        entries: dict[str, dict[str, Any]] = {}
        for entry in raw_entries:
            team = _as_dict(entry.get("team"))
            team_source_id = _string_or_none(team.get("id"))
            if not team_source_id:
                continue
            record = _as_dict(entry.get("record"))
            trend = _as_int(entry.get("delta"))
            if trend is None:
                trend = _trend_value(entry.get("trend"))
            rank = _as_int(entry.get("currentRank") or entry.get("current"))
            previous_rank = _as_int(entry.get("previousRank") or entry.get("previous"))
            first_rank = _as_int(entry.get("firstRank") or entry.get("first"))
            entries[team_source_id] = {
                "source_id": team_source_id,
                "team_source_id": team_source_id,
                "rank": rank if rank is not None and rank > 0 else None,
                "previous_rank": (
                    previous_rank if previous_rank is not None and previous_rank > 0 else None
                ),
                "first_rank": first_rank if first_rank is not None and first_rank > 0 else None,
                "rank_delta": trend,
                "points": _as_decimal(entry.get("points")),
                "record": _first_string([record], "summary")
                or _first_string(_as_list(record.get("items")), "summary")
                or _string_or_none(entry.get("recordSummary")),
                "note": _string_or_none(entry.get("note")),
                "raw_payload": entry,
            }

        rankings.append(
            {
                "league_id": league_id,
                "source_id": ranking_source_id,
                "uid": _string_or_none(ranking.get("uid")),
                "name": name,
                "short_name": _string_or_none(ranking.get("shortName")),
                "full_name": _string_or_none(ranking.get("fullName"))
                or _string_or_none(ranking.get("headline")),
                "season_year": _as_int(season.get("year") or ranking.get("season")),
                "week": _as_int(week_value),
                "raw_payload": ranking,
                "entries": list(entries.values()),
            }
        )
    return rankings


def _first_league(payload: dict[str, Any]) -> dict[str, Any] | None:
    direct = next(
        (item for item in _as_list(payload.get("leagues")) if isinstance(item, dict)),
        None,
    )
    if direct:
        return direct
    for sport in _as_list(payload.get("sports")):
        for league in _as_list(_as_dict(sport).get("leagues")):
            if isinstance(league, dict):
                return league
    return None


def _first_string(objects: list[Any], key: str) -> str | None:
    for obj in objects:
        if isinstance(obj, dict) and obj.get(key) not in (None, ""):
            return str(obj[key])
    return None


def _record_stat(items: list[Any], name: str) -> str | None:
    for item in items:
        item_dict = _as_dict(item)
        for stat in _as_list(item_dict.get("stats")):
            stat_dict = _as_dict(stat)
            stat_name = _string_or_none(stat_dict.get("name"))
            if stat_name and stat_name.lower() == name.lower():
                return _string_value(stat_dict.get("value")) or _string_or_none(
                    stat_dict.get("displayValue")
                )
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_dict(value: Any) -> dict[str, Any]:
    return next((item for item in _as_list(value) if isinstance(item, dict)), {})


def _trend_value(value: Any) -> int | None:
    if value in (None, "", "-"):
        return None
    text = str(value)
    if text in ("UNRANKED", "unranked"):
        return None
    return _as_int(text)


def _object_list(value: Any) -> list[dict[str, Any]] | None:
    items = [item for item in _as_list(value) if isinstance(item, dict)]
    return items or None


def _string_or_none(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return None
    return str(value)


def _season_type(value: Any) -> str | None:
    if isinstance(value, dict):
        return (
            _string_or_none(value.get("id"))
            or _string_or_none(value.get("type"))
            or _string_or_none(value.get("abbreviation"))
            or _string_or_none(value.get("name"))
        )
    return _string_or_none(value)


def _string_value(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("value") or value.get("displayValue")
    return _string_or_none(value)


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return Decimal(str(value)) if value is not None else None
    except (InvalidOperation, ValueError):
        return None


def _stable_source_id(*values: Any) -> str:
    direct = _string_or_none(values[0])
    if direct:
        return direct[:191]
    fallback = "|".join(_string_or_none(value) or "" for value in values[1:])
    return f"generated-{hashlib.sha256(fallback.encode()).hexdigest()[:40]}"
