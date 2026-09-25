from __future__ import annotations

from typing import Any

TEAM_LIST: dict[str, Any] = {
    "sports": [
        {
            "id": "20",
            "name": "Football",
            "leagues": [
                {
                    "id": "28",
                    "uid": "s:20~l:28",
                    "name": "National Football League",
                    "abbreviation": "NFL",
                    "slug": "nfl",
                    "year": 2026,
                    "season": {"year": 2026, "type": {"id": "2"}},
                    "teams": [
                        {
                            "team": {
                                "id": "9",
                                "uid": "s:20~l:28~t:9",
                                "slug": "green-bay-packers",
                                "location": "Green Bay",
                                "name": "Packers",
                                "abbreviation": "GB",
                                "displayName": "Green Bay Packers",
                                "shortDisplayName": "Packers",
                                "color": "204e32",
                                "alternateColor": "ffb612",
                                "logo": "https://example.test/gb.png",
                            }
                        }
                    ],
                }
            ],
        }
    ]
}

SCOREBOARD: dict[str, Any] = {
    "leagues": [
        {
            "id": "28",
            "uid": "s:20~l:28",
            "name": "National Football League",
            "abbreviation": "NFL",
            "slug": "nfl",
            "season": {"year": 2026, "type": {"id": "2"}},
            "logos": [{"href": "https://example.test/nfl.png"}],
        }
    ],
    "season": {"year": 2026, "type": 2},
    "events": [
        {
            "id": "401872948",
            "uid": "s:20~l:28~e:401872948",
            "date": "2026-09-25T00:15Z",
            "name": "Chicago Bears at Green Bay Packers",
            "shortName": "CHI @ GB",
            "season": {"year": 2026, "type": 2},
            "week": {"number": 3},
            "competitions": [
                {
                    "id": "401872948",
                    "date": "2026-09-25T00:15Z",
                    "venue": {
                        "id": "3798",
                        "fullName": "Lambeau Field",
                        "address": {"city": "Green Bay"},
                    },
                    "competitors": [
                        {
                            "id": "9",
                            "uid": "s:20~l:28~t:9",
                            "type": "team",
                            "order": 0,
                            "homeAway": "home",
                            "score": "0",
                            "winner": None,
                            "team": {
                                "id": "9",
                                "name": "Packers",
                                "abbreviation": "GB",
                                "logo": "https://example.test/gb.png",
                            },
                            "statistics": [],
                            "records": [{"summary": "1-1"}],
                        },
                        {
                            "id": "20",
                            "type": "team",
                            "order": 1,
                            "homeAway": "away",
                            "score": "0",
                            "team": {"id": "20", "name": "Bears", "abbreviation": "CHI"},
                        },
                    ],
                }
            ],
            "status": {
                "clock": 0,
                "period": 0,
                "type": {
                    "id": "1",
                    "name": "STATUS_SCHEDULED",
                    "state": "pre",
                    "completed": False,
                    "detail": "Thursday",
                    "shortDetail": "Thu",
                },
            },
        }
    ],
}

NEWS: dict[str, Any] = {
    "articles": [
        {
            "id": 12345,
            "nowId": "1-12345",
            "type": "Story",
            "headline": "A local headline",
            "description": "A description",
            "published": "2026-09-24T12:00:00Z",
            "lastModified": "2026-09-24T12:01:00Z",
            "images": [{"url": "https://example.test/image.jpg"}],
            "links": {"web": {"href": "https://example.test/story"}},
            "categories": [{"type": "league", "description": "NFL"}],
        }
    ]
}

RANKINGS: dict[str, Any] = {
    "latestSeason": {"year": 2026},
    "latestWeek": {"number": 4},
    "rankings": [
        {
            "id": "1",
            "name": "AP Top 25",
            "shortName": "AP Poll",
            "season": {"year": 2026},
            "occurrence": {"number": 4},
            "ranks": [
                {
                    "current": 1,
                    "previous": 2,
                    "points": 1706,
                    "trend": "+1",
                    "team": {
                        "id": "9",
                        "name": "Packers",
                        "abbreviation": "GB",
                    },
                }
            ],
            "others": [
                {
                    "current": 0,
                    "previous": 0,
                    "points": 2,
                    "trend": "+26",
                    "team": {
                        "id": "10",
                        "name": "Bears",
                        "abbreviation": "CHI",
                    },
                }
            ],
        }
    ],
}
