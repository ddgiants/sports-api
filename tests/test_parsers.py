from __future__ import annotations

from app.services.catalog import LeagueSpec
from app.services.parsers import (
    parse_news,
    parse_rankings,
    parse_scoreboard,
    parse_team_detail,
    parse_team_list,
)
from tests.fixtures import NEWS, RANKINGS, SCOREBOARD, TEAM_LIST


def test_scoreboard_parser_preserves_current_espn_shape() -> None:
    spec = LeagueSpec("football", "Football", "nfl", "NFL", "NFL", "28")
    parsed = parse_scoreboard(SCOREBOARD, 7, spec)

    assert len(parsed.events) == 1
    assert parsed.events[0]["source_id"] == "401872948"
    assert parsed.events[0]["week"] == 3
    assert parsed.events[0]["season_type"] == "2"
    assert parsed.events[0]["venue_name"] == "Lambeau Field"
    assert len(parsed.competitors) == 2
    assert parsed.competitors[0]["score"] == "0"
    assert parsed.competitors[0]["winner"] is None
    assert parsed.teams[0]["logo_url"] == "https://example.test/gb.png"


def test_team_list_and_news_parser_use_current_fields() -> None:
    spec = LeagueSpec("football", "Football", "nfl", "NFL", "NFL", "28")
    metadata, teams = parse_team_list(TEAM_LIST, 7, spec)
    articles = parse_news(NEWS, 7)

    assert metadata["source_id"] == "28"
    assert metadata["season_type"] == "2"
    assert len(teams) == 1
    assert teams[0]["source_id"] == "9"
    assert articles[0]["link_url"] == "https://example.test/story"
    assert articles[0]["image_url"] == "https://example.test/image.jpg"
    assert articles[0]["uid"] == "1-12345"


def test_rankings_parser_supports_ranks_and_others_shape() -> None:
    rankings = parse_rankings(RANKINGS, 7)

    assert len(rankings) == 1
    assert rankings[0]["season_year"] == 2026
    assert rankings[0]["week"] == 4
    assert rankings[0]["entries"][0]["rank"] == 1
    assert rankings[0]["entries"][0]["previous_rank"] == 2
    assert rankings[0]["entries"][0]["rank_delta"] == 1
    assert float(rankings[0]["entries"][0]["points"]) == 1706
    assert rankings[0]["entries"][1]["rank"] is None
    assert rankings[0]["entries"][1]["previous_rank"] is None


def test_team_detail_parser_reads_record_rank_stat() -> None:
    spec = LeagueSpec("football", "Football", "nfl", "NFL", "NFL", "28")
    _, existing = parse_team_list(TEAM_LIST, 7, spec)
    detail = {
        "team": {
            **existing[0]["raw_payload"]["team"],
            "record": {
                "items": [
                    {
                        "summary": "1-1",
                        "stats": [{"name": "rank", "value": 3}],
                    }
                ]
            },
        }
    }
    parsed = parse_team_detail(detail, 7, existing[0])
    assert parsed is not None
    assert parsed["record"] == "1-1"
    assert parsed["rank"] == "3"
