# overlays/azure/

**Status: reserved, not yet implemented.**

Would contain AKS-specific Kustomize patches (e.g. an Azure Application Gateway ingress class, an Azure
Disk-backed `StorageClass` reference) layered on top of `infra/kubernetes/base/`, mirroring the pattern in
`overlays/gcp/kustomization.yaml`.
