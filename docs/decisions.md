# Architectural decisions and tradeoffs

Record of decisions reflected in the **notes-api** repository and their tradeoffs. Inferred from current code and manifests only.

---

## 1. FastAPI + Uvicorn

**Decision**: Application is a single FastAPI app served by Uvicorn (single process, no workers).

**Tradeoffs**:
- **Pros**: Simple, fast to develop; async support; automatic OpenAPI; low footprint for Phase 1.
- **Cons**: Single process; no multi-worker concurrency. Under load, one replica may become a bottleneck; scaling is horizontal only (more pods).

---

## 2. Single replica Deployment

**Decision**: Deployment runs with `replicas: 1`.

**Tradeoffs**:
- **Pros**: Minimal resource use; no need for session affinity or shared state; simpler for early phase.
- **Cons**: No high availability. Pod or node failure causes full service outage until Kubernetes reschedules the pod. No load spreading.

**Production risk**: Any single failure leads to downtime. Increase replicas and validate stateless behavior before production.

---

## 3. Image `notes-api:local` and `imagePullPolicy: Never`

**Decision**: Deployment uses a local image name and never pulls from a registry.

**Status**: Legacy (Phase 1 only); superseded by Decision 13 (GHCR + immutable SHA tags).

**Tradeoffs**:
- **Pros**: Works with local or on-node images; no registry or pull-secrets setup for dev/k3s.
- **Cons**: Not standard for production. Image supply is manual (load onto node or push to registry and change manifest). Tag `:local` is not versioned; rollbacks are ambiguous.

**Production risk**: Must move to a versioned image and a pull policy (or registry) that matches your release process.

---

## 4. Namespace `ai-platform`

**Decision**: All resources are in the shared namespace `ai-platform`.

**Tradeoffs**:
- **Pros**: Single namespace to manage; simple RBAC and visibility.
- **Cons**: No isolation from other workloads in the same namespace; naming and quotas are shared. Not multi-tenant.

---

## 5. Traefik Ingress, single host

**Decision**: Ingress uses `ingressClassName: traefik` and one host: `api.89.167.103.77.sslip.io`.

**Tradeoffs**:
- **Pros**: Fits k3s default Traefik; sslip.io gives a quick hostname for an IP.
- **Cons**: Host is hardcoded and IP-specific; no TLS in the manifest; not portable across environments.

**Production risk**: Add TLS (e.g. Ingress TLS or cert-manager) and use a stable hostname; avoid committing production hostnames/IPs if policy requires.

---

## 6. No TLS in Ingress

**Decision**: Ingress has no `tls` section; traffic is HTTP only at the manifest level.

**Tradeoffs**:
- **Pros**: No certificate management in repo; quick for dev.
- **Cons**: Traffic to the app is not encrypted by this config. TLS may be terminated elsewhere (e.g. LB or Traefik default) but is not documented in repo.

**Production risk**: Ensure TLS is enabled (here or upstream) and document where it is configured.

---

## 7. Kustomize (no Helm)

**Decision**: Manifests are plain YAML with a single `kustomization.yaml`; no Helm chart.

**Tradeoffs**:
- **Pros**: No Helm dependency; easy to read and edit; `kubectl apply -k` is enough; good for a single app.
- **Cons**: No templating or versioned package; multi-environment or parameterized values require overlays or external tooling.

---

## 8. Prometheus metrics and ServiceMonitor

**Decision**: App exposes `/metrics` (Prometheus format) and a ServiceMonitor targets it with label `release: monitoring`.

**Tradeoffs**:
- **Pros**: Standard Prometheus integration; one custom metric (`http_requests_total`); works with Prometheus Operator.
- **Cons**: ServiceMonitor only has effect if Prometheus Operator (or equivalent) is installed and selects that label. No alerts or dashboards in repo.

**Production risk**: If the cluster has no Operator or different label, metrics are not scraped; add alerts and SLOs when moving to production.

---

## 9. Health checks on `/health` only

**Decision**: Readiness and liveness both use `GET /health` on port 8000.

