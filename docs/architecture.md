# Architecture

This document describes the current architecture of **notes-api** based on the repository only. No external or planned components are assumed.

---

## Infrastructure layer

- **Orchestration**: Kubernetes (k3s). All resources live in namespace `ai-platform`.
- **Compute**: Single Deployment `notes-api` with one replica. Pods run the app container (port 8000).
- **Networking**:
  - **Service** `notes-api`: ClusterIP (default), port 80 → targetPort 8000, selector `app: notes-api`.
  - **Ingress** `notes-api`: IngressClassName `traefik`; single rule `host: api.89.167.103.77.sslip.io`, path `/` → Service port 80. No TLS block is defined in the manifest.
- **Image**: Deployment uses `notes-api:local` with `imagePullPolicy: Never`, so the image is expected to be present on the node (e.g. loaded locally or pre-pulled), not from a remote registry.

**Production risks (infrastructure)**:
- Single replica: no high availability; node or pod failure causes full outage until reschedule.
- Hardcoded Ingress host (IP in hostname) and no TLS: not suitable for production without changing host and adding TLS.
- `imagePullPolicy: Never` and tag `:local`: deployment assumes a specific image supply process (e.g. load onto node); any other workflow requires changing the deployment.

---

## Application layer

- **Stack**: Python 3.11, FastAPI, Uvicorn. Single module `app/main.py`.
- **Process**: Uvicorn runs `app.main:app` bound to `0.0.0.0:8000`. No environment-based config files in the repo.
- **Endpoints**:
  - `GET /health` — returns `{"status":"ok"}`. Used by Kubernetes readiness and liveness probes.
  - `GET /metrics` — Prometheus exposition format (includes `http_requests_total` and default process metrics).
  - `GET /ingest`, `GET /search` — placeholders only; no storage or business logic.
- **Middleware**: One HTTP middleware that increments a Prometheus counter `http_requests_total` with labels `method` and `endpoint` (using `request.url.path`).
- **Security**: Container runs as non-root user (`appuser`). No authentication, rate limiting, or CORS configuration in code. No database or external clients in current scope.

**Production risks (application)**:
- No authentication or authorization on any endpoint.
- No persistence: ingest/search are stubs; no database or backing store.
- No explicit CORS or security headers; reliance on default FastAPI behavior.

---

## Observability

- **Health**: `/health` used for both readiness and liveness (interval 5s / 10s in Deployment).
- **Metrics**: Prometheus format on `/metrics`. One custom metric: `http_requests_total{method, endpoint}`. No RED/golden signals for latency or errors beyond what the client may expose.
- **Scraping**: A **ServiceMonitor** (Prometheus Operator) is defined for `notes-api` in namespace `ai-platform`, label `release: monitoring`, scraping the Service port named `http` at path `/metrics` every 15s. This only works if a Prometheus instance is installed and selects ServiceMonitors with that label (e.g. Prometheus Operator `release: monitoring`).
- **Logging**: No structured logging or log level configuration in the repo; standard Uvicorn/FastAPI stdout logging only. No log aggregation or retention defined in the repo.

**Production risks (observability)**:
- ServiceMonitor is a no-op if Prometheus Operator (or equivalent) is not installed or does not match `release: monitoring`.
- No alerting rules, dashboards, or SLOs defined in the repo.
- No distributed tracing or request IDs.

---

## Deployment model

- **Build**: Dockerfile builds a single-stage image; installs dependencies, copies `app/`, runs as non-root. No build args or multi-stage variant in repo.
- **Apply**: Manifests are applied with Kustomize: `kubectl apply -k k8s/`. Order is implied by Kustomize (namespace first, then workload and service, then ingress and ServiceMonitor). No overlays or env-specific patches in repo.
- **Rollout**: Standard Kubernetes Deployment; no canary or blue/green. Changing the image (e.g. tag) and re-applying triggers a rolling update. Rollback via `kubectl rollout undo deployment/notes-api -n ai-platform`.
- **Secrets/Config**: No ConfigMaps or Secrets referenced in the Deployment; no external config or credentials in repo.

**Production risks (deployment)**:
- No CI/CD or pipeline in repo; image build and push/load are manual.
- Image tag is fixed (`notes-api:local`); no versioned tags or change process documented in repo.
- No automated rollback or smoke tests after deploy.

---

## Known limitations

1. **Single replica** — no redundancy; pod or node failure causes downtime.
2. **No TLS on Ingress** — TLS must be added at ingress or LB for production.
3. **Hardcoded Ingress host** — `api.89.167.103.77.sslip.io` is environment-specific; other environments need host/path changes.
4. **Image supply** — `imagePullPolicy: Never` and `notes-api:local` assume image is loaded or available on the node; no registry flow in repo.
5. **No persistence** — ingest and search are placeholders; no database or storage.
6. **No auth** — all endpoints are unauthenticated.
7. **ServiceMonitor dependency** — metrics scraping depends on Prometheus Operator (or compatible) with matching `release: monitoring`.
8. **No structured logging or tracing** — only default Uvicorn/FastAPI logs; no request IDs or trace context.
9. **No resource tuning** — requests/limits (50m–500m CPU, 64Mi–256Mi memory) are fixed; not validated for production load.
10. **Shared namespace** — `ai-platform` is shared; multi-service naming and isolation are not documented.

These limitations should be addressed before treating the system as production-ready.
