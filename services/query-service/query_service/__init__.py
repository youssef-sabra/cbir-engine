"""query-service — the core customer-facing search API (Milestones 7-9).

Orchestrates the retrieval path: embed the query (via ai-service) -> ANN
search in the tenant's vector collection (with metadata filters) -> optional
rerank -> ranked results with scores. The most latency-sensitive service;
kept lean and stateless. Caching (Milestone 8) sits in front of the embed +
search steps.

Clean Architecture layering per docs/CLEAN_ARCHITECTURE.md Section 3.
"""
