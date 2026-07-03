"""catalog-service — the data layer & storage foundation (Milestone 3).

Owns catalog item metadata (PostgreSQL), raw image objects (S3-compatible
storage via signed URLs), and the right-to-erasure deletion workflow.
Milestone 4 extends this service with the asynchronous ingestion pipeline
(dedup, queue, workers).

Internally follows the Clean Architecture layering documented in
docs/CLEAN_ARCHITECTURE.md Section 3.
"""
