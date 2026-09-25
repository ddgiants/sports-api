from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class LeagueSpec:
    sport_slug: str
    sport_name: str
    slug: str
    name: str
    abbreviation: str
    source_id: str | None = None
    resources: frozenset[str] = frozenset({"news", "scoreboard", "teams"})
    include_summaries: bool = False

    @property
    def api_path(self) -> str:
        return f"{self.sport_slug}/{self.slug}"

    @property
    def selector(self) -> str:
        return f"{self.sport_slug}.{self.slug}"

    def supports(self, resource: str) -> bool:
        return resource in self.resources


_NON_SOCCER: tuple[LeagueSpec, ...] = (
    LeagueSpec(
        sport_slug="football",
        sport_name="Football",
        slug="college-football",
        name="NCAA Football",
        abbreviation="FB",
        resources=frozenset({"news", "scoreboard", "teams", "rankings"}),
        include_summaries=True,
    ),
    LeagueSpec("football", "Football", "nfl", "NFL", "NFL", "28"),
    LeagueSpec("baseball", "Baseball", "mlb", "MLB", "MLB", "10"),
    LeagueSpec(
        "baseball",
        "Baseball",
        "college-baseball",
        "NCAA Baseball",
        "BASE",
        resources=frozenset({"scoreboard"}),
    ),
    LeagueSpec("hockey", "Hockey", "nhl", "NHL", "NHL", "1"),
    LeagueSpec("basketball", "Basketball", "nba", "NBA", "NBA", "46"),
    LeagueSpec("basketball", "Basketball", "wnba", "WNBA", "WNBA", "41"),
    LeagueSpec(
        "basketball",
        "Basketball",
        "mens-college-basketball",
        "NCAA Men's Basketball",
        "MBB",
    ),
    LeagueSpec(
        "basketball",
        "Basketball",
        "womens-college-basketball",
        "NCAA Women's Basketball",
        "WBB",
    ),
)


def league_catalog(settings: Settings) -> list[LeagueSpec]:
    """Return every Gist endpoint league, including configured soccer slugs."""
    leagues = list(_NON_SOCCER)
    leagues.extend(
        LeagueSpec(
            sport_slug="soccer",
            sport_name="Soccer",
            slug=slug,
            name=_soccer_name(slug),
            abbreviation=slug.upper(),
        )
        for slug in settings.soccer_league_slugs
    )
    return leagues


def _soccer_name(slug: str) -> str:
    names = {
        "eng.1": "English Premier League",
        "usa.1": "Major League Soccer",
        "esp.1": "LaLiga",
        "ger.1": "Bundesliga",
        "ita.1": "Serie A",
        "fra.1": "Ligue 1",
        "por.1": "Primeira Liga",
        "ned.1": "Eredivisie",
        "uefa.champions": "UEFA Champions League",
        "uefa.europa": "UEFA Europa League",
        "uefa.europa.conf": "UEFA Conference League",
        "mex.1": "Liga MX",
        "bra.1": "Campeonato Brasileiro Série A",
        "arg.1": "Liga Profesional de Fútbol",
        "col.1": "Categoría Primera A",
        "fifa.world": "FIFA World Cup",
    }
    return names.get(slug, slug)
