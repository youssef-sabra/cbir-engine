# pipelines/

The actual, executable CI pipeline definition lives at `.github/workflows/ci.yml` — GitHub Actions requires
workflow files to live under `.github/workflows/` at the repository root, so it cannot physically live here.

This directory exists to document that constraint and to hold pipeline *documentation* / any future
non-GitHub-Actions pipeline definitions (e.g. if a GitLab CI or other platform pipeline is ever added
alongside GitHub Actions). See `.github/workflows/ci.yml` for the current, real pipeline, and
`docs/MILESTONES.md` Milestone 1 for what it's expected to do at this stage.
