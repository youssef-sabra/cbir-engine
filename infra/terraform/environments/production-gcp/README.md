# production-gcp

**Not deployed. Not referenced by CI. No credentials required to have this directory exist.**

This is the root Terraform module that would deploy the reference GCP production environment, once cloud
deployment becomes an active milestone (see `docs/MILESTONES.md`). Until then, this directory is prepared,
reviewed, and version-controlled like any other code, but never executed.

To actually deploy this (in a future milestone, deliberately):

1. `cp terraform.tfvars.example terraform.tfvars` and fill in your real GCP project ID.
2. Uncomment and configure the `backend "gcs"` block in `main.tf` (a remote state backend should be set up
   before the first real `apply`, not after).
3. `terraform init && terraform plan` — review carefully before `terraform apply`.

None of this is part of Milestone 1.
