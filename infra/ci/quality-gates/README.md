# quality-gates/

**Status: reserved, not yet populated.**

Will hold the retrieval-quality regression gate configuration (Recall@K, nDCG benchmark thresholds)
introduced in Milestone 9, per `docs/MILESTONES.md`. This is a CBIR-specific CI gate -- required before any
embedding-model or reranking-logic change reaches production -- and is deliberately given its own visible
location rather than being buried inside a generic "tests" step, per `docs/CLEAN_ARCHITECTURE.md` Section 8.

Not used by the current CI pipeline (`.github/workflows/ci.yml`), which only covers Milestone 1's scope
(build, lint, test, containerize, compose-validate, startup check).
