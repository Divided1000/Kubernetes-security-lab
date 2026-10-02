# Kubernetes Security Lab

A small, deliberately security-focused project: a containerized Python/Flask API
deployed to Kubernetes with least-privilege RBAC, a hardened container image, and
a container vulnerability scan. The goal is to demonstrate practical
**container and Kubernetes security** controls end to end — image hardening,
least privilege, and vulnerability management — on a minimal, easy-to-read app.

> **Why I built this (learning in progress).** I come from a cloud security and
> IAM background, and I'm actively building my container and Kubernetes security
> skills. This repo is my hands-on lab for working through the
> [**OWASP Kubernetes Top 10**](https://owasp.org/www-project-kubernetes-top-ten/)
> and container-hardening best practices — building a control, verifying it,
> and documenting what I learned (including the gaps I haven't closed yet).
> It's a living project; the roadmap at the bottom tracks what I'm learning next.

See [`THREAT_MODEL.md`](./THREAT_MODEL.md) for the security reasoning behind the
lab — assets, trust boundaries, STRIDE analysis, what's out of scope and why.

## Learning goals

- Work through the **OWASP Kubernetes Top 10** by implementing and verifying real controls
- Practice **container image hardening** (non-root, minimal surface, patched base)
- Apply **least-privilege RBAC** the same way I apply least privilege in AWS IAM
- Build a **vulnerability management** habit: scan, triage, decide, document

---

## What this demonstrates

| Area | Control shown here |
|------|--------------------|
| Container hardening | Non-root runtime user, cleaned package cache, minimal layers, healthcheck |
| Least privilege | Kubernetes RBAC `Role` scoped to read-only `get`/`list` on pods and services |
| Vulnerability management | Trivy image scan with triaged severity counts |
| Supply chain hygiene | Base image kept patched (`apt-get upgrade`), dependencies pinned to a single install layer |

---

## Mapping to the OWASP Kubernetes Top 10

The [OWASP Kubernetes Top 10](https://owasp.org/www-project-kubernetes-top-ten/)
is the Kubernetes-specific list of the most common security risks. I'm using it
as my study checklist. Here's where this lab currently stands against it — honest
about what's done and what I'm still learning:

| # | OWASP K8s risk | Status in this lab |
|---|----------------|--------------------|
| K01 | Insecure Workload Configurations | 🟢 Addressed — non-root `securityContext` (`runAsNonRoot`, dropped capabilities, `readOnlyRootFilesystem`, `seccompProfile`), resource limits, liveness/readiness probes |
| K02 | Supply Chain Vulnerabilities | 🟢 Addressed — Trivy image scan + triage; base image patched; Trivy runs in CI on every push |
| K03 | Overly Permissive RBAC | 🟢 Addressed — read-only `Role` scoped to `get`/`list` only |
| K04 | Lack of Centralized Policy Enforcement | 🟢 Addressed — Kyverno `ClusterPolicy` rejects pods that aren't non-root / drop caps / disallow privilege escalation (admission-time guardrail) |
| K05 | Inadequate Logging & Monitoring | 🔴 Learning next — audit logging, runtime visibility |
| K06 | Broken Authentication | 🟡 N/A for this scope — single demo app, no auth layer yet |
| K07 | Missing Network Segmentation Controls | 🟢 Addressed — default-deny `NetworkPolicy` with explicit allow for app port + DNS |
| K08 | Secrets Management Failures | 🟡 In progress — no secrets in image; Gitleaks secrets scan runs in CI; proper Secret handling to add |
| K09 | Misconfigured Cluster Components | 🟡 N/A for this scope — using a managed/local cluster |
| K10 | Outdated and Vulnerable Components | 🟢 Addressed — Trivy tracks CVEs; base kept current |

Legend: 🟢 implemented · 🟡 partial / in progress · 🔴 on my learning roadmap

---

## Architecture

```
client ──> Service (NodePort, 80 ─> 5000) ──> Deployment (2 replicas) ──> Flask API
                                                     │
                                                     └── RBAC: security-reader Role
                                                         bound to security-auditor user
```

- **`app/app.py`** — minimal Flask API with two endpoints:
  - `GET /` — returns a message and the pod hostname (useful to see which of the
    2 replicas served the request)
  - `GET /health` — liveness/health endpoint, also used by the container healthcheck
- **`Dockerfile`** — hardened image build (see below)
- **`k8s/`** — Kubernetes manifests (Deployment, Service, RBAC Role + RoleBinding)
- **`scan.json`** — Trivy vulnerability scan output (generated artifact, git-ignored)

---

## Container hardening

The image is built from `python:3.12-slim` and hardened with the following
controls (see `Dockerfile` for inline rationale):

- **Runs as a non-root user** (`appuser`, UID 10001). Dropping root privileges
  limits the blast radius if the process or container is compromised. Verified:

  ```bash
  $ docker run --rm k8s-security-api:hardened id
  uid=10001(appuser) gid=10001(appuser) groups=10001(appuser)
  ```

- **Patched base packages** — `apt-get upgrade` pulls current security fixes,
  and `rm -rf /var/lib/apt/lists/*` removes package metadata to shrink the image
  and avoid stale data in the layer.
- **No pip cache** — `--no-cache-dir` keeps the image smaller and cleaner.
- **Layer ordering for caching** — dependencies are installed before application
  code is copied, so code changes don't invalidate the dependency layer.
- **Healthcheck** — a `HEALTHCHECK` probes `/health` so the runtime can tell when
  the app is actually serving.

### Build and run

```bash
# Build the hardened image
docker build -t k8s-security-api:hardened .

# Confirm it runs as a non-root user
docker run --rm k8s-security-api:hardened id

# Run it locally
docker run --rm -p 5000:5000 k8s-security-api:hardened
curl localhost:5000/
curl localhost:5000/health
```

---

## Deploy to Kubernetes

```bash
# From the project root
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/rolebinding.yaml
kubectl apply -f k8s/networkpolicy.yaml

# Check it's running
kubectl get pods -l app=security-api
kubectl get svc security-api-service
```

> Tip: validate manifests without touching the cluster using
> `kubectl apply --dry-run=server -f k8s/<file>.yaml`.

### Workload hardening (OWASP K8s K01)

`k8s/deployment.yaml` applies defense-in-depth at the orchestration layer, so a
bad image can't quietly undo the Dockerfile hardening:

- **Pod `securityContext`** — `runAsNonRoot: true`, pinned `runAsUser: 10001`,
  and `seccompProfile: RuntimeDefault` (blocks dangerous syscalls).
- **Container `securityContext`** — `allowPrivilegeEscalation: false`,
  `readOnlyRootFilesystem: true`, and `capabilities: drop: [ALL]`. Writable
  scratch space is provided explicitly via an ephemeral `emptyDir` at `/tmp`.
- **Resource `requests`/`limits`** — caps CPU/memory so a compromised or buggy
  pod can't exhaust the node (a denial-of-service path).
- **Liveness & readiness probes** — both hit `/health`, so traffic is only sent
  to ready pods and wedged containers get restarted.

### Network segmentation (OWASP K8s K07)

`k8s/networkpolicy.yaml` flips the pod from Kubernetes' default allow-all to
**default-deny**, then explicitly allows only inbound traffic to port 5000 and
outbound DNS. This limits lateral movement if another pod in the cluster is
compromised. Note: enforcement requires a CNI that implements NetworkPolicy
(e.g. Calico, Cilium).

### Least-privilege RBAC

`k8s/rbac.yaml` defines a `Role` (`security-reader`) that grants only
**read-only** access — `get` and `list` on `pods` and `services`. Nothing more.
`k8s/rolebinding.yaml` binds it to a `security-auditor` user. This models the
principle of least privilege: an auditor identity can observe workloads without
the ability to modify or delete them.

---

## Policy enforcement with Kyverno (OWASP K8s K04)

Hardening a single manifest only protects that manifest. Nothing stops someone
from deploying a *different* pod that runs as root. [Kyverno](https://kyverno.io)
closes that gap: it's a Kubernetes admission controller that evaluates every pod
against policy **before it is created**, and rejects anything non-compliant.

This is the Kubernetes equivalent of an AWS Service Control Policy — a
**preventive guardrail** that enforces the rule in one place instead of relying
on every author to remember it.

`policies/require-pod-hardening.yaml` rejects any pod that is not non-root, that
allows privilege escalation, or that does not drop all Linux capabilities.

```bash
# Install Kyverno, then apply the policy
kubectl create -f https://github.com/kyverno/kyverno/releases/download/v1.13.4/install.yaml
kubectl apply -f policies/require-pod-hardening.yaml

# Proof: an un-hardened pod is rejected at admission time
kubectl run bad --image=nginx --dry-run=server
# -> blocked: "Pods must run as non-root ... allowPrivilegeEscalation ... drop ALL"

# The hardened Deployment passes the same policy.
```

> Note: in production, Kyverno itself is a privileged, trusted component (it can
> see and gate every resource). It would be subject to the same RBAC review,
> pod hardening, and patching as any other workload — the security tooling is
> part of the attack surface.

---

## CI security gates (DevSecOps / shift-left)

`.github/workflows/security.yml` runs automated security checks on every push and
pull request, so problems are caught at commit time rather than in production.
Each gate targets one of the most common real-world attack vectors:

| Gate | Tool | Defends against |
|------|------|-----------------|
| Dependency / CVE scan | Trivy (fs) | Vulnerable components (K02/K10) |
| Secrets scan | Gitleaks | Leaked credentials (K08) — the #1 breach vector |
| Manifest / IaC scan | Trivy (config) | Insecure workload config (K01) |
| Policy check | Kyverno CLI | Manifests validated against our own guardrails (K01/K04) |

The workflow uses least-privilege permissions (`contents: read`) and fails the
build on HIGH/CRITICAL findings, which can gate merges via branch protection.

---

## Vulnerability scan (Trivy)

[Trivy](https://github.com/aquasecurity/trivy) scans the image for known CVEs in
OS packages and language dependencies.

```bash
# Scan the built image and write JSON
trivy image --format json --output scan.json k8s-security-api

# Human-readable table, high/critical only
trivy image --severity HIGH,CRITICAL k8s-security-api
```

### Results summary (from `scan.json`)

Base image: **Debian 13.7** · Artifact: `k8s-security-api`

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 46 |
| MEDIUM | 56 |
| LOW | 59 |
| UNKNOWN | 2 |
| **Total** | **163** |

### Triage notes

- **Zero criticals** on the hardened image.
- Most **HIGH** findings are in base OS libraries (e.g. `bsdutils`, `libblkid1`,
  `libacl1`) and currently have **no fixed version available upstream** — meaning
  they cannot be patched by rebuilding yet. This is a realistic situation:
  vulnerability management is as much about *tracking and accepting* unfixable
  findings as it is about patching.
- The practical mitigations here are **running as non-root** and keeping the base
  image current, which reduce exploitability even where a package fix isn't yet
  published.
- A further reduction would be switching to a smaller base (e.g. a distroless or
  Alpine image), which removes many of these OS packages entirely.

> `scan.json` is a generated artifact and is git-ignored. Regenerate it with the
> Trivy command above.

---

## Roadmap / what I'm learning next

Honest list of what this lab does **not** yet do, mapped to the OWASP Kubernetes
Top 10 risk each item closes. This is my active study plan:

- [x] Pod `securityContext`: `runAsNonRoot`, `readOnlyRootFilesystem`,
      `allowPrivilegeEscalation: false`, drop all Linux capabilities — *(K01)*
- [x] CPU/memory resource `requests` and `limits` — *(K01)*
- [x] Liveness/readiness probes wired to `/health` — *(K01)*
- [x] `NetworkPolicy` (default-deny, then allow only required traffic) — *(K07)*
- [x] Admission-control enforcement (Kyverno) for cluster-wide guardrails — *(K04)*
- [x] CI pipeline running Trivy + Gitleaks + policy checks on every push — *(K02, K08)*
- [ ] Pod Security Standards as a second enforcement layer alongside Kyverno — *(K04)*
- [ ] Proper Kubernetes `Secret` handling (no secrets in image or env) — *(K08)*
- [ ] Audit logging and runtime monitoring — *(K05)*
- [ ] Smaller/distroless base image to cut the OS CVE surface — *(K02, K10)*

---

## Project layout

```
k8s-security-lab/
├── Dockerfile          # hardened image build
├── app/
│   └── app.py          # minimal Flask API (/ and /health)
├── k8s/
│   ├── deployment.yaml # Deployment, 2 replicas
│   ├── service.yaml    # NodePort service, 80 -> 5000
│   ├── rbac.yaml       # read-only Role (least privilege)
│   ├── rolebinding.yaml# binds Role to security-auditor
│   └── networkpolicy.yaml # default-deny + explicit allow (segmentation)
├── policies/
│   └── require-pod-hardening.yaml # Kyverno admission guardrail (K04)
└── scan.json           # Trivy scan output (generated, git-ignored)

# repo root also contains:
#   .github/workflows/security.yml  # CI security gates (Trivy, Gitleaks, Kyverno)
```
