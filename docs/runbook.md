# Runbook

Operational procedures for **notes-api** on **k3s (Hetzner VPS)**. Assume `kubectl` is configured for the target k3s cluster.

---

## Prerequisites

- `kubectl` context pointing to the k3s cluster.
- Docker (optional, for local builds / debugging). Phase 2 images are built and pushed by GitHub Actions to GHCR; Phase 1 manual import is legacy (see §2).
- For ServiceMonitor: Prometheus Operator (or compatible) installed with selector matching `release: monitoring`.

---

## Golden commands

```bash
# Check current image and rollout
kubectl get deployment notes-api -n ai-platform -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl get pods -n ai-platform -l app=notes-api -o jsonpath='{..image}{"\n"}'

# Deploy (after updating image tag to desired SHA in k8s/deployment.yaml)
kubectl apply -k k8s/

# Check basic health
kubectl get pods -n ai-platform -l app=notes-api
curl -s -H "Host: api.89.167.103.77.sslip.io" http://<VPS-IP>/health

# Rollback
kubectl rollout undo deployment/notes-api -n ai-platform
kubectl rollout status deployment/notes-api -n ai-platform
kubectl get deployment notes-api -n ai-platform -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

---

## 1. Build the image

Phase 2 images are built and pushed automatically by GitHub Actions workflow `.github/workflows/build.yml`:

- Triggered on pushes to `main` or via `workflow_dispatch`.
- Builds the Dockerfile in the repo and pushes to `ghcr.io/olie-aglan-x/notes-api`.
- Tags include a SHA-based tag (e.g. `sha-ea0d59b`), branch-based tags, and `latest`.

**Optional (local debug only)**: you can still build an image locally:

```bash
docker build -t notes-api:local .
```

This is not used by the Phase 2 deployment to k3s.

---

## 2. Image supply (Phase 2 and legacy)

### Phase 2 (default) — GHCR pull

- Deployment `k8s/deployment.yaml` references a GHCR image such as `ghcr.io/olie-aglan-x/notes-api:sha-ea0d59b` with `imagePullPolicy: IfNotPresent`.
- Ensure the desired commit has a built image in GHCR (GitHub Actions run for that commit on `main` should be green).
- Update the image tag in `k8s/deployment.yaml` to the desired SHA tag.
- Apply manifests with `kubectl apply -k k8s/` (see §3).

### Phase 1 legacy — manual tar import to k3s

The legacy flow uses a locally built `notes-api:local` image and imports it into k3s:

- The manifest referenced `notes-api:local` with `imagePullPolicy: Never`.
- To reproduce this path:

  **Option A — k3s ctr import (from dev machine):**

  ```bash
  docker build -t notes-api:local .
  docker save notes-api:local | ssh <k3s-node> 'sudo k3s ctr images import -'
  ```

  Replace `<k3s-node>` with your Hetzner VPS host (SSH config alias or IP). If kubectl uses a different user/host, use the same SSH target as for the node where the pod runs.

  **Option B — On the VPS directly:**

  ```bash
  # On the VPS (after copying image tar or building there):
  sudo k3s ctr images import notes-api-local.tar
  ```

Use this legacy flow only if GHCR is temporarily unavailable or for one-off debugging.

---

## 3. Deploy / apply manifests

From repository root:

```bash
kubectl apply -k k8s/
```

This applies (in order implied by Kustomize): namespace `ai-platform`, Deployment, Service, Ingress, ServiceMonitor.

To preview:

```bash
kubectl kustomize k8s/
kubectl apply -k k8s/ --dry-run=client -o yaml
```

---

## 4. Verify deployment

- **Pods:**
  ```bash
  kubectl get pods -n ai-platform -l app=notes-api
  ```
  Expect `Running` and `1/1` Ready.

- **Service:**
  ```bash
  kubectl get svc -n ai-platform notes-api
  ```

- **Endpoints:**
  ```bash
  kubectl get endpoints -n ai-platform notes-api
  ```
  Should list the pod IP and port 8000.

- **Ingress:**
  ```bash
  kubectl get ingress -n ai-platform notes-api
  ```

- **Health from inside cluster:**
  ```bash
  kubectl run curl --rm -it --restart=Never --image=curlimages/curl -- curl -s http://notes-api.ai-platform.svc.cluster.local/health
  ```

- **From outside (Ingress is host-based):** Use the Ingress host in the `Host` header when calling by IP (e.g. VPS IP). Expect `{"status":"ok"}`.

  ```bash
  curl -s -H "Host: api.89.167.103.77.sslip.io" http://<VPS-IP>/health
  curl -s -H "Host: api.89.167.103.77.sslip.io" http://<VPS-IP>/metrics
  ```

  If DNS for `api.89.167.103.77.sslip.io` resolves to the VPS, you can also:

  ```bash
  curl -s http://api.89.167.103.77.sslip.io/health
  ```

- **Verify image running in pods:**

  ```bash
  kubectl get deployment notes-api -n ai-platform -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
  kubectl get pods -n ai-platform -l app=notes-api -o jsonpath='{..image}{"\n"}'
  ```

---

## 5. Rollback

If a new deployment is unhealthy:

```bash
kubectl rollout undo deployment/notes-api -n ai-platform
```

Check status:

```bash
kubectl rollout status deployment/notes-api -n ai-platform
```

To roll back to a specific revision:

```bash
kubectl rollout history deployment/notes-api -n ai-platform
kubectl rollout undo deployment/notes-api -n ai-platform --to-revision=<revision>
```

After any rollback, verify the image tag:

```bash
kubectl get deployment notes-api -n ai-platform -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl get pods -n ai-platform -l app=notes-api -o jsonpath='{..image}{"\n"}'
```

**Note**: Rollback reverts to a previous pod template (e.g. previous SHA image). You still need to ensure that the SHA tag in `k8s/deployment.yaml` matches the version you intend to run.

---

## 6. Restart the workload

To force a pod restart without changing manifest:

```bash
kubectl rollout restart deployment/notes-api -n ai-platform
kubectl rollout status deployment/notes-api -n ai-platform
```

---

## 7. Scaling (current manifest)

Replicas are fixed at 1 in `k8s/deployment.yaml`. To scale manually:

```bash
kubectl scale deployment/notes-api -n ai-platform --replicas=2
```

To make it permanent, edit `k8s/deployment.yaml` (`spec.replicas`) and re-apply with `kubectl apply -k k8s/`.

---

## 8. View logs

```bash
kubectl logs -n ai-platform -l app=notes-api -f --tail=100
```

For a specific pod:

```bash
kubectl logs -n ai-platform <pod-name> -f
```

Previous (crashed) container:

```bash
kubectl logs -n ai-platform <pod-name> -p
```

---

## 9. Troubleshooting

| Symptom | Checks |
|--------|--------|
| Pod not starting | `kubectl describe pod -n ai-platform -l app=notes-api`: ImagePullBackOff → image not on node or pull misconfigured; CrashLoopBackOff → check `kubectl logs` and events. |
| Pod not Ready | Readiness uses `/health`. Check `kubectl logs` and `curl` to `/health` from inside the pod or cluster. |
| 502 / no route | Ingress and Traefik: `kubectl get ingress`, check Traefik logs. Confirm Service has endpoints: `kubectl get endpoints notes-api -n ai-platform`. |
| No metrics in Prometheus | Confirm ServiceMonitor: `kubectl get servicemonitor -n ai-platform`. Ensure Prometheus Operator is installed and selects `release: monitoring`. Check Prometheus scrape config and targets. |
| High memory/CPU | Check `kubectl top pod -n ai-platform -l app=notes-api`. Current limits: 256Mi memory, 500m CPU. Adjust in `k8s/deployment.yaml` if needed. |

**Debug inside pod:**
```bash
kubectl exec -n ai-platform -it deployment/notes-api -- sh
# or run curl from another pod in the cluster to http://notes-api:80/health
```

---

## 10. Remove deployment

To remove all resources defined by Kustomize:

```bash
kubectl delete -k k8s/
```

This deletes the Deployment, Service, Ingress, ServiceMonitor, and (if empty) can leave the namespace. To delete the namespace explicitly:

```bash
kubectl delete namespace ai-platform
```

**Warning**: Deleting the namespace removes all resources in `ai-platform`, not only notes-api.
