# Week 1: Local Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Guided execution, chosen by the owner:** work through this in the main session, one step at a time. Claude explains and writes the setup files. The owner runs the commands and writes `collector/graph.py`. Do not start the next task until the owner has answered that task's "Explain back" questions in their own words.

**Goal:** Run Online Boutique, metrics, traces and Chaos Mesh on the laptop under load, and find out whether it all fits in memory.

**Architecture:** One `k3d` Kubernetes cluster inside Docker. The app runs in the `boutique` namespace with tracing on. Prometheus, the OpenTelemetry Collector and Jaeger run in `monitoring`, and Chaos Mesh in `chaos-mesh`. One script builds everything from nothing.

**Tech Stack:** k3d v5.9.0, kubectl with built-in Kustomize, Helm, Online Boutique v0.10.7, kube-prometheus-stack chart 92.17.0, opentelemetry-collector chart 0.178.1, Jaeger v2.22.0, Chaos Mesh v2.8.7, Python 3.12, uv, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-11-02-root-cause-gnn-design.md`

## Global Constraints

- Metrics are scraped every 5 seconds.
- The 10 possible root causes are: adservice, cartservice, checkoutservice, currencyservice, emailservice, frontend, paymentservice, productcatalogservice, recommendationservice, shippingservice.
- Every version above is pinned. Change a version only by editing it in one place and noting why in `docs/journal.md`.
- Everything is free this week. No AWS or LLM account is needed.
- Commands are for PowerShell, from the repository root.
- Secrets, raw run data and model checkpoints stay out of git.
- Commit after each task. Push only when the owner says to, because the repository is public.

## Review Focus

- Docker Desktop is not running when `up.ps1` starts: it stops with a clear message telling the owner to start Docker (Task 6, Step 6).
- `up.ps1` is run on a cluster that already exists: it updates in place and does not fail or make a duplicate (Task 6, Step 6).
- The laptop restarts: the cluster and all pods come back without a rebuild (Task 6, Step 7).
- A service sends no spans, which upstream's comments suggest for adservice: the gap is reported, not silently ignored (Task 5, `test_missing_services_reports_gap`).
- A trace is partial, with a parent span missing: graph building skips that link and does not crash (Task 5, `test_missing_parent_is_skipped`).

---

### Task 1: Tools and project basics

**Learn first:** what Docker, a container and an image are, and why a container is not a full virtual machine.

**Files:**
- Create: `.gitignore`, `docs/journal.md`, `infra/local/versions.ps1`

**Interfaces:**
- Produces: `infra/local/versions.ps1`, which sets `$K3dVersion`, `$BoutiqueVersion`, `$PromChartVersion`, `$OtelChartVersion`, `$JaegerVersion` and `$ChaosMeshVersion`.

- [ ] **Step 1: Start Docker Desktop and run a first container**

Run: `docker run --rm hello-world`
Expected: prints "Hello from Docker!"

- [ ] **Step 2: Record how much memory Docker can use**

Run: `docker info --format "{{.MemTotal}} {{.NCPU}}"`
Expected: a byte count and CPU count. Write both in `docs/journal.md`. Docker may see only part of the 16 GB, and that number matters in Task 6.

- [ ] **Step 3: Install Helm**

Run: `winget install --id Helm.Helm --exact`, then open a new terminal and run `helm version --short`.
Expected: prints a version.

- [ ] **Step 4: Install k3d v5.9.0**

Download `k3d-windows-amd64.exe` from the official `k3d-io/k3d` v5.9.0 GitHub release, compare it with the release's published checksum if one is provided, rename it `k3d.exe`, and put it in a folder on `PATH`.

Run: `k3d version`
Expected: `k3d version v5.9.0`. If Windows Smart App Control blocks it, stop and work through that with Claude. Do not turn off any security setting to get past it.

- [ ] **Step 5: Create the project basics**

`.gitignore` covers `.env`, `.venv/`, `__pycache__/`, `data/`, `*.pt` and `*.tfstate*`. `docs/journal.md` starts with a heading and the Step 2 numbers. `versions.ps1` holds the versions listed under Tech Stack.

- [ ] **Step 6: Explain back, then commit**

Explain back: what is the difference between an image and a container? Why does Docker's memory figure matter to this project?

```bash
git add .gitignore docs/journal.md infra/local/versions.ps1
git commit -m "chore: add project basics and pinned tool versions"
```

---

### Task 2: Cluster and shop app

**Learn first:** cluster, node, namespace, pod, deployment and service, using the shop as the example.

**Files:**
- Create: `infra/local/k3d-cluster.yaml`, `infra/local/boutique/kustomization.yaml`

**Interfaces:**
- Produces: cluster `rca` (kubectl context `k3d-rca`) with namespace `boutique`.

- [ ] **Step 1: Create the cluster**

`k3d-cluster.yaml`: name `rca`, 1 server, 0 agents, bundled Traefik disabled.

Run: `k3d cluster create --config infra/local/k3d-cluster.yaml`, then `kubectl get nodes`.
Expected: one node showing `Ready`.

- [ ] **Step 2: Deploy the app**

`kustomization.yaml`: namespace `boutique`, resource `github.com/GoogleCloudPlatform/microservices-demo/kustomize/base?ref=v0.10.7`.

Run: `kubectl create namespace boutique`, then `kubectl apply -k infra/local/boutique`, then `kubectl wait --for=condition=Ready pods --all -n boutique --timeout=600s`.
Expected: all pods Ready. The first run downloads images and can take several minutes.

- [ ] **Step 3: Use the shop**

Run: `kubectl port-forward -n boutique svc/frontend 8080:80`, then open http://localhost:8080.
Expected: the shop loads. Buy something to walk through checkout. Nothing is real.

- [ ] **Step 4: Look around, and see a pod come back**

Run: `kubectl get pods -n boutique`, `kubectl logs -n boutique deploy/loadgenerator --tail=20`, `kubectl delete pod -n boutique -l app=paymentservice`, then `kubectl get pods -n boutique -w` until the new pod is Ready.
Expected: the load generator shows traffic, and a replacement payment pod appears by itself.

- [ ] **Step 5: Explain back, then commit**

Explain back: what brought the payment pod back? What is the difference between a pod and a service? Which part of this shop would be affected if payments failed?

```bash
git add infra/local/k3d-cluster.yaml infra/local/boutique/kustomization.yaml
git commit -m "feat: run Online Boutique on a local k3d cluster"
```

---

### Task 3: Metrics with Prometheus

**Learn first:** what a metric and a time series are, what scraping means, and what `rate()` does.

**Files:**
- Create: `infra/local/prometheus-values.yaml`

**Interfaces:**
- Consumes: cluster `rca`.
- Produces: Helm release `prom` in namespace `monitoring`, with Prometheus reachable at `svc/prom-kube-prometheus-stack-prometheus` on port 9090.

- [ ] **Step 1: Install Prometheus**

Values: scrape interval `5s`, retention `1d`, Alertmanager off, Grafana on, and `serviceMonitorSelectorNilUsesHelmValues: false` so that Task 4's ServiceMonitor is picked up.

Run: `helm repo add prometheus-community https://prometheus-community.github.io/helm-charts`, then `helm upgrade --install prom prometheus-community/kube-prometheus-stack --version 92.17.0 -n monitoring --create-namespace -f infra/local/prometheus-values.yaml --wait`.
Expected: the release shows `deployed`.

