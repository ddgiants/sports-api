"""create the current-snapshot sports schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sports")),
        sa.UniqueConstraint("slug", name=op.f("uq_sports_slug")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_table(
        "leagues",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sport_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(length=191), nullable=True),
        sa.Column("uid", sa.String(length=255), nullable=True),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("abbreviation", sa.String(length=50), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("season_year", sa.SmallInteger(), nullable=True),
        sa.Column("season_type", sa.String(length=50), nullable=True),
        sa.Column("raw_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sport_id"], ["sports.id"], name=op.f("fk_leagues_sport_id_sports"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leagues")),
        sa.UniqueConstraint("slug", name=op.f("uq_leagues_slug")),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_leagues_sport_id", "leagues", ["sport_id"])

    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("league_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(length=191), nullable=False),
        sa.Column("uid", sa.String(length=255), nullable=True),
        sa.Column("slug", sa.String(length=150), nullable=True),
        sa.Column("location", sa.String(length=150), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("abbreviation", sa.String(length=50), nullable=True),
        sa.Column("display_name", sa.String(length=300), nullable=True),
        sa.Column("short_display_name", sa.String(length=300), nullable=True),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("alternate_color", sa.String(length=20), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("rank", sa.String(length=50), nullable=True),
        sa.Column("record", sa.String(length=100), nullable=True),
        sa.Column("raw_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("detail_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_teams_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
        sa.UniqueConstraint("league_id", "source_id", name="uq_teams_league_source"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_teams_league_id", "teams", ["league_id"])
    op.create_index("ix_teams_league_slug", "teams", ["league_id", "slug"])

    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("league_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(length=191), nullable=False),
        sa.Column("uid", sa.String(length=255), nullable=True),
        sa.Column("start_at", sa.DateTime(), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("short_name", sa.String(length=300), nullable=True),
        sa.Column("season_year", sa.SmallInteger(), nullable=True),
        sa.Column("season_type", sa.String(length=50), nullable=True),
        sa.Column("season_name", sa.String(length=100), nullable=True),
        sa.Column("week", sa.SmallInteger(), nullable=True),
        sa.Column("status_id", sa.String(length=100), nullable=True),
        sa.Column("status_name", sa.String(length=150), nullable=True),
        sa.Column("status_state", sa.String(length=50), nullable=True),
        sa.Column("status_detail", sa.String(length=300), nullable=True),
        sa.Column("status_short_detail", sa.String(length=300), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("clock", sa.Integer(), nullable=True),
        sa.Column("period", sa.Integer(), nullable=True),
        sa.Column("neutral_site", sa.Boolean(), nullable=True),
        sa.Column("conference_competition", sa.Boolean(), nullable=True),
        sa.Column("venue_id", sa.String(length=191), nullable=True),
        sa.Column("venue_name", sa.String(length=500), nullable=True),
        sa.Column("venue_address", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("summary_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_events_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sa.UniqueConstraint("league_id", "source_id", name="uq_events_league_source"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_events_league_start_at", "events", ["league_id", "start_at"])
    op.create_index("ix_events_status", "events", ["status_state", "completed"])

    op.create_table(
        "event_competitors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=True),
        sa.Column("competition_id", sa.String(length=191), nullable=True),
        sa.Column("source_id", sa.String(length=191), nullable=False),
        sa.Column("uid", sa.String(length=255), nullable=True),
        sa.Column("competitor_type", sa.String(length=100), nullable=True),
        sa.Column("sort_order", sa.SmallInteger(), nullable=True),
        sa.Column("home_away", sa.String(length=20), nullable=True),
        sa.Column("winner", sa.Boolean(), nullable=True),
        sa.Column("score", sa.String(length=100), nullable=True),
        sa.Column("linescores", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("records", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("statistics", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("leaders", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_competitors_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name=op.f("fk_event_competitors_team_id_teams"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_competitors")),
        sa.UniqueConstraint(
            "event_id", "competition_id", "source_id", name="uq_event_competitors_source"
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_event_competitors_team_id", "event_competitors", ["team_id"])

    op.create_table(
        "news_articles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("league_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(length=191), nullable=False),
        sa.Column("uid", sa.String(length=255), nullable=True),
        sa.Column("headline", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("last_modified_at", sa.DateTime(), nullable=True),
        sa.Column("article_type", sa.String(length=100), nullable=True),
        sa.Column("byline", sa.String(length=500), nullable=True),
        sa.Column("link_url", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("categories", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_news_articles_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_articles")),
        sa.UniqueConstraint("league_id", "source_id", name="uq_news_articles_league_source"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "ix_news_articles_league_published", "news_articles", ["league_id", "published_at"]
    )

    op.create_table(
        "rankings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("league_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(length=191), nullable=False),
        sa.Column("uid", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("short_name", sa.String(length=150), nullable=True),
        sa.Column("full_name", sa.String(length=500), nullable=True),
        sa.Column("season_year", sa.SmallInteger(), nullable=True),
        sa.Column("week", sa.SmallInteger(), nullable=True),
        sa.Column("raw_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_rankings_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rankings")),
        sa.UniqueConstraint("league_id", "source_id", name="uq_rankings_league_source"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "ix_rankings_league_season_week", "rankings", ["league_id", "season_year", "week"]
    )

    op.create_table(
        "ranking_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ranking_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=True),
        sa.Column("source_id", sa.String(length=191), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("previous_rank", sa.Integer(), nullable=True),
        sa.Column("first_rank", sa.Integer(), nullable=True),
        sa.Column("rank_delta", sa.Integer(), nullable=True),
        sa.Column("points", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("record", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ranking_id"],
            ["rankings.id"],
            name=op.f("fk_ranking_entries_ranking_id_rankings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name=op.f("fk_ranking_entries_team_id_teams"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ranking_entries")),
        sa.UniqueConstraint("ranking_id", "source_id", name="uq_ranking_entries_ranking_source"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_ranking_entries_team_id", "ranking_entries", ["team_id"])

    op.create_table(
        "sync_states",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("league_id", sa.BigInteger(), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_successful_sync", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_sync_states_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_states")),
        sa.UniqueConstraint("league_id", "resource", name="uq_sync_states_league_resource"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    op.drop_table("sync_states")
    op.drop_table("ranking_entries")
    op.drop_table("rankings")
    op.drop_table("news_articles")
    op.drop_table("event_competitors")
    op.drop_table("events")
    op.drop_table("teams")
    op.drop_table("leagues")
    op.drop_table("sports")
