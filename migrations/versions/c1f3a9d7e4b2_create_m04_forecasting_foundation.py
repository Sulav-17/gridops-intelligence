"""Create M04 forecasting foundation.

Revision ID: c1f3a9d7e4b2
Revises: b2a6d3f4c8e9
Create Date: 2026-07-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1f3a9d7e4b2"
down_revision: str | Sequence[str] | None = "b2a6d3f4c8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply M04 forecasting foundation tables."""

    op.create_table(
        "forecast_issues",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("forecast_issue_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_length_hours", sa.Integer(), nullable=False),
        sa.Column("forecast_type", sa.String(length=128), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("point_in_time_safety_rule", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quality_blocking_behavior", sa.String(length=256), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "horizon_length_hours > 0",
            name=op.f("ck_forecast_issues_forecast_issues_horizon_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('defined', 'blocked', 'ready')",
            name=op.f("ck_forecast_issues_forecast_issues_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_issues")),
        sa.UniqueConstraint(
            "forecast_issue_time_utc",
            "forecast_type",
            "feature_version",
            name="uq_forecast_issues_issue_type_feature_version",
        ),
    )
    op.create_index("ix_forecast_issues_forecast_type", "forecast_issues", ["forecast_type"])
    op.create_index("ix_forecast_issues_issue_time", "forecast_issues", ["forecast_issue_time_utc"])
    op.create_index("ix_forecast_issues_status", "forecast_issues", ["status"])

    op.create_table(
        "feature_snapshot_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("forecast_issue_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quality_status", sa.String(length=64), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status IN ('planned', 'running', 'succeeded', 'failed', 'blocked')",
            name=op.f("ck_feature_snapshot_runs_feature_snapshot_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["forecast_issue_id"],
            ["forecast_issues.id"],
            name=op.f("fk_feature_snapshot_runs_forecast_issue_id_forecast_issues"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feature_snapshot_runs")),
    )
    op.create_index(
        "ix_feature_snapshot_runs_forecast_issue_id",
        "feature_snapshot_runs",
        ["forecast_issue_id"],
    )
    op.create_index(
        "ix_feature_snapshot_runs_started_at_utc",
        "feature_snapshot_runs",
        ["started_at_utc"],
    )
    op.create_index("ix_feature_snapshot_runs_status", "feature_snapshot_runs", ["status"])

    op.create_table(
        "baseline_forecast_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("baseline_name", sa.String(length=128), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("training_window_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_window_end_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation_window_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation_window_end_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quality_blocking_behavior", sa.String(length=256), nullable=True),
        sa.Column("run_metadata", sa.Text(), nullable=True),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "evaluation_window_start_utc IS NULL OR evaluation_window_end_utc IS NULL "
            "OR evaluation_window_start_utc < evaluation_window_end_utc",
            name=op.f(
                "ck_baseline_forecast_runs_baseline_forecast_runs_evaluation_window_order_valid"
            ),
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'running', 'succeeded', 'failed', 'blocked')",
            name=op.f("ck_baseline_forecast_runs_baseline_forecast_runs_status_valid"),
        ),
        sa.CheckConstraint(
            "training_window_start_utc IS NULL OR training_window_end_utc IS NULL "
            "OR training_window_start_utc < training_window_end_utc",
            name=op.f(
                "ck_baseline_forecast_runs_baseline_forecast_runs_training_window_order_valid"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_baseline_forecast_runs")),
    )
    op.create_index(
        "ix_baseline_forecast_runs_baseline_name",
        "baseline_forecast_runs",
        ["baseline_name"],
    )
    op.create_index(
        "ix_baseline_forecast_runs_started_at_utc",
        "baseline_forecast_runs",
        ["started_at_utc"],
    )
    op.create_index("ix_baseline_forecast_runs_status", "baseline_forecast_runs", ["status"])

    op.create_table(
        "feature_snapshot_rows",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("feature_snapshot_run_id", sa.BigInteger(), nullable=False),
        sa.Column("forecast_issue_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_interval_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_interval_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_hour", sa.Integer(), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("quality_status", sa.String(length=64), nullable=False),
        sa.Column("demand_source_row_id", sa.BigInteger(), nullable=True),
        sa.Column("weather_observation_source_row_id", sa.BigInteger(), nullable=True),
        sa.Column("weather_forecast_source_row_id", sa.BigInteger(), nullable=True),
        sa.Column("related_quality_run_id", sa.BigInteger(), nullable=True),
        sa.Column("lineage_metadata", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "lead_hour > 0",
            name=op.f("ck_feature_snapshot_rows_feature_snapshot_rows_lead_hour_positive"),
        ),
        sa.CheckConstraint(
            "target_interval_start_utc < target_interval_end_utc",
            name=op.f("ck_feature_snapshot_rows_feature_snapshot_rows_target_interval_order_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["demand_source_row_id"],
            ["ieso_hourly_demand.id"],
            name=op.f("fk_feature_snapshot_rows_demand_source_row_id_ieso_hourly_demand"),
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_run_id"],
            ["feature_snapshot_runs.id"],
            name=op.f("fk_feature_snapshot_rows_feature_snapshot_run_id_feature_snapshot_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["related_quality_run_id"],
            ["quality_runs.id"],
            name=op.f("fk_feature_snapshot_rows_related_quality_run_id_quality_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["weather_forecast_source_row_id"],
            ["weather_forecasts.id"],
            name=op.f("fk_feature_snapshot_rows_weather_forecast_source_row_id_weather_forecasts"),
        ),
        sa.ForeignKeyConstraint(
            ["weather_observation_source_row_id"],
            ["weather_observations.id"],
            name=op.f(
                "fk_feature_snapshot_rows_weather_observation_source_row_id_weather_observations"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feature_snapshot_rows")),
        sa.UniqueConstraint(
            "feature_snapshot_run_id",
            "target_interval_start_utc",
            name="uq_feature_snapshot_rows_run_target_start",
        ),
    )
    op.create_index(
        "ix_feature_snapshot_rows_run_id", "feature_snapshot_rows", ["feature_snapshot_run_id"]
    )
    op.create_index(
        "ix_feature_snapshot_rows_target_start",
        "feature_snapshot_rows",
        ["target_interval_start_utc"],
    )

    op.create_table(
        "baseline_forecast_predictions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("baseline_forecast_run_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_snapshot_row_id", sa.BigInteger(), nullable=True),
        sa.Column("forecast_issue_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_interval_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_interval_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_hour", sa.Integer(), nullable=False),
        sa.Column("predicted_demand_mw", sa.Numeric(12, 3), nullable=True),
        sa.Column("actual_demand_mw", sa.Numeric(12, 3), nullable=True),
        sa.Column("prediction_status", sa.String(length=32), nullable=False),
        sa.Column("lineage_metadata", sa.Text(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "lead_hour > 0",
            name=op.f(
                "ck_baseline_forecast_predictions_baseline_forecast_predictions_lead_hour_positive"
            ),
        ),
        sa.CheckConstraint(
            "target_interval_start_utc < target_interval_end_utc",
            name=op.f(
                "ck_baseline_forecast_predictions_baseline_forecast_predictions_target_interval_order_valid"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["baseline_forecast_run_id"],
            ["baseline_forecast_runs.id"],
            name=op.f(
                "fk_baseline_forecast_predictions_baseline_forecast_run_id_baseline_forecast_runs"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_row_id"],
            ["feature_snapshot_rows.id"],
            name=op.f(
                "fk_baseline_forecast_predictions_feature_snapshot_row_id_feature_snapshot_rows"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_baseline_forecast_predictions")),
        sa.UniqueConstraint(
            "baseline_forecast_run_id",
            "forecast_issue_time_utc",
            "target_interval_start_utc",
            name="uq_baseline_predictions_run_issue_target",
        ),
    )
    op.create_index(
        "ix_baseline_predictions_issue_time",
        "baseline_forecast_predictions",
        ["forecast_issue_time_utc"],
    )
    op.create_index(
        "ix_baseline_predictions_run_id",
        "baseline_forecast_predictions",
        ["baseline_forecast_run_id"],
    )
    op.create_index(
        "ix_baseline_predictions_target_start",
        "baseline_forecast_predictions",
        ["target_interval_start_utc"],
    )

    op.create_table(
        "baseline_metric_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("baseline_forecast_run_id", sa.BigInteger(), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("metric_unit", sa.String(length=64), nullable=True),
        sa.Column("evaluation_window_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation_window_end_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lineage_metadata", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["baseline_forecast_run_id"],
            ["baseline_forecast_runs.id"],
            name=op.f("fk_baseline_metric_results_baseline_forecast_run_id_baseline_forecast_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_baseline_metric_results")),
        sa.UniqueConstraint(
            "baseline_forecast_run_id",
            "metric_name",
            name="uq_baseline_metric_results_run_metric",
        ),
    )
    op.create_index(
        "ix_baseline_metric_results_metric_name",
        "baseline_metric_results",
        ["metric_name"],
    )
    op.create_index(
        "ix_baseline_metric_results_run_id",
        "baseline_metric_results",
        ["baseline_forecast_run_id"],
    )

    op.create_table(
        "baseline_slice_metric_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("baseline_forecast_run_id", sa.BigInteger(), nullable=False),
        sa.Column("slice_name", sa.String(length=128), nullable=False),
        sa.Column("slice_value", sa.String(length=128), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("metric_unit", sa.String(length=64), nullable=True),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lineage_metadata", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["baseline_forecast_run_id"],
            ["baseline_forecast_runs.id"],
            name=op.f(
                "fk_baseline_slice_metric_results_baseline_forecast_run_id_baseline_forecast_runs"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_baseline_slice_metric_results")),
        sa.UniqueConstraint(
            "baseline_forecast_run_id",
            "slice_name",
            "slice_value",
            "metric_name",
            name="uq_baseline_slice_metric_results_run_slice_metric",
        ),
    )
    op.create_index(
        "ix_baseline_slice_metric_results_metric_name",
        "baseline_slice_metric_results",
        ["metric_name"],
    )
    op.create_index(
        "ix_baseline_slice_metric_results_run_id",
        "baseline_slice_metric_results",
        ["baseline_forecast_run_id"],
    )
    op.create_index(
        "ix_baseline_slice_metric_results_slice",
        "baseline_slice_metric_results",
        ["slice_name", "slice_value"],
    )


def downgrade() -> None:
    """Revert M04 forecasting foundation tables."""

    op.drop_table("baseline_slice_metric_results")
    op.drop_table("baseline_metric_results")
    op.drop_table("baseline_forecast_predictions")
    op.drop_table("feature_snapshot_rows")
    op.drop_table("baseline_forecast_runs")
    op.drop_table("feature_snapshot_runs")
    op.drop_table("forecast_issues")
