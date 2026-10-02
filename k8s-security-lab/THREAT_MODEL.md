# Threat Model — k8s-security-lab

A threat model answers four questions: **what are we protecting, from whom,
with which controls, and where are the gaps?** This document records the
security reasoning behind the lab — not just *what* controls exist, but *why*,
and honestly, what is still exposed.

> Scope note: this is a single-service learning lab, not a production system.
> The point is to demonstrate the reasoning a security engineer applies, and to
> be explicit about what is intentionally out of scope.

---

## 1. What we're protecting (assets)

| Asset | Why it matters |
|-------|----------------|
| The Flask API workload | The running service; its availability and integrity |
| The container/pod runtime | A compromised pod is an attacker's foothold |
| The cluster (nodes, API server) | Pod compromise should not become cluster compromise |
| The CI pipeline & policies | Privileged, trusted components (see §5) |

---

## 2. Trust boundaries

A trust boundary is where data or control crosses from one level of trust to
another — the places worth scrutinizing.

```
Internet ──[B1]──> Service (NodePort) ──[B2]──> Pod / Flask app
                                                   │
Developer ──[B3]──> Git / CI ──> image + manifests │
                                                   │
                   Kubernetes API server ──[B4]──> cluster resources
                        │
                        └── admission control (Kyverno) ──[B5]
```

- **B1 — Internet → Service:** untrusted external traffic enters here.
- **B2 — Service → Pod:** traffic reaches the workload; the app must treat input as untrusted.
- **B3 — Developer → Git/CI:** code and config enter the system; supply-chain trust boundary.
- **B4 — Client → API server:** who can change the cluster (authn + RBAC).
- **B5 — Admission control:** what resources are *allowed to exist* (Kyverno).

---

## 3. Threats (STRIDE) and controls

STRIDE = Spoofing, Tampering, Repudiation, Information disclosure, Denial of
service, Elevation of privilege.

| Threat | Example in this system | Control in place | Residual gap |
|--------|------------------------|------------------|--------------|
| **S**poofing | Caller pretends to be an authorized cluster user | RBAC (`security-reader` least-privilege Role) | App itself has no authn (out of scope, §4) |
| **T**ampering | Attacker modifies the running container (drops a binary/webshell) | `readOnlyRootFilesystem`, image scanning in CI | Base-image CVEs without upstream fixes remain |
| **R**epudiation | Action taken with no record | Falco runtime detection rules written (shell/sensitive-file/pkg-tool in app container) | Live capture pending a supported-kernel cluster; audit logging still to add (K05) |
| **I**nfo disclosure | Secrets leaked via image, git, or logs | No secrets in image; Gitleaks in CI | Full Secret management not implemented (K08) |
| **D**enial of service | Pod exhausts node CPU/memory | Resource `requests`/`limits` | No cluster-wide quota; single app only |
| **E**levation of privilege | Container escape → host/cluster | Non-root, drop ALL caps, `allowPrivilegeEscalation: false`, seccomp `RuntimeDefault`; Kyverno enforces these cluster-wide | Kernel 0-days; Kyverno itself is privileged (§5) |

The elevation-of-privilege row is the heart of the lab: **defense in depth.** An
attacker who compromises the app must still defeat several independent controls
(no root powers, no writable fs, no dangerous syscalls, no way to escalate) to
escape — and even then, no un-hardened pod can be deployed as a pivot because
Kyverno rejects it.

---

## 4. Explicitly out of scope (and why)

Naming what you are *not* defending is part of a threat model. Pretending
everything is covered is dishonest and hides risk.

- **Application-layer auth / authorization (OWASP web A01/A07).** This is a
  single-user demo; adding auth would be security theater here. In a
  multi-user or internet-facing deployment, these endpoints would require
  authentication and per-object authorization. *Decision recorded, not forgotten.*
- **Cluster component hardening (K09).** Using a local/managed cluster; API
  server, etcd encryption, and node hardening are the platform's responsibility.
- **The application's own code vulnerabilities.** Container hardening does not
  fix a SQL injection or SSRF *inside* the app — that is a separate layer
  (the web OWASP Top 10) and a separate lab.

---

## 5. Security of the security tooling

The tools that enforce security are themselves high-value, privileged targets —
and are often overlooked.

- **Kyverno** sees and gates every resource in the cluster. If compromised, an
  attacker could disable policies or inject malicious mutations into every pod.
  In production it needs its own RBAC review, pod hardening, a deliberate
  webhook failure-policy choice (fail-closed vs fail-open), and patching.
- **The CI pipeline** builds images and holds credentials. A compromised
  pipeline can ship malicious artifacts straight to production. It runs with
  least-privilege permissions (`contents: read`) for this reason.

The principle: **the most privileged, most trusted components deserve the
tightest controls**, because compromising one grants reach into everything it
touches. (Same logic as reducing IAM blast radius.)

---

## 6. Attacker's-eye summary

How a real attacker would approach this, and what stops them:

1. **Get in** — most breaches start with stolen credentials, not exploits.
   *Mitigation:* least-privilege RBAC limits what any single identity can do;
   Gitleaks keeps credentials out of the repo.
2. **Execute / persist** — drop a tool in the container.
   *Mitigation:* read-only filesystem, dropped capabilities, non-root.
3. **Escalate** — gain more privilege than granted.
   *Mitigation:* `allowPrivilegeEscalation: false`, seccomp, no capabilities.
4. **Move laterally** — pivot to other pods or the cluster.
   *Mitigation:* default-deny NetworkPolicy; Kyverno blocks deploying a
   privileged pivot pod.
5. **Act undetected** — partially addressed.
   *Mitigation:* Falco runtime detection rules written to catch shells, sensitive
   file reads, and runtime tooling inside the app container (K05). Live capture
   needs a supported-kernel cluster; audit logging still to add. **Assume breach;
   you must be able to see it.**

The honest takeaway: this lab significantly reduces the container/orchestration
attack surface, but no system has zero risk. Security is a posture, not a finish
line — the goal is to raise attacker cost and shrink blast radius at every layer.
