"""Create M03 quality storage.

Revision ID: b2a6d3f4c8e9
Revises: 4f7d9b2a6c1e
Create Date: 2026-07-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2a6d3f4c8e9"
down_revision: str | Sequence[str] | None = "4f7d9b2a6c1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply M03 quality storage tables."""

    op.create_table(
        "quality_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("dataset_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_window_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_window_end_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_error_detail", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "checked_window_start_utc IS NULL OR checked_window_end_utc IS NULL "
            "OR checked_window_start_utc < checked_window_end_utc",
            name=op.f("ck_quality_runs_quality_runs_checked_window_order_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_quality_runs_quality_runs_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_runs")),
    )
    op.create_index("ix_quality_runs_dataset_name", "quality_runs", ["dataset_name"])
    op.create_index("ix_quality_runs_started_at_utc", "quality_runs", ["started_at_utc"])
    op.create_index("ix_quality_runs_status", "quality_runs", ["status"])

    op.create_table(
        "quality_results",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("quality_run_id", sa.BigInteger(), nullable=False),
        sa.Column("dataset_name", sa.String(length=128), nullable=False),
        sa.Column("check_name", sa.String(length=128), nullable=False),
        sa.Column("check_category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("observed_value", sa.Text(), nullable=True),
        sa.Column("expected_value", sa.Text(), nullable=True),
        sa.Column("affected_record_count", sa.BigInteger(), nullable=True),
        sa.Column("safe_detail", sa.String(length=1000), nullable=True),
        sa.Column("is_blocking", sa.Boolean(), nullable=False),
        sa.Column("related_ingestion_run_id", sa.BigInteger(), nullable=True),
        sa.Column("related_raw_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "affected_record_count IS NULL OR affected_record_count >= 0",
            name=op.f("ck_quality_results_quality_results_affected_record_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "check_category IN ("
            "'schema', 'completeness', 'continuity', 'uniqueness', 'range', "
            "'freshness', 'timestamp', 'dst', 'source_metadata'"
            ")",
            name=op.f("ck_quality_results_quality_results_check_category_valid"),
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name=op.f("ck_quality_results_quality_results_severity_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('passed', 'failed', 'skipped', 'error')",
            name=op.f("ck_quality_results_quality_results_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["quality_run_id"],
            ["quality_runs.id"],
            name=op.f("fk_quality_results_quality_run_id_quality_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["related_ingestion_run_id"],
            ["ingestion_runs.id"],
            name=op.f("fk_quality_results_related_ingestion_run_id_ingestion_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["related_raw_snapshot_id"],
            ["raw_snapshots.id"],
            name=op.f("fk_quality_results_related_raw_snapshot_id_raw_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_results")),
    )
    op.create_index("ix_quality_results_check_name", "quality_results", ["check_name"])
    op.create_index("ix_quality_results_created_at_utc", "quality_results", ["created_at_utc"])
    op.create_index("ix_quality_results_dataset_name", "quality_results", ["dataset_name"])
    op.create_index("ix_quality_results_quality_run_id", "quality_results", ["quality_run_id"])
    op.create_index("ix_quality_results_severity", "quality_results", ["severity"])
    op.create_index("ix_quality_results_status", "quality_results", ["status"])


def downgrade() -> None:
    """Revert M03 quality storage tables."""

    op.drop_table("quality_results")
    op.drop_table("quality_runs")
