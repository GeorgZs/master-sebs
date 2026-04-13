# Run 5 — Cloud-to-Cloud Benchmarks & Latency Decomposition (2026-04-10)

Benchmarks run from EC2 instances inside each system's VPC, simulating microservice-to-function communication. Compared against existing edge (laptop) results from run_1–run_4.

## Motivation

All prior results (run_1–run_4) were collected from a laptop over the internet. Internet RTT (~20-30ms) dominated client latency and obscured the actual system differences. This run measures two things:

1. **Cloud-to-cloud latency** — what a microservice calling a serverless function actually experiences
2. **Latency decomposition** — breaking client latency into Network RTT + Function Execution + Serverless Overhead

## Setup

### EC2 Benchmark Clients

| System | Client EC2 | Instance type | Target endpoint | Network |
|--------|-----------|---------------|-----------------|---------|
| Lambda | `13.51.69.83` (Lambda VPC) | t3.small, AL2023 | API Gateway HTTPS (intra-region) | Regional |
| Boki | `13.53.71.50` (Boki VPC) | t3.small, Ubuntu 20.04 | `http://10.41.1.237:8080` (private IP) | Private |
| Cloudburst | `16.171.237.239` (existing client node) | t3.small, AL2023 | `http://localhost:8088` | Localhost |

### Experiment Matrix

Same as run_2, all from EC2:

| Experiment | Concurrency | State size | Reps |
|------------|-------------|------------|------|
| Throughput | 1, 10, 50, 100 | 64KB | 200 |
| Latency distribution | 10 | 64KB | 1000 |
| State size impact | 10 | 1, 64, 512KB | 200 |

### Infrastructure

- **Lambda:** Existing deployment (unchanged from run_2). API Gateway + Lambda + ElastiCache Redis.
- **Boki:** Fresh `terraform destroy + apply` (deployment 7). Required coordinated restart: infra → engines → ZK `cmd/start`. Benchmark binary rebuilt with `CGO_ENABLED=0` (static linking) due to GLIBC 2.31 in the Docker container.
- **Cloudburst:** Existing deployment from run_4. Scheduler + 2 executors + 1 Anna node. HTTP gateway on port 8088.

### Results Delivery

Each EC2 client committed results to `results/cloud/<system>/` and pushed to GitHub via deploy key. Results pulled locally for analysis.

---

## Latency Decomposition

### Formula

```
ClientLatency = NetworkRTT + FunctionExecution + ServerlessOverhead
```

- **NetworkRTT** ≈ `http_startup` (pycurl `PRETRANSFER_TIME` = TCP handshake). Includes TLS for Lambda (HTTPS).
- **FunctionExecution** = `benchmark` (`end - begin` from function response). State write + read + compute.
- **ServerlessOverhead** = `client - benchmark - http_startup`. The dispatch/routing residual.

### Cross-System Comparison (latency-dist, P50, warm invocations)

#### Edge (laptop → internet → AWS)

| Component | Lambda | Boki | Cloudburst |
|-----------|--------|------|------------|
| Client E2E | 55.3ms | 50.9ms | 142.1ms |
| Network RTT | 23.1ms | 7.7ms | 8.2ms |
| Function execution | 5.1ms | 7.6ms | 19.5ms |
| Serverless overhead | 25.5ms | 35.1ms | 115.6ms |

#### Cloud (EC2 → private/regional → AWS)

| Component | Lambda | Boki | Cloudburst |
|-----------|--------|------|------------|
| Client E2E | 27.3ms | **10.2ms** | 99.3ms |
| Network RTT | 8.1ms | **236μs** | 183μs |
| Function execution | 2.3ms | 5.2ms | 14.5ms |
| Serverless overhead | 15.8ms | **4.0ms** | 82.0ms |

#### Percentage Breakdown (Cloud, P50)

| Component | Lambda | Boki | Cloudburst |
|-----------|--------|------|------------|
| % Network | 30.1% | 2.6% | 0.2% |
| % Function | 9.3% | 54.5% | 14.3% |
| % Overhead | 59.0% | 42.8% | 85.3% |

