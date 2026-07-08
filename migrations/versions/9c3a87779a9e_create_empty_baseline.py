"""Create empty baseline.

Revision ID: 9c3a87779a9e
Revises:
Create Date: 2026-07-08

"""

from collections.abc import Sequence

revision: str = "9c3a87779a9e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the empty baseline migration."""


def downgrade() -> None:
    """Revert the empty baseline migration."""
