"""Create M05 production forecasting schema.

Revision ID: d5e6f7a8b9c0
Revises: c1f3a9d7e4b2
Create Date: 2026-07-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c1f3a9d7e4b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply M05 production forecasting and MLOps tables."""

    op.create_table(
        "model_training_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("training_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=True),
        sa.Column("metrics_summary_json", sa.JSON(), nullable=True),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("safe_error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "evaluation_window_start_utc < evaluation_window_end_utc",
            name=op.f("ck_model_training_runs_model_training_runs_evaluation_window_order_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'running', 'succeeded', 'failed', 'blocked')",
            name=op.f("ck_model_training_runs_model_training_runs_status_valid"),
        ),
        sa.CheckConstraint(
            "training_window_start_utc < training_window_end_utc",
            name=op.f("ck_model_training_runs_model_training_runs_training_window_order_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_training_runs")),
    )
    op.create_index("ix_model_training_runs_model_name", "model_training_runs", ["model_name"])
    op.create_index(
        "ix_model_training_runs_model_version", "model_training_runs", ["model_version"]
    )
    op.create_index(
        "ix_model_training_runs_started_at_utc",
        "model_training_runs",
        ["started_at_utc"],
    )
    op.create_index("ix_model_training_runs_status", "model_training_runs", ["status"])

    op.create_table(
        "model_artifacts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("model_training_run_id", sa.BigInteger(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("artifact_uri", sa.String(length=1024), nullable=False),
        sa.Column("artifact_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("training_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=True),
        sa.Column("metrics_summary_json", sa.JSON(), nullable=True),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evaluation_window_start_utc < evaluation_window_end_utc",
            name=op.f("ck_model_artifacts_model_artifacts_evaluation_window_order_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'available', 'failed', 'deprecated')",
            name=op.f("ck_model_artifacts_model_artifacts_status_valid"),
        ),
        sa.CheckConstraint(
            "training_window_start_utc < training_window_end_utc",
            name=op.f("ck_model_artifacts_model_artifacts_training_window_order_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["model_training_run_id"],
            ["model_training_runs.id"],
            name=op.f("fk_model_artifacts_model_training_run_id_model_training_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_artifacts")),
        sa.UniqueConstraint("artifact_hash", name="uq_model_artifacts_artifact_hash"),
    )
    op.create_index("ix_model_artifacts_model_name", "model_artifacts", ["model_name"])
    op.create_index("ix_model_artifacts_model_version", "model_artifacts", ["model_version"])
    op.create_index("ix_model_artifacts_status", "model_artifacts", ["status"])
    op.create_index(
        "ix_model_artifacts_training_run_id", "model_artifacts", ["model_training_run_id"]
    )

    op.create_table(
        "model_selection_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("model_training_run_id", sa.BigInteger(), nullable=True),
        sa.Column("model_artifact_id", sa.BigInteger(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("selection_status", sa.String(length=32), nullable=False),
        sa.Column("selection_reason", sa.String(length=1000), nullable=False),
        sa.Column("training_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candidate_metrics_json", sa.JSON(), nullable=False),
        sa.Column("baseline_metrics_json", sa.JSON(), nullable=False),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evaluation_window_start_utc < evaluation_window_end_utc",
            name=op.f(
                "ck_model_selection_results_model_selection_results_evaluation_window_order_valid"
            ),
        ),
        sa.CheckConstraint(
            "selection_status IN ('evaluated', 'selected', 'rejected', 'failed')",
            name=op.f("ck_model_selection_results_model_selection_results_status_valid"),
        ),
        sa.CheckConstraint(
            "training_window_start_utc < training_window_end_utc",
            name=op.f(
                "ck_model_selection_results_model_selection_results_training_window_order_valid"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["model_artifact_id"],
            ["model_artifacts.id"],
            name=op.f("fk_model_selection_results_model_artifact_id_model_artifacts"),
        ),
        sa.ForeignKeyConstraint(
            ["model_training_run_id"],
            ["model_training_runs.id"],
            name=op.f("fk_model_selection_results_model_training_run_id_model_training_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_selection_results")),
    )
    op.create_index(
        "ix_model_selection_results_artifact_id",
        "model_selection_results",
        ["model_artifact_id"],
    )
    op.create_index(
        "ix_model_selection_results_created_at_utc",
        "model_selection_results",
        ["created_at_utc"],
    )
    op.create_index(
        "ix_model_selection_results_status",
        "model_selection_results",
        ["selection_status"],
    )
    op.create_index(
        "ix_model_selection_results_training_run_id",
        "model_selection_results",
        ["model_training_run_id"],
    )

    op.create_table(
        "production_forecast_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("model_artifact_id", sa.BigInteger(), nullable=True),
        sa.Column("feature_snapshot_run_id", sa.BigInteger(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("forecast_issue_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quality_status", sa.String(length=64), nullable=True),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("safe_error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status IN ('planned', 'running', 'succeeded', 'failed', 'blocked')",
            name=op.f("ck_production_forecast_runs_production_forecast_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_run_id"],
            ["feature_snapshot_runs.id"],
            name=op.f("fk_production_forecast_runs_feature_snapshot_run_id_feature_snapshot_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["model_artifact_id"],
            ["model_artifacts.id"],
            name=op.f("fk_production_forecast_runs_model_artifact_id_model_artifacts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_production_forecast_runs")),
    )
    op.create_index(
        "ix_production_forecast_runs_artifact_id",
        "production_forecast_runs",
        ["model_artifact_id"],
    )
    op.create_index(
        "ix_production_forecast_runs_feature_snapshot_run_id",
        "production_forecast_runs",
        ["feature_snapshot_run_id"],
    )
    op.create_index(
        "ix_production_forecast_runs_issue_time",
        "production_forecast_runs",
        ["forecast_issue_time_utc"],
    )
    op.create_index("ix_production_forecast_runs_status", "production_forecast_runs", ["status"])

    op.create_table(
        "production_forecast_predictions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("production_forecast_run_id", sa.BigInteger(), nullable=False),
        sa.Column("feature_snapshot_row_id", sa.BigInteger(), nullable=True),
        sa.Column("forecast_issue_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_interval_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_interval_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_hour", sa.Integer(), nullable=False),
        sa.Column("p10_demand_mw", sa.Numeric(12, 3), nullable=True),
        sa.Column("p50_demand_mw", sa.Numeric(12, 3), nullable=True),
        sa.Column("p90_demand_mw", sa.Numeric(12, 3), nullable=True),
        sa.Column("point_forecast_demand_mw", sa.Numeric(12, 3), nullable=True),
        sa.Column("prediction_type", sa.String(length=64), nullable=False),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "lead_hour > 0",
            name=op.f(
                "ck_production_forecast_predictions_production_forecast_predictions_lead_hour_positive"
            ),
        ),
        sa.CheckConstraint(
            "p10_demand_mw IS NULL OR p50_demand_mw IS NULL OR p10_demand_mw <= p50_demand_mw",
            name=op.f(
                "ck_production_forecast_predictions_production_forecast_predictions_p10_not_above_p50"
            ),
        ),
        sa.CheckConstraint(
            "p50_demand_mw IS NOT NULL OR point_forecast_demand_mw IS NOT NULL",
            name=op.f(
                "ck_production_forecast_predictions_production_forecast_predictions_point_or_p50_required"
            ),
        ),
        sa.CheckConstraint(
            "p90_demand_mw IS NULL OR p50_demand_mw IS NULL OR p90_demand_mw >= p50_demand_mw",
            name=op.f(
                "ck_production_forecast_predictions_production_forecast_predictions_p90_not_below_p50"
            ),
        ),
        sa.CheckConstraint(
            "target_interval_start_utc < target_interval_end_utc",
            name=op.f(
                "ck_production_forecast_predictions_production_forecast_predictions_target_interval_order_valid"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["feature_snapshot_row_id"],
            ["feature_snapshot_rows.id"],
            name=op.f(
                "fk_production_forecast_predictions_feature_snapshot_row_id_feature_snapshot_rows"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["production_forecast_run_id"],
            ["production_forecast_runs.id"],
            name=op.f(
                "fk_production_forecast_predictions_production_forecast_run_id_production_forecast_runs"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_production_forecast_predictions")),
        sa.UniqueConstraint(
            "production_forecast_run_id",
            "forecast_issue_time_utc",
            "target_interval_start_utc",
            name="uq_production_forecast_predictions_run_issue_target",
        ),
    )
    op.create_index(
        "ix_production_forecast_predictions_issue_time",
        "production_forecast_predictions",
        ["forecast_issue_time_utc"],
    )
    op.create_index(
        "ix_production_forecast_predictions_run_id",
        "production_forecast_predictions",
        ["production_forecast_run_id"],
    )
    op.create_index(
        "ix_production_forecast_predictions_target_start",
        "production_forecast_predictions",
        ["target_interval_start_utc"],
    )

    op.create_table(
        "forecast_peak_outputs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("production_forecast_run_id", sa.BigInteger(), nullable=False),
        sa.Column("peak_target_interval_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("peak_target_interval_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("peak_demand_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("peak_lead_hour", sa.Integer(), nullable=False),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "peak_demand_mw >= 0",
            name=op.f("ck_forecast_peak_outputs_forecast_peak_outputs_peak_demand_nonnegative"),
        ),
        sa.CheckConstraint(
            "peak_lead_hour > 0",
            name=op.f("ck_forecast_peak_outputs_forecast_peak_outputs_lead_hour_positive"),
        ),
        sa.CheckConstraint(
            "peak_target_interval_start_utc < peak_target_interval_end_utc",
            name=op.f("ck_forecast_peak_outputs_forecast_peak_outputs_peak_interval_order_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["production_forecast_run_id"],
            ["production_forecast_runs.id"],
            name=op.f(
                "fk_forecast_peak_outputs_production_forecast_run_id_production_forecast_runs"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_peak_outputs")),
        sa.UniqueConstraint("production_forecast_run_id", name="uq_forecast_peak_outputs_run_id"),
    )
    op.create_index(
        "ix_forecast_peak_outputs_peak_start",
        "forecast_peak_outputs",
        ["peak_target_interval_start_utc"],
    )
    op.create_index(
        "ix_forecast_peak_outputs_run_id",
        "forecast_peak_outputs",
        ["production_forecast_run_id"],
    )

    op.create_table(
        "forecast_ramp_outputs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("production_forecast_run_id", sa.BigInteger(), nullable=False),
        sa.Column("target_interval_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_target_interval_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forecast_ramp_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("absolute_ramp_mw", sa.Numeric(12, 3), nullable=False),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "absolute_ramp_mw >= 0",
            name=op.f("ck_forecast_ramp_outputs_forecast_ramp_outputs_absolute_ramp_nonnegative"),
        ),
        sa.CheckConstraint(
            "previous_target_interval_start_utc < target_interval_start_utc",
            name=op.f("ck_forecast_ramp_outputs_forecast_ramp_outputs_previous_before_target"),
        ),
        sa.ForeignKeyConstraint(
            ["production_forecast_run_id"],
            ["production_forecast_runs.id"],
            name=op.f(
                "fk_forecast_ramp_outputs_production_forecast_run_id_production_forecast_runs"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_ramp_outputs")),
        sa.UniqueConstraint(
            "production_forecast_run_id",
            "target_interval_start_utc",
            name="uq_forecast_ramp_outputs_run_target",
        ),
    )
    op.create_index(
        "ix_forecast_ramp_outputs_run_id",
        "forecast_ramp_outputs",
        ["production_forecast_run_id"],
    )
    op.create_index(
        "ix_forecast_ramp_outputs_target_start",
        "forecast_ramp_outputs",
        ["target_interval_start_utc"],
    )

    op.create_table(
        "model_performance_summaries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("model_artifact_id", sa.BigInteger(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("metric_unit", sa.String(length=64), nullable=True),
        sa.Column("row_count", sa.BigInteger(), nullable=False),
        sa.Column("evaluation_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evaluation_window_start_utc < evaluation_window_end_utc",
            name=op.f(
                "ck_model_performance_summaries_model_performance_summaries_evaluation_window_order_valid"
            ),
        ),
        sa.CheckConstraint(
            "row_count >= 0",
            name=op.f(
                "ck_model_performance_summaries_model_performance_summaries_row_count_nonnegative"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["model_artifact_id"],
            ["model_artifacts.id"],
            name=op.f("fk_model_performance_summaries_model_artifact_id_model_artifacts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_performance_summaries")),
        sa.UniqueConstraint(
            "model_artifact_id",
            "metric_name",
            "evaluation_window_start_utc",
            "evaluation_window_end_utc",
            name="uq_model_performance_summaries_artifact_metric_window",
        ),
    )
    op.create_index(
        "ix_model_performance_summaries_artifact_id",
        "model_performance_summaries",
        ["model_artifact_id"],
    )
    op.create_index(
        "ix_model_performance_summaries_metric_name",
        "model_performance_summaries",
        ["metric_name"],
    )

    op.create_table(
        "model_drift_summaries",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("model_artifact_id", sa.BigInteger(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("feature_version", sa.String(length=128), nullable=False),
        sa.Column("feature_name", sa.String(length=128), nullable=False),
        sa.Column("drift_metric_name", sa.String(length=128), nullable=False),
        sa.Column("drift_score", sa.Numeric(18, 6), nullable=True),
        sa.Column("baseline_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comparison_window_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comparison_window_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("lineage_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "baseline_window_start_utc < baseline_window_end_utc",
            name=op.f("ck_model_drift_summaries_model_drift_summaries_baseline_window_order_valid"),
        ),
        sa.CheckConstraint(
            "comparison_window_start_utc < comparison_window_end_utc",
            name=op.f(
                "ck_model_drift_summaries_model_drift_summaries_comparison_window_order_valid"
            ),
        ),
        sa.CheckConstraint(
            "drift_score IS NULL OR drift_score >= 0",
            name=op.f("ck_model_drift_summaries_model_drift_summaries_drift_score_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["model_artifact_id"],
            ["model_artifacts.id"],
            name=op.f("fk_model_drift_summaries_model_artifact_id_model_artifacts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_drift_summaries")),
    )
    op.create_index(
        "ix_model_drift_summaries_artifact_id",
        "model_drift_summaries",
        ["model_artifact_id"],
    )
    op.create_index(
        "ix_model_drift_summaries_created_at_utc",
        "model_drift_summaries",
        ["created_at_utc"],
    )
    op.create_index(
        "ix_model_drift_summaries_feature_name",
        "model_drift_summaries",
        ["feature_name"],
    )


def downgrade() -> None:
    """Revert M05 production forecasting and MLOps tables."""

    op.drop_table("model_drift_summaries")
    op.drop_table("model_performance_summaries")
    op.drop_table("forecast_ramp_outputs")
    op.drop_table("forecast_peak_outputs")
    op.drop_table("production_forecast_predictions")
    op.drop_table("production_forecast_runs")
    op.drop_table("model_selection_results")
    op.drop_table("model_artifacts")
    op.drop_table("model_training_runs")
