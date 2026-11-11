# Root-cause GNN and human-approved remediation agent: design

**Date:** 2026-11-02
**Status:** Draft for review
**Repository:** [faisssss/new-proj](https://github.com/faisssss/new-proj)

## 1. Purpose

Build a portfolio project that shows real depth in machine learning, cloud infrastructure and agent engineering. The owner trains the core model and writes the core agent themselves, learning as they go, and must be able to explain every part in a technical interview.

**The problem.** When one service in a microservices app fails, the failure spreads and alerts fire across many services. Engineers then lose time working out where it started.

**The system.** It automatically finds the service that most likely started the failure, investigates it, proposes a fix, applies the fix once a person approves it, and checks that the app has recovered.

### Constraints

- About 8 weeks at about 35 hours a week.
- The owner starts with basic Python and Java, and is new to Kubernetes, graph neural networks and AWS.
- Development laptop: 16 GB RAM, 10-core i7-12650H, RTX 3050 with 4 GB, about 250 GB of free disk, Windows 11, Docker.
- Cloud and API spending stays small and capped (section 9).

### Success criteria

1. A person can trigger a failure and see the system identify the source, propose a fix, and confirm recovery after approval.
2. The model and all three baselines are measured on the same test sets, and the results are published whether or not the model wins.
3. The whole AWS environment can be created and destroyed with Terraform.
4. A public demo page works without an account, and without any cost per visitor.
5. The owner can explain the model, the agent and the evaluation without notes.

The model beating the baselines is a goal, not a condition of success. An honest report that it did not is still a valid outcome.

### Out of scope

- Fixes applied without human approval.
- Claims of production readiness.
- Multiple cloud providers, and managed Kubernetes (EKS).
- Cloud GPUs for training.
- User accounts, or use on anyone else's systems.
- Testing on a second app is a stretch goal only (section 12).

## 2. Architecture

```
Online Boutique on Kubernetes ◄── Fault injector
        │                              │
        ▼                              ▼ ground-truth label
Metrics, traces, logs ───────► Run collector ──► Dataset
        │                                           │
        │ (when an alert fires)                     ▼ training
        ▼                                      Trained model
  Inference service ◄───────────────────────────────┘
        │ ranked list of suspect services
        ▼
  Agent loop ──► read-only investigation tools
        │
        ▼ proposed fix
  Human approval ──► Allowed-action executor ──► Recovery check
```

The same system runs on the laptop (`k3d`) and on AWS (`k3s` on one server). Training always happens on the laptop.

## 3. Test environment

- **App:** Google's open-source [Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo), pinned to one release. It has 10 application services, a load generator and a Redis store. The 10 application services are the possible root causes.
- **Traffic:** the app's load generator, at a fixed rate during data collection.
- **Metrics:** Prometheus, scraping every 5 seconds, collecting CPU, memory, network, restarts and pod status.
- **Request-level signals:** OpenTelemetry traces. The Collector's span metrics provide each service's request rate, error rate and latency, which the app does not expose directly. At v0.10.7, `adservice`, `cartservice` and `shippingservice` send no spans of their own, so their request signals come from the client spans of the services calling them. This measures them from the caller's side, and includes any network delay.
- **Logs:** a small script that counts error-level lines per service. This avoids running a full log system.
- **Dependency graph:** directed edges (caller to callee) built from captured traces, stored as a versioned file.

**Week 1 check: memory.** Run the full stack on the laptop under load. If it does not fit in 16 GB, the order of cuts is: trace viewer UI, then lower trace sampling, then replicas and resource requests. If it still does not fit, collect data on a temporary cloud server and update this spec.

## 4. Fault injection and dataset

Each run injects one fault into one service.

| Fault type | Method | Used in |
|---|---|---|
| CPU overload | Chaos Mesh | Train, validation, test |
| Added network delay | Chaos Mesh | Train, validation, test |
| Pod crashes | Chaos Mesh | Train, validation, test |
| Bad release (broken image or config) | Scripted deployment | Train, validation, test |
| Memory pressure | Chaos Mesh | **Test only** |
| Packet loss | Chaos Mesh | **Test only** |

**Week 2 check: fault injection on Windows.** Some Chaos Mesh faults need kernel features that the Docker Desktop (WSL2) kernel may lack. Test each fault early. A fault that cannot run locally moves to a temporary cloud server, or is replaced by a similar fault, with this table updated.

### Each run

About 5 minutes in total: 2 minutes healthy, 2 minutes with the fault active, and 1 minute for recovery. The cluster is then checked and reset before the next run.

Each run saves its metrics, error-log counts, the fault details and true root cause, the fault start and end times, the alert time, and the versions of the app and collection code.

### Dataset size

| Set | Runs | Contents |
|---|---|---|
| Train | 280 | 4 fault types × 10 services × 7 repeats |
| Validation | 40 | 4 fault types × 10 services × 1 repeat |
| Test: seen fault types | 40 | 4 fault types × 10 services × 1 repeat |
| Test: unseen fault types | 180 | 2 fault types × 10 services × 9 repeats |
| Healthy | 40 | No fault, used to measure false alarms |

That is 580 runs, or about 48 hours of collection, which is about 6 nights at 8 hours a night.

### Rules against leakage and false confidence

- Whole runs stay in one set. Windows from one run never appear in two sets.
- The split and the unseen fault types are fixed before any training.
- Service names and IDs are not model inputs, so the model cannot just memorise which service fails most often.
- The fault start time is never an input. Each input window ends at the alert time.
- Both test sets are used once, for the final results. All tuning uses the validation set. If a test set has to be reused, the report says so.

### Validity checks

A run is marked invalid, excluded and counted in the report if the fault did not take effect, the app was unhealthy before the fault, or data is missing. The collector can resume after an interruption, and it replaces invalid runs so that each combination reaches its target count.

## 5. Alert

A fixed rule watches frontend error rate and latency, and fires when either stays above a threshold for 30 seconds. The thresholds are set from the healthy periods of the training runs only, and then frozen. Runs where no alert fires count as misses for that method. They are not silently dropped.

## 6. Model and baselines

### Input

For each service, a window of the 2 minutes before the alert, sampled every 5 seconds. The features are CPU, memory, network, restarts, request rate, error rate, latency and error-log count. They are normalised using statistics from the healthy periods of the training runs, so that normalising does not reveal when the fault started.

### Model

Written by the owner in PyTorch and PyTorch Geometric:

1. A GRU encodes each service's time series into a vector, with the same weights for every service.
2. Two graph attention layers pass information along the dependency graph.
3. A final layer gives each service a score, and softmax turns the scores into a ranking.
4. Training uses cross-entropy against the true root cause.

The model starts small and only grows if the validation results justify it. It must train within 4 GB of GPU memory, falling back to CPU if needed.

### Baselines

| Baseline | Method | The question it answers |
|---|---|---|
| Anomaly score | Rank services by how far their signals moved from healthy | Is machine learning needed at all? |
| Random walk | Personalised PageRank over the dependency graph, seeded by anomaly scores | Does a learned model beat a classic graph method? |
| Model without graph | The same GRU and final layer, with no graph layers | Does the graph actually help? |

### Metrics

- Top-1 and top-3 accuracy, with 95% bootstrap confidence intervals.
- Reported separately for seen and unseen fault types, and per fault type.
- Alert false-alarm rate on healthy runs.
- A confusion matrix, plus a review of the model's worst failures.

## 7. Agent

Written by the owner in Python with no agent framework. The LLM sits behind a small interface, so it can be swapped without rewriting the agent.

**The LLM is chosen in week 5.** The options are a free local model or a paid API such as Claude. The owner decides after testing and checking prices, and no LLM account or spending is needed before then. If a local model is chosen, the hardware for the live AWS version is decided at the same time, because the planned server has no GPU.

### Loop

1. Receive the alert and the model's ranking.
2. Investigate using read-only tools, within a limit on steps and spending.
3. Produce a diagnosis with its evidence, plus one proposed action or a decision to escalate.
4. Wait for human approval.
5. Run the approved action.
6. Check recovery against the alert rule. If the app has not recovered within the time limit, escalate and do not retry on its own.

### Tools

| Kind | Tools |
|---|---|
| Read-only | Get ranking, query metrics, read logs, list recent releases, view the dependency graph |
| Needs approval | Roll back a deployment, restart a service, scale a service within fixed limits |
| Always available | Escalate to a person |

### Safety rules

These are enforced in code and Kubernetes permissions, not in the prompt:

- The executor rejects any action or argument outside the allowed list.
- The agent's Kubernetes service account can only act within the app's namespace.
- It has no shell tool, and no access to secrets.
- Logs and metrics are treated as untrusted input, since a log line could contain text written to mislead the LLM. Text from them cannot trigger an action without passing the same checks and human approval.
- Every step, tool call, approval, token count and cost goes to a per-incident log.

### Failures

API errors get a limited number of retries, then the agent escalates. Reaching a step or spending limit, or receiving an invalid or malformed proposal, also leads to escalation. Nothing is ever applied as a fallback.

## 8. End-to-end evaluation

Chaos faults usually clear on their own, which would make a do-nothing agent look successful. Recovery is therefore measured only on persistent faults that stay broken until they are fixed:

- A bad image release.
- A bad configuration release.
- A resource limit set too low.
- A service scaled to zero.

**Scenarios:** 20 persistent-fault incidents. Each runs twice, with and without the model's ranking, for 40 agent runs. Each scenario also has a do-nothing control, measured without the agent.

**Approval:** a scripted approver accepts any allowed action during this evaluation, so that the results are repeatable. The write-up states this, and the demo uses a real person.

**Metrics:** diagnosis correct, action correct, time to recovery, steps taken, cost per incident, and how the runs with and without the ranking compare.

For chaos faults, the agent is scored on diagnosis only.

## 9. AWS and cost

- Region `ap-south-1` (Mumbai). One EC2 server running `k3s`, set up entirely with Terraform and sized during week 6.
- The server runs only when needed, and `terraform destroy` removes everything. A smoke test confirms that this works.
- Access is limited to the owner's IP address. IAM permissions are as narrow as practical.
- Secrets are never committed. API keys come from environment variables or AWS Parameter Store, and Terraform state stays out of git.
- **Spending limits, to confirm at spec review:** an AWS budget alert at USD 20 per month. If a paid LLM API is chosen in week 5, a project spending limit is set before first use, starting from USD 20, and the agent also gets a per-incident spending limit. Actual prices are checked before anything is created.

## 10. Demo

- **Public page:** a static site on GitHub Pages replaying recorded real incidents. It shows the service map, alarms spreading, the model's ranking, the agent's steps, the approval and the recovery. It also has the evaluation results and their limitations. It makes no calls to AWS or any LLM.
- **Live version:** a private environment, created with Terraform for interviews. Only the owner can trigger faults and approve fixes.

Recordings are real runs and are labelled as recordings. Nothing shown is scripted to look better than it was.

## 11. Repository and engineering

```
infra/local/       k3d, Online Boutique, monitoring and Chaos Mesh setup
infra/aws/         Terraform
collector/         fault injector, run collector, validity checks
rca/               features, dataset, baselines, model, training, evaluation
agent/             loop, tools, executor, approval, logging
demo/              static replay site
experiments/       configs and result summaries (raw data stays out of git)
docs/journal.md    the owner's notes: decisions, mistakes, what changed
```

- Python 3.12, `uv`, `pytest`, `ruff`. Raw run data and model checkpoints stay out of git.
- Results are reproducible: every result records its git commit, config, random seed and dataset version.
- Project licence: MIT, to confirm at spec review.

### Testing

- **Unit tests:** feature code, split rules (including a test that no run appears in two sets), baselines and validity checks.
- **Model sanity tests:** the model can overfit a tiny dataset, and it learns a small synthetic graph with a known cause.
- **Agent tests:** a fake LLM runs scripted conversations. Forbidden actions, malformed proposals, limits being reached and misleading log lines must all be handled safely, with no real API calls.
- **Infrastructure:** `terraform validate`, plus a smoke test of the deployed system.
- **CI:** GitHub Actions runs everything except tests that need a cluster, a GPU, AWS or a paid API.

## 12. Schedule

| Week | Work | Finished when |
|---|---|---|
| 1 | Run the app and monitoring locally | The full stack runs under load, and the memory check is done |
| 2 | Fault injection and collector | Every fault is tested, 20 trial runs are valid, overnight collection is running |
| 3 | Machine learning basics, feature code and baselines | Baseline results on the validation set |
| 4 | Graph neural network | Training works, and it is compared with baselines on validation |
| 5 | LLM choice, agent loop, tools, approval and safety | One full incident recovers on the laptop |
| 6 | AWS and Terraform | Create, test and destroy all work |
| 7 | Final test-set evaluation and agent evaluation | Results written up. Stretch goal if time allows |
| 8 | Demo, write-up, buffer | Public page live, README finished |

**Stretch goal:** test the frozen model on a second microservices app that it has never seen, and report the result either way.

**If time runs short,** cut in this order: the stretch goal, the live AWS interview version (keeping one recorded AWS run), then demo polish. A laptop-only system with an honest evaluation is the minimum complete project, and it should exist at the end of week 5, apart from the final evaluation.

## 13. Roles

| Area | Owner | Claude |
|---|---|---|
| Local setup and Kubernetes | Runs it, learns it | Explains, writes setup files, helps debug |
| Fault injection | Chooses faults, runs and checks experiments, extends the script | Writes the first script |
| Data pipeline | Writes labelling and feature code | Explains, helps with collection plumbing, reviews |
| Baselines | Writes | Explains, reviews |
| **Model** | Runs training, reads and understands every part | Writes it and explains it line by line |
| Evaluation | Runs, interprets | Checks for mistakes such as leakage |
| **Agent loop and safety rules** | Runs it, reads and understands every part | Writes it and explains it line by line |
| AWS and Terraform | Creates accounts, handles payment and keys, runs deploys | Writes the first files and explains them line by line |
| Demo page | Decides content, records incidents | Builds most of it |
| Write-up | Writes | Gives feedback, checks claims against results |

**Learning loop for each step:** Claude explains the concept, writes the code and walks through it line by line; the owner runs it and asks about anything unclear; then commit and add a line to the journal. (Changed on 2026-11-11 at the owner's request: the owner no longer writes the core code.)

**Resume rule:** claim only what was built and measured, using the real numbers and "human-approved", not "autonomous".

## 14. Main risks

| Risk | Response |
|---|---|
| The stack does not fit in 16 GB | Week 1 check, with the cuts in section 3 |
| Chaos faults do not work on the Windows setup | Week 2 check, then use a temporary cloud server or a similar fault |
| Synthetic faults do not resemble real failures | State this limit in every result, and test unseen fault types |
| Too little data, or a noisy result | Report confidence intervals, and collect more runs if validation shows it would help |
| The model does not beat the baselines | Publish the result and analyse why |
| Learning takes longer than planned | Use the cut order in section 12, and keep the schedule honest |
| Unexpected cloud costs | Budget alerts, spending limits and `terraform destroy` after each session |
| A free local LLM is too weak for the agent | Test it in week 5. The owner then chooses between a paid API and narrowing what the agent does |
