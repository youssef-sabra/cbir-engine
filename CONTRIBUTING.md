# Contributing

## Branching strategy

This project uses **trunk-based development**:
- `main` is always deployable (in the CI sense: it always passes the full pipeline).
- Work happens on short-lived feature branches (`feat/...`, `fix/...`, `chore/...`) branched from `main`.
- Branches are merged back via pull request as soon as the change is complete and passing CI — avoid
  long-lived branches that drift from `main`.

This pairs directly with the CI pipeline's design: every merge to `main` is expected to pass build, lint,
test, and the local-stack startup check without manual intervention.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) style:

```
feat(catalog-service): add manifest import endpoint
fix(query-service): correct pagination offset bug
chore(infra): add reserved AWS provider stub
docs(prd): update MVP scope after design-partner feedback
```

This keeps history scannable and makes it straightforward to generate changelogs later if needed.

## Pull request expectations

- Every PR must pass CI (build, lint, test, compose validation, startup check) before merge.
- Keep PRs scoped to one milestone task where possible — smaller, reviewable diffs over large batched changes.
- If a PR changes anything under `infra/`, call that out explicitly in the PR description, even though the
  CI pipeline does not deploy — infrastructure changes deserve the same review rigor as application code.
- If a PR touches a service's `domain/` or `application/` layer (once those exist from Milestone 2 onward),
  reviewers should specifically check that no framework- or vendor-specific import has leaked into those
  layers (see `docs/CLEAN_ARCHITECTURE.md`).

## Code style

- Python: formatted and linted with `ruff` (see each service's `pyproject.toml` once services exist).
- Terraform: run `terraform fmt` before committing any `.tf` file.
- YAML (Kubernetes manifests, GitHub Actions): 2-space indentation, per `.editorconfig`.

## Local development

See the root `README.md` Quickstart section. `docker compose up --build` should always be sufficient
to start developing — if it stops being that simple, that's a bug in the setup, not something to work around.
