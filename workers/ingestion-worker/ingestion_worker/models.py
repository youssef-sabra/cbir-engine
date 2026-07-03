"""Thin SQLAlchemy models mirroring the columns the worker reads/writes.

Source of truth for this schema is catalog-service's Alembic migrations
(catalog_items, embedding_refs). These models are intentionally a subset and
are never used to create or migrate tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class CatalogItemRow(Base):
    __tablename__ = "catalog_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    object_key: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    phash: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EmbeddingRefRow(Base):
    __tablename__ = "embedding_refs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_items.id", ondelete="CASCADE")
    )
    vector_db_collection: Mapped[str] = mapped_column(Text)
    vector_id: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def build_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)
