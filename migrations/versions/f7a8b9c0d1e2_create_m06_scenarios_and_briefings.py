"""Create M06 scenario and briefing schema.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply M06 scenario and deterministic briefing tables."""

    op.create_table(
        "scenario_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("scenario_type", sa.String(length=64), nullable=False),
        sa.Column("production_forecast_run_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scenario_version", sa.String(length=128), nullable=False),
        sa.Column("generated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assumptions_json", sa.JSON(), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("safe_error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "scenario_type IN ('weather_adjustment', 'demand_growth', 'combined_weather_load')",
            name=op.f("ck_scenario_runs_scenario_runs_scenario_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name=op.f("ck_scenario_runs_scenario_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["production_forecast_run_id"],
            ["production_forecast_runs.id"],
            name=op.f("fk_scenario_runs_production_forecast_run_id_production_forecast_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_runs")),
    )
    op.create_index(
        "ix_scenario_runs_forecast_run_id",
        "scenario_runs",
        ["production_forecast_run_id"],
    )
    op.create_index(
        "ix_scenario_runs_generated_at_utc",
        "scenario_runs",
        ["generated_at_utc"],
    )
    op.create_index("ix_scenario_runs_scenario_type", "scenario_runs", ["scenario_type"])

    op.create_table(
        "scenario_assumptions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("scenario_run_id", sa.BigInteger(), nullable=False),
        sa.Column("assumption_name", sa.String(length=128), nullable=False),
        sa.Column("assumption_value", sa.String(length=256), nullable=False),
        sa.Column("assumption_unit", sa.String(length=64), nullable=True),
        sa.Column("assumption_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"],
            ["scenario_runs.id"],
            name=op.f("fk_scenario_assumptions_scenario_run_id_scenario_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_assumptions")),
    )
    op.create_index(
        "ix_scenario_assumptions_name",
        "scenario_assumptions",
        ["assumption_name"],
    )
    op.create_index(
        "ix_scenario_assumptions_scenario_run_id",
        "scenario_assumptions",
        ["scenario_run_id"],
    )

    op.create_table(
        "scenario_result_rows",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("scenario_run_id", sa.BigInteger(), nullable=False),
        sa.Column("production_forecast_prediction_id", sa.BigInteger(), nullable=True),
        sa.Column("target_interval_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_interval_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base_value_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("scenario_value_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("delta_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("row_metadata_json", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "target_interval_start_utc < target_interval_end_utc",
            name=op.f("ck_scenario_result_rows_scenario_result_rows_target_interval_order_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["production_forecast_prediction_id"],
            ["production_forecast_predictions.id"],
            name=op.f(
                "fk_scenario_result_rows_production_forecast_prediction_id_production_forecast_predictions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["scenario_run_id"],
            ["scenario_runs.id"],
            name=op.f("fk_scenario_result_rows_scenario_run_id_scenario_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_result_rows")),
    )
    op.create_index(
        "ix_scenario_result_rows_scenario_run_id",
        "scenario_result_rows",
        ["scenario_run_id"],
    )
    op.create_index(
        "ix_scenario_result_rows_target_start",
        "scenario_result_rows",
        ["target_interval_start_utc"],
    )

    op.create_table(
        "briefing_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("production_forecast_run_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("briefing_version", sa.String(length=128), nullable=False),
        sa.Column("generated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("safe_error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name=op.f("ck_briefing_runs_briefing_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["production_forecast_run_id"],
            ["production_forecast_runs.id"],
            name=op.f("fk_briefing_runs_production_forecast_run_id_production_forecast_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_briefing_runs")),
    )
    op.create_index(
        "ix_briefing_runs_forecast_run_id",
        "briefing_runs",
        ["production_forecast_run_id"],
    )
    op.create_index(
        "ix_briefing_runs_generated_at_utc",
        "briefing_runs",
        ["generated_at_utc"],
    )

    op.create_table(
        "briefing_facts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("briefing_run_id", sa.BigInteger(), nullable=False),
        sa.Column("fact_type", sa.String(length=128), nullable=False),
        sa.Column("fact_value_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["briefing_run_id"],
            ["briefing_runs.id"],
            name=op.f("fk_briefing_facts_briefing_run_id_briefing_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_briefing_facts")),
    )
    op.create_index("ix_briefing_facts_briefing_run_id", "briefing_facts", ["briefing_run_id"])
    op.create_index("ix_briefing_facts_fact_type", "briefing_facts", ["fact_type"])


def downgrade() -> None:
    """Revert M06 scenario and deterministic briefing tables."""

    op.drop_table("briefing_facts")
    op.drop_table("briefing_runs")
    op.drop_table("scenario_result_rows")
    op.drop_table("scenario_assumptions")
    op.drop_table("scenario_runs")
