import asyncio
from typing import Annotated

import typer

from app.core.config import get_settings
from app.services.catalog import league_catalog
from app.services.ingestion import SyncOptions, normalize_dates, run_sync

app = typer.Typer(help="Synchronize the current ESPN snapshot into MySQL.", no_args_is_help=True)


@app.command("sync")
def sync_command(
    league: Annotated[
        list[str] | None,
        typer.Option(
            "--league",
            "-l",
            help="League selector, for example nfl, football.nfl, or eng.1. Repeatable.",
        ),
    ] = None,
    dates: Annotated[
        str | None,
        typer.Option("--dates", help="Scoreboard date in YYYYMMDD or YYYY-MM-DD format."),
    ] = None,
    calendar: Annotated[
        str | None,
        typer.Option("--calendar", help="Optional ESPN scoreboard calendar value."),
    ] = None,
    team_details: Annotated[
        bool,
        typer.Option(
            "--team-details",
            help="Force fetching each parameterized team endpoint from the Gist.",
        ),
    ] = False,
    no_team_details: Annotated[
        bool,
        typer.Option(
            "--no-team-details",
            help="Skip each parameterized team endpoint from the Gist.",
        ),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Abort a league snapshot if an individual detail request fails.",
        ),
    ] = False,
    no_strict: Annotated[
        bool,
        typer.Option(
            "--no-strict",
            help="Allow individual detail failures and retain a partial snapshot.",
        ),
    ] = False,
    fail_fast: Annotated[
        bool,
        typer.Option("--fail-fast", help="Stop after the first league failure."),
    ] = False,
    allow_partial: Annotated[
        bool,
        typer.Option(
            "--allow-partial",
            help="Return exit code 0 when a league commits with detail warnings.",
        ),
    ] = False,
) -> None:
    """Fetch and replace current data for all configured leagues."""
    settings = get_settings()
    try:
        normalized_dates = normalize_dates(dates)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if team_details and no_team_details:
        raise typer.BadParameter("--team-details and --no-team-details cannot be used together")
    if strict and no_strict:
        raise typer.BadParameter("--strict and --no-strict cannot be used together")
    include_team_details: bool | None = None
    if team_details:
        include_team_details = True
    elif no_team_details:
        include_team_details = False
    strict_override: bool | None = None
    if strict:
        strict_override = True
    elif no_strict:
        strict_override = False

    options = SyncOptions(
        dates=normalized_dates,
        calendar=calendar,
        include_team_details=include_team_details,
        strict=strict_override,
    )
    results = asyncio.run(
        run_sync(
            settings,
            selectors=league,
            options=options,
            fail_fast=fail_fast,
        )
    )
    failures = 0
    partials = 0
    for result in results:
        marker = "FAIL" if not result.success else "WARN" if result.warnings else "OK"
        detail = ", ".join(f"{key}={value}" for key, value in result.counts.items())
        typer.echo(f"[{marker}] {result.selector} {detail}".rstrip())
        for warning in result.warnings[:10]:
            typer.echo(f"  warning: {warning}")
        if result.error:
            typer.echo(f"  error: {result.error}", err=True)
        failures += int(not result.success)
        partials += int(result.success and bool(result.warnings))
    if failures:
        raise typer.Exit(code=1)
    if partials and not allow_partial:
        raise typer.Exit(code=2)


@app.command("leagues")
def leagues_command() -> None:
    """List the leagues covered by the default Gist catalog."""
    for spec in league_catalog(get_settings()):
        resources = ", ".join(sorted(spec.resources))
        typer.echo(f"{spec.selector:38} {resources}")


if __name__ == "__main__":
    app()
