"""Create M06 alert foundation schema.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply M06 deterministic alert foundation tables."""

    op.create_table(
        "alert_evaluation_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("production_forecast_run_id", sa.BigInteger(), nullable=True),
        sa.Column("policy_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("safe_error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_alert_evaluation_runs_alert_evaluation_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["production_forecast_run_id"],
            ["production_forecast_runs.id"],
            name=op.f(
                "fk_alert_evaluation_runs_production_forecast_run_id_production_forecast_runs"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_evaluation_runs")),
    )
    op.create_index(
        "ix_alert_evaluation_runs_forecast_run_id",
        "alert_evaluation_runs",
        ["production_forecast_run_id"],
    )
    op.create_index("ix_alert_evaluation_runs_status", "alert_evaluation_runs", ["status"])
    op.create_index(
        "ix_alert_evaluation_runs_started_at_utc",
        "alert_evaluation_runs",
        ["started_at_utc"],
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("rule_name", sa.String(length=128), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("explanation", sa.String(length=1000), nullable=False),
        sa.Column("production_forecast_run_id", sa.BigInteger(), nullable=True),
        sa.Column("forecast_issue_time_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_interval_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_interval_end_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppressed_until_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_evidence_json", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "alert_type IN ("
            "'high_demand', 'ramp', 'forecast_deviation', 'source_health', "
            "'combined_context'"
            ")",
            name=op.f("ck_alerts_alerts_alert_type_valid"),
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'watch', 'warning', 'critical')",
            name=op.f("ck_alerts_alerts_severity_valid"),
        ),
        sa.CheckConstraint(
            "state IN ('open', 'acknowledged', 'resolved', 'suppressed', 'expired')",
            name=op.f("ck_alerts_alerts_state_valid"),
        ),
        sa.CheckConstraint(
            "target_interval_start_utc IS NULL OR target_interval_end_utc IS NULL "
            "OR target_interval_start_utc < target_interval_end_utc",
            name=op.f("ck_alerts_alerts_target_interval_order_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["production_forecast_run_id"],
            ["production_forecast_runs.id"],
            name=op.f("fk_alerts_production_forecast_run_id_production_forecast_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index("ix_alerts_alert_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_fingerprint", "alerts", ["fingerprint"])
    op.create_index("ix_alerts_forecast_run_id", "alerts", ["production_forecast_run_id"])
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_state", "alerts", ["state"])
    op.create_index("ix_alerts_target_start", "alerts", ["target_interval_start_utc"])
    op.create_index(
        "uq_alerts_active_fingerprint",
        "alerts",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text("state IN ('open', 'acknowledged')"),
    )

    op.create_table(
        "alert_evidence",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("alert_id", sa.BigInteger(), nullable=False),
        sa.Column("alert_evaluation_run_id", sa.BigInteger(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("generated_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["alert_evaluation_run_id"],
            ["alert_evaluation_runs.id"],
            name=op.f("fk_alert_evidence_alert_evaluation_run_id_alert_evaluation_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name=op.f("fk_alert_evidence_alert_id_alerts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_evidence")),
    )
    op.create_index("ix_alert_evidence_alert_id", "alert_evidence", ["alert_id"])
    op.create_index(
        "ix_alert_evidence_evaluation_run_id",
        "alert_evidence",
        ["alert_evaluation_run_id"],
    )
    op.create_index(
        "ix_alert_evidence_generated_at_utc",
        "alert_evidence",
        ["generated_at_utc"],
    )

    op.create_table(
        "alert_lifecycle_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("alert_id", sa.BigInteger(), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("transition_reason", sa.String(length=1000), nullable=True),
        sa.Column("changed_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "from_state IS NULL OR from_state IN "
            "('open', 'acknowledged', 'resolved', 'suppressed', 'expired')",
            name=op.f("ck_alert_lifecycle_history_alert_lifecycle_history_from_state_valid"),
        ),
        sa.CheckConstraint(
            "to_state IN ('open', 'acknowledged', 'resolved', 'suppressed', 'expired')",
            name=op.f("ck_alert_lifecycle_history_alert_lifecycle_history_to_state_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name=op.f("fk_alert_lifecycle_history_alert_id_alerts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_lifecycle_history")),
    )
    op.create_index(
        "ix_alert_lifecycle_history_alert_id",
        "alert_lifecycle_history",
        ["alert_id"],
    )
    op.create_index(
        "ix_alert_lifecycle_history_changed_at_utc",
        "alert_lifecycle_history",
        ["changed_at_utc"],
    )


def downgrade() -> None:
    """Revert M06 deterministic alert foundation tables."""

    op.drop_table("alert_lifecycle_history")
    op.drop_table("alert_evidence")
    op.drop_index("uq_alerts_active_fingerprint", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("alert_evaluation_runs")
