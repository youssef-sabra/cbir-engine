# overlays/aws/

**Status: reserved, not yet implemented.**

Would contain EKS-specific Kustomize patches (e.g. `kubernetes.io/ingress.class: "alb"`, an EBS-backed
`StorageClass` reference) layered on top of `infra/kubernetes/base/`, mirroring the pattern in
`overlays/gcp/kustomization.yaml`.