Samples: Lambda=1000, Boki=1000, Cloudburst=1000.

### Improvement: Edge → Cloud

| System | Edge P50 | Cloud P50 | Improvement | What changed |
|--------|----------|-----------|-------------|-------------|
| Lambda | 55.3ms | 27.3ms | **2.0x** | TLS overhead halved (intra-region), RTT 23→8ms |
| Boki | 50.9ms | 10.2ms | **5.0x** | Private IP eliminates internet RTT, overhead 35→4ms |
| Cloudburst | 142.1ms | 99.3ms | **1.4x** | Network removed but scheduler dispatch still 82ms |

---

## Throughput Results (Cloud)


| Concurrency | Lambda (inv/s) | Boki (inv/s) | Cloudburst (inv/s) |
|-------------|----------------|--------------|-------------------|
| c=1 | 38.8 | 144.2 | 36.3 |
| c=10 | 145.9 | 428.2 | 46.7 |
| c=50 | 221.2 | 875.9 | 37.3 |
| c=100 | 545.9 | 849.9 | 54.8 |


### Throughput Comparison: Edge vs Cloud


| Concurrency | Lambda edge→cloud | Boki edge→cloud | Cloudburst edge→cloud |
|-------------|-------------------|-----------------|----------------------|
| c=1 | 20.7 → 38.8 (1.9x) | 42.9 → 144.2 (3.4x) | 25.2 → 36.3 (1.4x) |
| c=10 | 84.0 → 145.9 (1.7x) | 280.5 → 428.2 (1.5x) | 32.6 → 46.7 (1.4x) |
| c=50 | 87.9 → 221.2 (2.5x) | 532.8 → 875.9 (1.6x) | 38.9 → 37.3 (1.0x) |
| c=100 | 86.8 → 545.9 (6.3x) | 665.1 → 849.9 (1.3x) | 62.3 → 54.8 (0.9x) |


**Observations:**
- **Lambda scales dramatically in cloud** — from 87 to 546 inv/s at c=100 (6.3x). From the laptop, Lambda was bottlenecked by the internet RTT serializing effective concurrency. From EC2, the lower RTT allows true concurrent execution.
- **Boki gains most at low concurrency** — 3.4x at c=1 (network was the bottleneck). At high concurrency, the engine dispatch is the bottleneck regardless of network.
- **Cloudburst is unchanged** — the scheduler dispatch chain (ZMQ → scheduler → executor) is the bottleneck, not the network. Moving to cloud doesn't help.

### State Size Impact (Cloud, write P50)


| State Size | Lambda | Boki | Cloudburst |
|------------|--------|------|------------|
| 1 KB | 800μs | 3,738μs | 4,769μs |
| 64 KB | 1,936μs | 4,709μs | 7,706μs |
| 512 KB | * | 5,003μs | 10,627μs |


\* Lambda 512KB: 0.8 inv/s (96.7s for 200 reps) — likely hitting Lambda timeout or Redis write timeout with large payloads. Needs investigation.

---

## Observations

### 1. Serverless overhead is the dominant cost

In cloud deployments, network RTT becomes negligible (< 1ms for Boki/Cloudburst, ~8ms for Lambda via API Gateway). The serverless overhead — the dispatch/routing layer between the HTTP request and the function execution — dominates:

- **Lambda (15.8ms):** API Gateway request routing + Lambda container dispatch + response serialization. This is the cost of the managed platform. Remarkably stable across concurrency levels (~15-22ms).
- **Boki (4.0ms):** Gateway HTTP parsing + ZK-based engine dispatch. The lowest overhead of all three systems. Scales well up to c=50, then increases (19.9ms at c=50, 42.8ms at c=100) due to engine-level queueing.
- **Cloudburst (82.0ms):** HTTP→ZMQ bridge + scheduler DAG resolution + executor dispatch + result serialization. The longest dispatch chain. Does not improve with network proximity because the bottleneck is internal.

