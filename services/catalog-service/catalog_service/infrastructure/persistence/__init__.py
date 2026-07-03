"""SQLAlchemy machinery and ORM models for the Milestone 3 data layer.

catalog-service's migration package owns: catalog_items, embedding_refs,
feedback, usage_records, adapter_versions — plus enabling the pgvector
extension. Ownership notes:

- usage_records will re-home to tenant-service (billing/metering milestone)
  and adapter_versions to ai-service (Milestone 5+) when those services
  exist; creating them here now delivers the complete Milestone 3 schema
  with a documented, mechanical migration-package move later (the tables
  themselves don't change).
- `metadata_` maps to the DB column "metadata" (the attribute name
  `metadata` is reserved by SQLAlchemy's declarative base).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class CatalogItemRow(Base):
    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("tenant_id", "external_id", name="uq_items_tenant_ext"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    phash: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmbeddingRefRow(Base):
    """Provenance pointer from a catalog item to its vector(s) in the vector
    database (populated from Milestone 5/6 onward)."""

    __tablename__ = "embedding_refs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vector_db_collection: Mapped[str] = mapped_column(Text, nullable=False)
    vector_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedbackRow(Base):
    """Tenant relevance feedback (FR3.1), consumed by fine-tuning later."""

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("catalog_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_ref: Mapped[str] = mapped_column(Text, nullable=False)
    relevant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageRecordRow(Base):
    """Usage metering events (owner-to-be: tenant-service)."""

    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class AdapterVersionRow(Base):
    """Per-tenant fine-tuned adapter versions (owner-to-be: ai-service)."""

    __tablename__ = "adapter_versions"
    __table_args__ = (UniqueConstraint("tenant_id", "version", name="uq_adapter_tenant_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def build_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)