- [ ] **Step 2: Query real data**

Run: `kubectl port-forward -n monitoring svc/prom-kube-prometheus-stack-prometheus 9090`, then open http://localhost:9090 and run these queries:

```
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="boutique"}[1m]))
sum by (pod) (container_memory_working_set_bytes{namespace="boutique"})
sum by (pod) (rate(container_network_receive_bytes_total{namespace="boutique"}[1m]))
sum by (pod) (kube_pod_container_status_restarts_total{namespace="boutique"})
```

Expected: each query returns a row per app pod. Any query that returns nothing is a problem to fix now, because the model needs these signals.

- [ ] **Step 3: Watch a change**

Graph the CPU query, delete the `currencyservice` pod, and watch the graph.
Expected: a visible gap or change, followed by recovery.

- [ ] **Step 4: Explain back, then commit**

Explain back: what does the CPU query calculate, in plain words? Which of these signals would you expect to change first if payments were overloaded?

```bash
git add infra/local/prometheus-values.yaml
git commit -m "feat: collect app metrics with Prometheus every 5 seconds"
```

---

### Task 4: Traces and request metrics

**Learn first:** what traces and spans are, why they show which service called which, and what the Collector does in the middle.

**Files:**
- Create: `infra/local/otel-values.yaml`, `infra/local/jaeger.yaml`
- Modify: `infra/local/boutique/kustomization.yaml`