**Tradeoffs**:
- **Pros**: One endpoint; simple; no dependency checks in app.
- **Cons**: Liveness and readiness are identical; a failing dependency (e.g. future DB) would not be reflected. No distinction between “alive” and “ready to serve”.

---

## 10. Non-root container user

**Decision**: Dockerfile creates `appuser` and runs the process as that user.

**Tradeoffs**:
- **Pros**: Reduces impact of container compromise; good practice for production.
- **Cons**: None significant for this app.

---

## 11. No ConfigMap/Secrets in Deployment

**Decision**: No environment variables, ConfigMaps, or Secrets are mounted or referenced in the Deployment.

**Tradeoffs**:
- **Pros**: No secrets in repo; app is currently stateless with no config.
- **Cons**: When config or credentials are needed (e.g. DB URL, API keys), they must be added via ConfigMap/Secret and wired into the Deployment.

---

## 12. Ingest and search as placeholders

**Decision**: `/ingest` and `/search` return fixed placeholder responses; no storage or logic.

**Tradeoffs**:
- **Pros**: API shape and routing can be tested; no DB or external services to run.
- **Cons**: No real functionality; production will require storage, auth, and error handling.

---

## Summary table

| Area           | Decision              | Main tradeoff / risk                          |
|----------------|------------------------|-----------------------------------------------|
| App runtime    | FastAPI + Uvicorn      | Single process; scale via more pods           |
| Replicas       | 1                      | No HA; single point of failure                |
| Image          | GHCR, SHA tags         | Pinned to SHA; manual manifest bump; GHCR dependency |
| Namespace      | ai-platform            | Shared; no isolation                          |
| Ingress        | Traefik, one host      | Hardcoded host; no TLS in repo                 |
| GitOps/apply   | ArgoCD + Kustomize     | Git = source of truth; ArgoCD sync, self-heal, prune |
| Observability  | ServiceMonitor         | Depends on Prometheus Operator                |
| Health         | Single /health         | No separate liveness vs dependency readiness  |
| Security       | Non-root, no auth      | Good base; no API auth                        |
| Config         | None                   | Add when adding dependencies                  |

These decisions are suitable for Phase 1 / dev; production will require addressing the risks above (replicas, image strategy, TLS, auth, observability, and real ingest/search implementation).

---

## 13. GHCR + immutable SHA image tags

**Decision**: Container images are built and pushed by GitHub Actions workflow `.github/workflows/build.yml` to GitHub Container Registry `ghcr.io/olie-aglan-x/notes-api`, using SHA-based tags (e.g. `sha-ea0d59b`). The Kubernetes Deployment is configured to pull a specific SHA tag.

**Tradeoffs**:
- **Pros**: Immutable tags tie each running image directly to a Git commit; easy to audit which commit is running; rollbacks can target a known SHA; works well with automated builds.
- **Cons**: Rolling forward or back requires updating the image tag in `k8s/deployment.yaml`; if manifests are not updated correctly, the cluster may continue running an unintended version; runtime depends on GHCR availability.

**Production risk**: Tag/manifest drift between GHCR and `k8s/deployment.yaml` can lead to confusion about which version is actually deployed; changes to GHCR availability or permissions will impact the ability to roll out new versions.

---

## 14. Adopt GitOps with ArgoCD

**Decision**: Deployment to the cluster is GitOps-managed by ArgoCD. This repo is the source of truth for `k8s/`; ArgoCD (configured elsewhere to watch this repo) applies manifests with auto-sync, self-heal, and prune. The promote workflow (`.github/workflows/promote.yml`) updates `k8s/deployment.yaml` with the new image SHA after each successful build and pushes to git; no manual `kubectl apply` for normal releases.

**Tradeoffs**:
- **Pros**: Git is the single source of truth; audit trail for changes; ArgoCD keeps cluster aligned with git (auto-sync, self-heal, prune); rollback is git revert + sync; no need to run `kubectl apply` from a laptop.
- **Cons**: ArgoCD must be installed and configured (outside this repo); operators need to understand GitOps flow; sync failures or RBAC misconfiguration can block deploys; manual apply is only a fallback.

**Production risk**: If ArgoCD is down or the Application is misconfigured, releases block until fixed; ensure ArgoCD and repo access are operational and documented.
