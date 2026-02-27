# notes-api

Phase 2: FastAPI service on k3s with GHCR images and ArgoCD GitOps.

## Architecture Summary

- Infrastructure: Hetzner Cloud VPS (8 vCPU / 16GB RAM)
- Cluster: single-node k3s
- Ingress: Traefik (default k3s)
- Monitoring: kube-prometheus-stack (Prometheus + Grafana)
- Packaging: Kustomize (`k8s/`); applied by ArgoCD (auto-sync, self-heal, prune)
- Deployment model: GHCR + immutable SHA tags; GitOps via ArgoCD (this repo = source of truth). Phase 1 manual image import is legacy.

## For new engineers

- **Codebase**: Single FastAPI app in `app/main.py`; Kubernetes manifests in `k8s/`.
- **Docs**: See [docs/architecture.md](docs/architecture.md), [docs/runbook.md](docs/runbook.md), and [docs/decisions.md](docs/decisions.md).
- **Runtime**: Python 3.11, Uvicorn on port 8000. No database or external services in current scope.

## Prerequisites

- Python 3.11+
- Docker (for building the image)
- Access to a k3s cluster with Traefik ingress and (optionally) Prometheus Operator for ServiceMonitor

## Quick start

### Local run

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/health  
- Metrics: http://localhost:8000/metrics  

### Build image

```bash
docker build -t notes-api:local .
```

The Phase 2 deployment uses images built and pushed by GitHub Actions to `ghcr.io/olie-aglan-x/notes-api` (including SHA-based tags). The local build is for debugging and legacy/manual flows only.

### Deploy to k8s (Phase 2 — GitOps)

Releases are driven by git: push to `main` (app or docs changes) triggers CI build → promote workflow updates `k8s/deployment.yaml` with the new SHA and pushes → ArgoCD syncs the cluster. No manual `kubectl apply` for normal releases. See [How to release](#how-to-release) below.

**Phase 1 legacy (manual image import):** Only if not using ArgoCD/GHCR: build locally, import image on the node (`docker save notes-api:local | ssh <k3s-node> 'sudo k3s ctr images import -'`), then `kubectl apply -k k8s/`. See [docs/runbook.md](docs/runbook.md) §2.

## How to release

1. **Commit** — Merge or push to `main` (app code; build workflow ignores `k8s/**`, `docs/**`, `README.md`).
2. **CI build** — `.github/workflows/build.yml` runs, builds image, pushes to `ghcr.io/olie-aglan-x/notes-api` with tag `sha-<commit>`.
3. **Promote** — `.github/workflows/promote.yml` runs after a successful build: updates `k8s/deployment.yaml` with the new image SHA, commits and pushes (message `GitOps: promote image ... [skip ci]`).
4. **ArgoCD sync** — ArgoCD (configured to use this repo as source) detects the change and applies manifests; auto-sync, self-heal, and prune keep the cluster in sync with git.

To roll back: revert the promote commit (or set image back to a previous SHA in `k8s/deployment.yaml`) and push; ArgoCD will sync to the reverted state.

## Deployment model

**Phase 2 (current)**

- **Build/push**: GitHub Actions `.github/workflows/build.yml` builds and pushes images to GHCR `ghcr.io/olie-aglan-x/notes-api` with immutable SHA tags (e.g. `sha-ea0d59b`).
- **Promote**: Workflow `.github/workflows/promote.yml` (runs after successful build) updates `k8s/deployment.yaml` with the new SHA and pushes to the repo.
- **Apply**: ArgoCD watches this repo and applies `k8s/` (Kustomize). Manual `kubectl apply -k k8s/` is not the primary mechanism; use git + ArgoCD sync for releases.

**Phase 1 legacy (manual tar import)**

- Image built locally as `notes-api:local`, manually imported via `docker save | k3s ctr images import`; Deployment used `notes-api:local` and `imagePullPolicy: Never`. Kept as fallback only.

## Repository layout

| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI app: health, metrics, placeholders for ingest/search |
| `k8s/*.yaml` | Kubernetes manifests (namespace, deployment, service, ingress, ServiceMonitor) |
| `k8s/kustomization.yaml` | Kustomize resource list |
| `Dockerfile` | Single stage, non-root user |
| `requirements.txt` | Python dependencies (FastAPI, Uvicorn, prometheus-client) |
| `.github/workflows/build.yml` | CI: build and push image to GHCR (SHA tags) |
| `.github/workflows/promote.yml` | CD: update `k8s/deployment.yaml` with new SHA and push (GitOps) |
| `docs/` | Architecture, runbook, decisions |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness/readiness; returns `{"status":"ok"}` |
| GET | `/metrics` | Prometheus exposition format |
| GET | `/ingest` | Placeholder |
| GET | `/search` | Placeholder |

`/ingest` and `/search` are placeholders in Phase 1. No persistence, indexing, or external storage is implemented.

## Phase 2 limitations / risks

- **Single node**: No HA; node failure causes full outage.
- **GitOps dependency**: ArgoCD must be configured to track this repo; sync and permissions are outside this repo.
- **Image pinning**: Deployment uses a GHCR image pinned to a specific SHA; promote workflow updates it on each successful build; rollback is via git revert (or manual manifest edit) and ArgoCD sync.
- **No automated tests** in pipeline before deploy.

See [docs/architecture.md](docs/architecture.md) and [docs/decisions.md](docs/decisions.md) for full limitations and production risks.

## Next steps

- Read [docs/architecture.md](docs/architecture.md) for infrastructure and observability.
- Use [docs/runbook.md](docs/runbook.md) for deploy, rollback, and troubleshooting.
- Review [docs/decisions.md](docs/decisions.md) for design choices and tradeoffs.