### 2. Boki is the fastest system in cloud-to-cloud

At 10.2ms E2E (P50), Boki outperforms Lambda (27.3ms) by 2.7x and Cloudburst (99.3ms) by 9.7x. The shared log architecture with engine-local caching provides the fastest state access, and the gateway's direct engine dispatch has minimal overhead.

### 3. Lambda benefits most from in-cloud deployment at high concurrency

Lambda's throughput at c=100 jumped from 86.8 to 545.9 inv/s (6.3x). From the laptop, internet RTT serialized requests — each concurrent request had to wait for the TCP handshake (~20ms). From EC2, the lower RTT (~8ms with TLS) allows requests to overlap effectively.

### 4. Cloudburst's bottleneck is architectural, not network

Moving from laptop to EC2 improved Cloudburst's latency by only 1.4x (142→99ms). The ~82ms of serverless overhead is the scheduler dispatch chain: ZMQ serialization, scheduler queueing, function lookup, executor dispatch, result collection. This is an inherent cost of Cloudburst's multi-hop architecture.

### 5. Two deployment scenarios for the thesis

| Scenario | Who | What it measures |
|----------|-----|-----------------|
| **Edge** (laptop → cloud) | End user, IoT device, mobile app | Full E2E including internet latency |
| **Cloud** (EC2 → cloud) | Microservice, workflow step, internal API | System overhead without network noise |

The cloud scenario reveals the true system differences. The edge scenario shows what real users experience.

---

## Measurement Notes

- **Lambda Network RTT (8.1ms, cloud):** This is the TLS handshake to API Gateway from within the same region. HTTPS adds ~6ms of TLS negotiation on top of the ~2ms TCP handshake. Lambda cannot be invoked without API Gateway from an HTTP client.

- **Boki Network RTT (236μs, cloud):** Plain HTTP to the gateway's private IP within the same VPC. This is the minimum possible network cost — a single TCP SYN-ACK over a VPC private network.

- **Cloudburst Network RTT (183μs, cloud):** The HTTP gateway runs on the same EC2 instance as the benchmark client (`localhost`). The 183μs is the loopback TCP handshake overhead.

- **Boki infrastructure notes:** Required full cluster redeploy due to ZK discovery lifecycle (L7). The infra user_data had a bug (`tee` before `mkdir`) and lacked auto-start (`docker-compose up -d`). Both fixed. The benchmark binary required static compilation (`CGO_ENABLED=0`) because the Docker container (`zjia/boki:sosp-ae`) uses GLIBC 2.31.

- **Lambda 512KB anomaly:** From EC2, Lambda 512KB statesize achieved only 0.8 inv/s (vs 87 inv/s at 64KB from laptop). This suggests a Redis write timeout or Lambda execution timeout for large payloads that was not triggered from the laptop (where internet RTT dominated). Needs investigation.

---

## Files

```
results/cloud/lambda/          — 8 JSON files (throughput, latency-dist, statesize)
results/cloud/boki/            — 8 JSON files
results/cloud/cloudburst/      — 8 JSON files
results/cloud/latency_drilldown_cloud.csv  — 7,075 rows (per-invocation decomposition)
scripts/latency_drilldown.py   — decomposition script
docs/plots/out/11_latency_decomposition.png  — edge vs cloud stacked bar
```

---

## Consolidated Cloud Results

### Throughput Scaling (64KB state, cloud)


| Concurrency | Lambda (inv/s) | Boki (inv/s) | Cloudburst (inv/s) |
|-------------|----------------|--------------|-------------------|
| c=1 | 38.8 | 144.2 | 36.3 |
| c=10 | 145.9 | 428.2 | 46.7 |
| c=50 | 221.2 | 875.9 | 37.3 |
| c=100 | 545.9 | 849.9 | 54.8 |


### Latency Distribution (64KB state, cloud)