**Interfaces:**
- Consumes: Helm release `prom`.
- Produces: Collector at `otel-collector.monitoring:4317`, Jaeger query at `svc/jaeger` on port 16686 in `monitoring`, and per-service request metrics in Prometheus.

- [ ] **Step 1: Deploy Jaeger**

`jaeger.yaml`: one Deployment and Service in `monitoring`, image `jaegertracing/jaeger:2.22.0`, with in-memory storage, a trace limit, and a memory limit. Ports 16686 and 4317.

Run: `kubectl apply -f infra/local/jaeger.yaml`, then `kubectl rollout status -n monitoring deploy/jaeger`.
Expected: rollout succeeds.

- [ ] **Step 2: Deploy the Collector**

`otel-values.yaml`: chart `open-telemetry/opentelemetry-collector` version 0.178.1, `mode: deployment`, `fullnameOverride: otel-collector`, an OTLP receiver, the `spanmetrics` connector, an exporter to `jaeger:4317`, a `prometheus` exporter on port 8889, and a ServiceMonitor scraping it every `5s`.

Run: `helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts`, then `helm upgrade --install otel open-telemetry/opentelemetry-collector --version 0.178.1 -n monitoring -f infra/local/otel-values.yaml --wait`.
Expected: the release shows `deployed`, and the pod is Ready.

- [ ] **Step 3: Turn on tracing in the app**

Add patches to `kustomization.yaml` for each service covered by upstream's `kustomize/components/google-cloud-operations/kustomization.yaml` at v0.10.7. Set `COLLECTOR_SERVICE_ADDR=otel-collector.monitoring:4317`, `OTEL_SERVICE_NAME=<service>` and `ENABLE_TRACING=1`. Do not use that component itself, or enable its Google Cloud profiler settings.

Run: `kubectl apply -k infra/local/boutique`, then `kubectl wait --for=condition=Ready pods --all -n boutique --timeout=600s`.
Expected: all pods Ready.

- [ ] **Step 4: Read a real trace**

Run: `kubectl port-forward -n monitoring svc/jaeger 16686`, then open http://localhost:16686 and find a `frontend` trace that includes checkout.
Expected: a timeline of calls between services.

- [ ] **Step 5: Check the request metrics**

In Prometheus, run:

```
sum by (service_name) (rate(traces_span_metrics_calls_total[1m]))
```

Expected: one row per service sending spans. If the metric has another name, find it under Prometheus's metric list and record the real name. Write down in `docs/journal.md` which of the 10 services are missing.

- [ ] **Step 6: Decide what to do about any missing service**

Tell Claude which services are missing. For each, confirm whether its callers' client spans still give request rate, errors and latency. Record the decision in `docs/journal.md`. If a service has no usable signal, update spec section 3 before continuing.

- [ ] **Step 7: Explain back, then commit**

Explain back: what is the difference between a metric and a trace? Why does a graph model need traces? What do we lose if a service sends no spans?

```bash
git add infra/local/otel-values.yaml infra/local/jaeger.yaml infra/local/boutique/kustomization.yaml docs/journal.md
git commit -m "feat: collect traces and per-service request metrics"
```

