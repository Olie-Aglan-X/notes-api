# notes-api

Phase 1: FastAPI service deployed on k3s with Prometheus monitoring.

## Architecture Summary

- Infrastructure: Hetzner Cloud VPS (8 vCPU / 16GB RAM)
- Cluster: single-node k3s
- Ingress: Traefik (default k3s)
- Monitoring: kube-prometheus-stack (Prometheus + Grafana)
- Packaging: Kustomize (`kubectl apply -k k8s/`)
- Deployment model: manual image import (Phase 1)

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

The cluster is configured to use `notes-api:local` with `imagePullPolicy: Never` (image must be available on the node).

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

## Deployment Model (Phase 1)

- Image is built locally as `notes-api:local`
- Image is manually imported into k3s container runtime
- `imagePullPolicy: Never` is used
- No CI/CD or registry integration yet

This will be replaced in Phase 2 by:
- GHCR-based image registry
- Automated build pipeline
- Versioned image tags

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
- **Manual deploy**: No CI/CD; build, image import, and `kubectl apply` are manual.
- **Local image**: `notes-api:local` and `imagePullPolicy: Never` require importing the image on the node (no registry pull).
- **No automated tests or rollback** in pipeline.

See [docs/architecture.md](docs/architecture.md) and [docs/decisions.md](docs/decisions.md) for full limitations and production risks.

## Next steps

- Read [docs/architecture.md](docs/architecture.md) for infrastructure and observability.
- Use [docs/runbook.md](docs/runbook.md) for deploy, rollback, and troubleshooting.
- Review [docs/decisions.md](docs/decisions.md) for design choices and tradeoffs.
