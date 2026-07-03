"""Milestone 4 ingestion: add pipeline-status columns to catalog_items.

- duplicate_of_id: points a DUPLICATE item at the original it matched (FR1.2).
- failure_reason: human-readable reason for a FAILED ingestion job (NFR21).
- indexed_at: when the item became searchable (re-index latency metric).

No new tables: the ingestion job's lifecycle is the item's `status` field, so
job-status tracking (pending_upload/queued/processing/indexed/duplicate/failed)
is queryable via the existing catalog API. The queue and dead-letter queue
live in Redis, not PostgreSQL.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_catalog"
down_revision = "0001_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("catalog_items", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column(
        "catalog_items", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_catalog_items_status", "catalog_items", ["status"])


def downgrade() -> None:
    op.drop_index("ix_catalog_items_status", table_name="catalog_items")
    op.drop_column("catalog_items", "indexed_at")
    op.drop_column("catalog_items", "failure_reason")
    op.drop_column("catalog_items", "duplicate_of_id")