---

### Task 5: Build the dependency graph (the owner's first code)

**Learn first:** what a directed graph is, how Jaeger's JSON connects spans to services, and how a failing test guides the code. The owner writes `collector/graph.py`. Claude gives hints first.

**Files:**
- Create: `pyproject.toml`, `collector/__init__.py`, `collector/graph.py`, `collector/fetch_traces.py`, `tests/collector/test_graph.py`, `experiments/dependency-graph-v1.json`, `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Jaeger query API at `http://localhost:16686/api/traces`.
- Produces:
  - `edges_from_traces(traces: list[dict]) -> set[tuple[str, str]]`, returning `(caller, callee)` pairs.
  - `missing_services(edges: set[tuple[str, str]], expected: set[str]) -> set[str]`.
  - `experiments/dependency-graph-v1.json`: `{"app_version": "v0.10.7", "edges": [{"caller": str, "callee": str, "source": "trace" | "manual", "note": str}]}`.

- [ ] **Step 1: Set up the Python project**

Python 3.12 with `uv`, dev dependencies `pytest` and `ruff`.

Run: `uv sync`, then `uv run python -m pytest --version`.
Expected: prints the pytest version.

- [ ] **Step 2: Write the failing tests**

```python
from collector.graph import edges_from_traces, missing_services

def trace(*spans):
    return {
        "spans": [
            {"spanID": sid, "processID": svc,
             "references": [{"refType": "CHILD_OF", "spanID": parent}] if parent else []}
            for sid, svc, parent in spans
        ],
        "processes": {svc: {"serviceName": svc} for _, svc, _ in spans},
    }

def test_call_between_services_becomes_edge():
    t = trace(("a", "frontend", None), ("b", "cartservice", "a"))
    assert edges_from_traces([t]) == {("frontend", "cartservice")}

def test_same_service_spans_make_no_edge():
    t = trace(("a", "frontend", None), ("b", "frontend", "a"))
    assert edges_from_traces([t]) == set()

def test_missing_parent_is_skipped():
    t = trace(("b", "cartservice", "not-in-this-trace"))
    assert edges_from_traces([t]) == set()

def test_edges_combine_across_traces():
    t1 = trace(("a", "frontend", None), ("b", "cartservice", "a"))
    t2 = trace(("c", "frontend", None), ("d", "adservice", "c"))
    assert edges_from_traces([t1, t2]) == {("frontend", "cartservice"), ("frontend", "adservice")}

def test_missing_services_reports_gap():
    edges = {("frontend", "cartservice")}
    assert missing_services(edges, {"frontend", "cartservice", "adservice"}) == {"adservice"}
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run python -m pytest tests/collector/test_graph.py -v`
Expected: FAIL, because `collector.graph` has no such functions yet.

- [ ] **Step 4: Owner implements both functions in `collector/graph.py`**