| Metric | Lambda | Boki | Cloudburst |
|--------|--------|------|------------|
| Client P50 | 27.3ms | 10.2ms | 99.3ms |
| Client P95 | 33.0ms | 14.0ms | 209.8ms |
| Client P99 | 39.7ms | 15.3ms | 1,066.5ms |
| Write P50 | 1,086μs | 3,471μs | 7,708μs |
| Read P50 | 894μs | 2μs* | 1,838μs |
| Samples | 1,000 | 1,000 | 1,000 |


\* Boki read is engine-cached (see LIMITATIONS.md L6).

### Per-System Latency Breakdown (All experiments, Cloud, P50)


| System | Experiment | Client P50 | Network | Function | Overhead |
|--------|-----------|-----------|---------|----------|----------|
| Lambda | latency-dist | 27.3ms | 8.1ms | 2.3ms | 15.8ms |
| Lambda | throughput-c1 | 24.0ms | 4.9ms | 2.1ms | 17.0ms |
| Lambda | throughput-c10 | 28.6ms | 8.1ms | 2.3ms | 17.0ms |
| Lambda | throughput-c50 | 37.5ms | 12.0ms | 2.5ms | 19.4ms |
| Lambda | throughput-c100 | 49.9ms | 22.3ms | 2.2ms | 21.6ms |
| Lambda | statesize-1kb | 26.8ms | 8.2ms | 1.2ms | 16.0ms |
| Lambda | statesize-64kb | 28.1ms | 8.4ms | 3.3ms | 16.1ms |
| Lambda | statesize-512kb | 40.5ms | 8.1ms | 16.6ms | 16.0ms |
| Boki | latency-dist | 10.2ms | 236μs | 5.2ms | 4.0ms |
| Boki | throughput-c1 | 8.2ms | 280μs | 6.1ms | 1.9ms |
| Boki | throughput-c10 | 9.6ms | 249μs | 5.2ms | 3.9ms |
| Boki | throughput-c50 | 25.7ms | 204μs | 5.5ms | 19.9ms |
| Boki | throughput-c100 | 51.3ms | 286μs | 6.4ms | 42.8ms |
| Boki | statesize-1kb | 9.0ms | 352μs | 4.9ms | 3.2ms |
| Boki | statesize-64kb | 9.5ms | 274μs | 5.3ms | 3.2ms |
| Boki | statesize-512kb | 9.9ms | 269μs | 4.9ms | 4.1ms |
| Cloudburst | latency-dist | 99.3ms | 183μs | 14.5ms | 82.0ms |
| Cloudburst | throughput-c1 | 29.4ms | 234μs | 25.7ms | 3.5ms |
| Cloudburst | throughput-c10 | 94.5ms | 182μs | 13.6ms | 79.6ms |
| Cloudburst | throughput-c50 | 413.8ms | 245μs | 11.2ms | 304.2ms |
| Cloudburst | throughput-c100 | 801.9ms | 218μs | 13.0ms | 545.0ms |
| Cloudburst | statesize-1kb | 83.9ms | 184μs | 10.8ms | 74.0ms |
| Cloudburst | statesize-64kb | 91.2ms | 184μs | 13.3ms | 77.2ms |
| Cloudburst | statesize-512kb | 100.3ms | 188μs | 16.9ms | 84.8ms |


### Plots Index (updated)


| # | File | Description |
|---|------|-------------|
| 01 | throughput_scaling.png | Throughput vs concurrency (edge) |
| 02 | latency_cdf.png | Cumulative latency distribution (edge) |
| 03 | latency_percentiles.png | P50/P95/P99 grouped bars (edge) |
| 04 | write_read_breakdown.png | Write vs read P50 per system (edge) |
| 05 | state_size_impact.png | Write latency vs state size (edge) |
| 06 | cold_start.png | Cold start comparison (log scale) |
| 07 | cost_per_invocation.png | Cost per 1,000 invocations |
| 08 | resource_usage.png | CPU/memory during experiments |
| 09 | state_placement.png | Same-key vs unique-key (Cloudburst) |
| 10 | scaling_timeline.png | Cloudburst scale-out timeline |
| 11 | latency_decomposition.png | Edge vs cloud latency decomposition |
