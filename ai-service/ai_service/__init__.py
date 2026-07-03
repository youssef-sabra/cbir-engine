"""ai-service — embedding generation and reranking (Milestones 5 & 9).

Turns images and text into vectors in a shared embedding space, and reranks
candidate shortlists. The encoder is a pluggable provider (NFR16): the
default is a deterministic, CPU-only local embedder that needs no GPU or
model download, so the whole platform runs and is testable locally; SigLIP 2
and DINOv2 adapters slot into the same seam when real weights are available.

Internally follows the Clean Architecture layering in
docs/CLEAN_ARCHITECTURE.md Section 3.
"""