Use only `spans`, `references` with `refType` `CHILD_OF`, and `processes`. Claude reviews it, but does not write it.

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run python -m pytest tests/collector/test_graph.py -v`
Expected: 5 passed.

- [ ] **Step 6: Capture the real graph**

`collector/fetch_traces.py` fetches recent traces for each service, calls both functions, prints the edges and any missing services, and writes `experiments/dependency-graph-v1.json`. Claude drafts it, and the owner reads it and explains it.

Run it with Jaeger port-forwarded, after at least 10 minutes of traffic.
Expected: edges that include `frontend` to `checkoutservice` and `checkoutservice` to `paymentservice`.

- [ ] **Step 7: Check against the app's published architecture**

Compare with the service diagram in the Online Boutique README. Add any real edge missing from traces with `"source": "manual"` and a note saying why. Redis is not one of the 10 root causes, so `cartservice` to Redis is left out.

- [ ] **Step 8: Add CI**

`ci.yml` runs on push and pull request: `uv sync`, `pytest` and `ruff check`, with no cluster needed.

Run locally: `uv run python -m ruff check .`
Expected: no errors.

- [ ] **Step 9: Explain back, then commit**

Explain back: walk through your code using one trace. Why are same-service spans ignored? Why is each edge marked `trace` or `manual`?

```bash
git add pyproject.toml uv.lock collector tests experiments/dependency-graph-v1.json .github/workflows/ci.yml
git commit -m "feat: build the service dependency graph from traces"
```

---

### Task 6: Chaos Mesh, one-command setup and the memory check

**Learn first:** what a Helm chart is, the difference between memory used and memory limits, what OOMKilled means, and why memory is the risk on this laptop.

**Files:**
- Create: `infra/local/chaos-mesh-values.yaml`, `infra/local/up.ps1`, `infra/local/down.ps1`, `docs/week-1-memory-check.md`
- Modify: `README.md` (create if missing), and the spec only if a fallback is used

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `up.ps1` (idempotent build), `down.ps1` (deletes the cluster), and the memory check result that week 2 relies on.

- [ ] **Step 1: Install Chaos Mesh, without injecting anything**

Values: runtime `containerd`, socket path `/run/k3s/containerd/containerd.sock`, dashboard off.

Run: `helm repo add chaos-mesh https://charts.chaos-mesh.org`, then `helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh --version 2.8.7 -n chaos-mesh --create-namespace -f infra/local/chaos-mesh-values.yaml --wait`.
Expected: its pods are Ready. Testing the actual faults is week 2 work.

- [ ] **Step 2: Measure memory for 30 minutes under load**

With everything running and the load generator on, take readings at 0, 15 and 30 minutes using `kubectl top pods -A`, `docker stats --no-stream` and Task Manager's available memory. Keep normal apps open that you would use during development. Record them in `docs/week-1-memory-check.md`.

- [ ] **Step 3: Decide pass or fail**

Pass when, for the full 30 minutes: all pods stay Ready, no pod restarts or is OOMKilled, Docker has at least 1.5 GB free of what Step 2 of Task 1 reported, and Windows has at least 1.5 GB available.

Check with: `kubectl get pods -A`.

- [ ] **Step 4: If it fails, apply the spec's cuts in order, re-measuring after each**

Grafana and the Jaeger UI first, then lower trace sampling, then lower replicas and resource requests. If it still fails, stop and use the spec's fallback, a temporary cloud server. This needs the owner's decision because it costs money. Update the spec with whichever cut was used.

- [ ] **Step 5: Write the one-command scripts, and rebuild from nothing**

`up.ps1` checks Docker first, dot-sources `versions.ps1`, creates the cluster if missing, then applies everything in order and waits for Ready. `down.ps1` runs `k3d cluster delete rca`.

Run: `./infra/local/down.ps1`, then `./infra/local/up.ps1`, then `kubectl get pods -A`.
Expected: all pods Ready, built only from files in the repo.

- [ ] **Step 6: Try the two script failure cases**

Run `up.ps1` again on the running cluster.
Expected: it finishes without errors and nothing is duplicated.

Quit Docker Desktop, then run `up.ps1`.
Expected: it stops immediately with a message asking you to start Docker.

- [ ] **Step 7: Restart the laptop**

Restart Windows, start Docker Desktop, then run `k3d cluster start rca` and `kubectl wait --for=condition=Ready pods --all -A --timeout=600s`.
Expected: all pods Ready without a rebuild. If `k3d cluster start` says it is already running, skip it.

- [ ] **Step 8: Write the README and journal**

`README.md`: what the project is, its current status, and how to run `up.ps1`, with no results claimed yet. `docs/journal.md`: what surprised you this week, and the decisions you made.

- [ ] **Step 9: Explain back, then commit**

Explain back: which pods use the most memory, and why? What would you cut first if memory ran out, and why does that not harm the data? What does OOMKilled mean?

```bash
git add infra/local README.md docs
git commit -m "feat: add one-command local setup and record the memory check"
```

**Week 1 is finished when** `up.ps1` builds the full stack, the memory check has a recorded result, and the owner can explain every part of it without notes.
