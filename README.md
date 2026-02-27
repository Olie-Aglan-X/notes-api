# notes-api

Phase 1: FastAPI service deployed on k3s with Prometheus monitoring.

## Architecture Summary

- Infrastructure: Hetzner Cloud VPS (8 vCPU / 16GB RAM)
- Cluster: single-node k3s
- Ingress: Traefik (default k3s)
- Monitoring: kube-prometheus-stack (Prometheus + Grafana)
- Packaging: Kustomize (`kubectl apply -k k8s/`)
- Deployment model: GHCR + GitHub Actions (Phase 2; Phase 1 manual image import is legacy)

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

### Deploy to k8s (k3s)

**Phase 1 legacy (manual image import):** Image must be present on the node. On the k3s node (or where the k3s containerd/docker runs), import the image, e.g.:

```bash
# From your dev machine: save and copy to node, then on the node:
docker save notes-api:local | ssh <k3s-node> 'sudo k3s ctr images import -'
# Or if k3s node uses docker: docker save notes-api:local | ssh <node> docker load
```

1. Ensure the image is imported on the node(s) that will run the workload (see above).
2. From repo root:
   ```bash
   kubectl apply -k k8s/
   ```
3. Check: `kubectl get pods -n ai-platform -l app=notes-api`

## Deployment model

**Phase 2 (current)**

- Container images are built and pushed by GitHub Actions workflow `.github/workflows/build.yml` to GHCR `ghcr.io/olie-aglan-x/notes-api`.
- Kubernetes Deployment (`k8s/deployment.yaml`) pulls an immutable SHA tag (for example `ghcr.io/olie-aglan-x/notes-api:sha-ea0d59b`) with `imagePullPolicy: IfNotPresent`.
- Releases are performed by updating the image tag in `k8s/deployment.yaml` to the desired SHA and applying `kubectl apply -k k8s/`.

**Phase 1 legacy (manual tar import)**

- Image was built locally as `notes-api:local`.
- Image was manually imported into the k3s container runtime via `docker save | k3s ctr images import`.
- Deployment used `notes-api:local` with `imagePullPolicy: Never`.

Phase 1 is kept in the documentation as a fallback path only; Phase 2 (GHCR + SHA tags) is the default.

## Repository layout

| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI app: health, metrics, placeholders for ingest/search |
| `k8s/*.yaml` | Kubernetes manifests (namespace, deployment, service, ingress, ServiceMonitor) |
| `k8s/kustomization.yaml` | Kustomize resource list |
| `Dockerfile` | Single stage, non-root user |
| `requirements.txt` | Python dependencies (FastAPI, Uvicorn, prometheus-client) |
| `docs/` | Architecture, runbook, decisions |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness/readiness; returns `{"status":"ok"}` |
| GET | `/metrics` | Prometheus exposition format |
| GET | `/ingest` | Placeholder |
| GET | `/search` | Placeholder |

`/ingest` and `/search` are placeholders in Phase 1. No persistence, indexing, or external storage is implemented.

## Phase 1 limitations / risks

- **Single node**: No HA; node failure causes full outage.
- **Manual deploy**: No CD; `kubectl apply -k k8s/` and image tag changes are manual (even though images are built and pushed by CI).
- **Image pinning**: Deployment uses a GHCR image pinned to a specific SHA; rolling forward/rollback requires updating manifests to the correct SHA.
- **No automated tests or rollback** in pipeline.

See [docs/architecture.md](docs/architecture.md) and [docs/decisions.md](docs/decisions.md) for full limitations and production risks.

## Next steps

- Read [docs/architecture.md](docs/architecture.md) for infrastructure and observability.
- Use [docs/runbook.md](docs/runbook.md) for deploy, rollback, and troubleshooting.
- Review [docs/decisions.md](docs/decisions.md) for design choices and tradeoffs.
