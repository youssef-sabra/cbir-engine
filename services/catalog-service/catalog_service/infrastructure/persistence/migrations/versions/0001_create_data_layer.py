"""Milestone 3 data layer: catalog_items, embedding_refs, feedback,
usage_records, adapter_versions — and the pgvector extension.

Design notes:
- pgvector is enabled here (CREATE EXTENSION) so small-tenant vector
  workloads can live in PostgreSQL per docs/TECH_STACK.md; actual vector
  columns arrive with the embedding milestones.
- catalog_items.tenant_id is indexed but deliberately NOT a foreign key to
  tenants (owned by auth-service's migration package): cross-service-package
  FKs would couple the services' deploy order. Tenant validity is enforced
  at the application layer — every request's tenant_id comes from
  auth-service validation before any row is written.
- embedding_refs/feedback cascade on item deletion: the right-to-erasure
  workflow (NFR13) removes one catalog item row and the database guarantees
  no derived metadata survives it.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_catalog"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "catalog_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False, unique=True),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("phash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_items_tenant_ext"),
    )
    op.create_index("ix_catalog_items_tenant_id", "catalog_items", ["tenant_id"])
    op.create_index("ix_catalog_items_phash", "catalog_items", ["phash"])

    op.create_table(
        "embedding_refs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("catalog_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vector_db_collection", sa.Text(), nullable=False),
        sa.Column("vector_id", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_embedding_refs_item_id", "embedding_refs", ["item_id"])

    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("catalog_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query_ref", sa.Text(), nullable=False),
        sa.Column("relevant", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_feedback_item_id", "feedback", ["item_id"])

    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_records_tenant_id", "usage_records", ["tenant_id"])
    op.create_index("ix_usage_records_occurred_at", "usage_records", ["occurred_at"])

    op.create_table(
        "adapter_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "version", name="uq_adapter_tenant_version"),
    )
    op.create_index("ix_adapter_versions_tenant_id", "adapter_versions", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("adapter_versions")
    op.drop_table("usage_records")
    op.drop_table("feedback")
    op.drop_table("embedding_refs")
    op.drop_table("catalog_items")
    # The extension is left installed: other migration packages may rely on it.
