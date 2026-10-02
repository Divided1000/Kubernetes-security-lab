# Kubernetes Security Lab

A hands-on lab hardening a containerized app on Kubernetes against the
**OWASP Kubernetes Top 10** — container hardening, least-privilege RBAC, network
segmentation, policy-as-code enforcement (Kyverno), and CI security gates.

➡️ **The project and full documentation live in
[`k8s-security-lab/`](./k8s-security-lab/).**

- [Project README](./k8s-security-lab/README.md) — controls, OWASP K8s mapping, how to run
- [Threat Model](./k8s-security-lab/THREAT_MODEL.md) — assets, trust boundaries, STRIDE analysis
- [CI security gates](./.github/workflows/security.yml) — Trivy, Gitleaks, Kyverno on every push
