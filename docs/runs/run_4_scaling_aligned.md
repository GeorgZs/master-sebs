# Run 4 — Time-Aligned Scaling Timeline (2026-04-07)

Scaling experiment with sustained concurrent load and manual scale-out, producing a multi-panel timeline figure for the thesis. Cloudburst only — Boki could not produce a clean timeline (explained below).

## Setup

Both systems freshly deployed via `terraform destroy` + `terraform apply` after run_3 degradation. See `tf_boki.md` and `tf_cloud.md` for deployment IPs.

## Cloudburst Scaling Timeline (Plot 10)

**Configuration:**

- Load: c=5 continuous (Python `ThreadPoolExecutor`, 5 workers always busy)
- Duration: 180 seconds
- Scale event: `set-desired-capacity 3` at T+60s
- Data collection: per-invocation `(timestamp_ms, latency_ms, phase)` via `/tmp/scaling_load.py`

**Results: 7,020 data points**


| Phase                       | Mean latency | Samples | Duration |
| --------------------------- | ------------ | ------- | -------- |
| Before scale (2 executors)  | 89ms         | 2,375   | 0–60s    |
| After scale (2→3 executors) | 90ms         | 4,645   | 60–180s  |


**Observations from plot 10:**

- **Top panel (throughput):** Steady ~30-50 inv/s throughout. No throughput drop at the scale event. Minor fluctuations are normal for the HTTP→ZMQ gateway path.
- **Middle panel (latency scatter):** Green dots (before) and orange dots (after) occupy the same latency band (~40-200ms). No visible spike at T+60s. Occasional outliers to 300-400ms in both phases — these are Anna KVS round-trip variance, not scaling artifacts.
- **Bottom panel (executor count):** Steps from 2→3 at ~~T+160s — the 100-second delay between the ASG `set-desired-capacity` command (T+60s) and the executor actually appearing reflects the EC2 launch time (~~30s) plus the Cloudburst bootstrap time (~90s: git clone, protobuf build, pip install, executor start, ZMQ connect to scheduler).

**Key finding:** Manual scale-out causes zero latency disruption. The new executor bootstraps in the background while existing executors serve all traffic. Once the third executor connects to the scheduler (~T+160s), the scheduler dispatches work across all three, but the load at c=5 is low enough that 2 executors were never saturated — the third executor adds capacity headroom without visibly improving latency.

## Why Boki Was Excluded

Two independent issues prevented a clean Boki scaling timeline:

### 1. Data collection methodology

The run_2 Boki scaling data (`boki_scaling_up_c10.csv`, 1,380 points) was collected with a shell-script loop:

```bash
for j in $(seq 1 10); do
  ( curl ... >> csv ) &
done
wait
sleep 0.2
```

This fires c=10 parallel curls, waits for all to complete, sleeps 200ms, then repeats. The `wait` blocks on the slowest curl, creating batch patterns. Combined with internet RTT (~30-100ms), this produced bursty data with large gaps — only 10 "before" samples vs 1,370 "after" samples. The Python continuous load generator (`ThreadPoolExecutor`) used for Cloudburst keeps all workers busy without waiting, producing evenly distributed data.

### 2. ZK discovery lifecycle

Boki's gateway discovers engines via ZooKeeper, but only during the initial `cmd/start` issued by the ZK-setup script (~120s after cluster start). After any infra container restart:

- Engines re-register with ZK (verified via ZK node listing)
- But the gateway never re-reads the engine list — it was populated at `cmd/start` time
- Result: gateway returns empty responses for all function calls

This is a fundamental architectural limitation of Boki's cluster lifecycle — not a configuration issue. It means:

- Fresh `terraform apply` works (everything starts in sequence, `cmd/start` discovers engines)
- Any manual restart of infra containers permanently breaks the gateway→engine dispatch
- The only recovery is full `terraform destroy` + `apply`

This is documented in LIMITATIONS.md L4 (Managed Scaling vs True Auto-Scaling) as evidence that self-hosted runtimes require solving service discovery refresh for scaling to work.

### Boki scaling was still validated

The run_2 data (`boki_scaling_up_c10.csv` and `boki_scaling_down_c10.csv`) confirmed:

- Scale-up (2→3 engines): no sustained latency disruption, one 10s outlier during scale-down
- Scale-down (3→2 engines): transparent to in-flight requests

The finding is the same as Cloudburst: manual scaling works without disruption. The limitation is that Boki cannot produce a publication-quality timeline figure due to the data collection and lifecycle issues described above.

## Files

```
results/run2/cloudburst_scaling_timeline.csv   (7,020 points)
results/run2/boki_scaling_up_c10.csv           (1,380 points — run_2, not used for plot)
docs/plots/out/10_scaling_timeline.png         (Cloudburst timeline)
```

---

## Consolidated Results (All Runs)

Single reference for all metrics collected across run_1 through run_4. All data from `results/run2/` unless noted.

### Throughput Scaling (64KB state)


| Concurrency | Lambda (inv/s) | Boki (inv/s) | Cloudburst (inv/s) |
| ----------- | -------------- | ------------ | ------------------ |
| c=1         | 20.7           | 42.9         | 25.2               |
| c=10        | 84.0           | 280.5        | 32.6               |
| c=50        | 87.9           | 532.8        | 38.9               |
| c=100       | 86.8           | 665.1        | 62.3               |


### Latency Distribution (64KB state)


| Metric     | Lambda  | Boki    | Cloudburst |
| ---------- | ------- | ------- | ---------- |
| Client P50 | 56.0ms  | 50.9ms  | 142.1ms    |
| Client P95 | 269.5ms | 88.7ms  | 315.2ms    |
| Write P50  | 3,035us | 4,855us | 13,175us   |
| Read P50   | 1,733us | 2us*    | 2,232us    |
| Samples    | 200     | 1,000   | 1,000      |



**Measurement notes:**

- **Boki Read P50 (2us):** This is a local memory access from the engine's in-memory cache (`--slog_engine_enable_cache`), not a shared log read over the network. The engine caches recent log entries; a GET immediately after a PUT to the same key hits this cache. This is by design — the engine is meant to serve hot reads locally — but it means Boki's read latency is not comparable to Lambda's Redis GET (network round-trip ~1.7ms) or Cloudburst's Anna GET (network round-trip ~2.2ms). At 2us, the measurement is also at the edge of `time.time()` precision on Linux (~1us resolution); the true value could be 1-3us. See LIMITATIONS.md L6.

- **Lambda Write variance (912us at c=1 vs 3,035us in latency-dist):** The c=1 throughput test ran after the Redis reboot with `allkeys-lru` and a warm connection pool — Redis was essentially empty and warm. The latency-dist run at c=10 included 9 cold starts out of 200 invocations, which inflate the P50 due to Redis connection pool creation (~23ms per cold start write). Both are real measurements under different conditions; the c=1 value represents best-case warm Lambda+Redis, while the latency-dist value reflects a mixed warm/cold workload.

- **Cloudburst Write range (7,488us–15,589us):** The c=50/c=100 threaded gateway results show lower write latency (7-8ms) than c=1/c=10 (13-15ms). This is counterintuitive and likely reflects the connection pool distributing requests across multiple `CloudburstConnection` instances (each with its own ZMQ sockets and Anna client), which parallelises the Anna KVS routing lookups and data writes. At c=1, a single connection handles all requests sequentially through one ZMQ socket.

- **Cloudburst Client P50 (142ms):** The high E2E latency relative to Boki (51ms) and Lambda (56ms) reflects Cloudburst's longer dispatch path: HTTP gateway → ZMQ → scheduler → executor → Anna KVS → response. Each hop adds latency. The server-side write+read time is ~15ms; the remaining ~127ms is dispatch overhead (ZMQ serialisation, scheduler queueing, executor function loading). See LIMITATIONS.md L1 (measurement point asymmetry) and L8 (HTTP gateway extra hop).

- **Measurement methodology:** All server-side timings (`state_write_lat_us`, `state_read_lat_us`) use `time.time()` inside the benchmark function (Python for Lambda/Cloudburst, Go for Boki), measured in microseconds. Client-side timing uses pycurl timestamps. `time.time()` on Linux has ~1us resolution, so sub-microsecond measurements (like Boki's 2us read) should be interpreted as order-of-magnitude rather than precise values.



Should include network hop to SeBS client <------????

ADAM
1. figure out concrete conclusion for cloudburst having larger figures??????
2. restate -> 4th system to benchmark as a production grade stateful serverless
3. 


### State Size Impact (write P50)


| State Size | Lambda  | Boki    | Cloudburst |
| ---------- | ------- | ------- | ---------- |
| 1 KB       | 1,538us | 3,858us | 11,993us   |
| 64 KB      | 1,846us | 5,176us | 14,248us   |
| 512 KB     | 6,582us | 5,296us | 12,390us   |


### Cold Start


| System     | Type               | Median     | Notes                                                  |
| ---------- | ------------------ | ---------- | ------------------------------------------------------ |
| Lambda     | Container spin-up  | 473ms      | 18 cold starts from run data (`is_cold` flag)          |
| Boki       | Engine restart     | 5,550ms    | 5 restart reps (excluding first warmup: 11,192ms)      |
| Cloudburst | Executor bootstrap | ~180,000ms | Fresh EC2 instance via ASG (git clone + build + start) |


### Scaling Behaviour


| System            | Scale event           | Latency disruption       | Data                       |
| ----------------- | --------------------- | ------------------------ | -------------------------- |
| Lambda            | Transparent (managed) | Cold starts during burst | N/A — managed by AWS       |
| Boki              | Manual 2→3 engines    | None observed (run_2)    | 1,380 points (sparse)      |
| Cloudburst        | Manual 2→3 executors  | None (89ms→90ms)         | 7,020 points (plot 10)     |
| Boki + Cloudburst | Auto-scaling attempt  | Both failed (run_3)      | Application lifecycle gaps |


### State Placement (Cloudburst only)


| Experiment                | Write P50 | Read P50 |
| ------------------------- | --------- | -------- |
| Same key, 1 Anna node     | 13.2ms    | 2.6ms    |
| Unique keys, 1 Anna node  | 13.0ms    | 1.9ms    |
| Same key, 2 Anna nodes    | 14.4ms    | 2.6ms    |
| Unique keys, 2 Anna nodes | 13.3ms    | 1.8ms    |


No measurable benefit — Cloudburst lacks executor-level state caching. See LIMITATIONS.md L11.

### Cost per Unit Work (at c=10)


| System            | Cost per 1,000 invocations | EC2 hourly rate                      |
| ----------------- | -------------------------- | ------------------------------------ |
| Lambda + Redis    | $0.0002                    | Pay-per-use                          |
| Boki              | $0.0008                    | $0.138/hr (3 × t3.medium)            |
| Cloudburst + Anna | $0.0022                    | $0.207/hr (5 × t3.medium + t3.small) |


### Metric Coverage


| Metric                    | Status      | Plot   | Source                              |
| ------------------------- | ----------- | ------ | ----------------------------------- |
| Steady State Throughput   | Collected   | 01     | throughput-c{1,10,50,100}.json      |
| Latency Distribution      | Collected   | 02, 03 | latency-dist.json                   |
| Cost per Unit Work        | Derived     | 07     | postprocess_results.py              |
| Throughput per Resource   | Derived     | —      | throughput / instance cost          |
| State Size Impact         | Collected   | 05     | statesize-{1,64,512}kb.json         |
| State Placement           | Collected   | 09     | placement-*.json (no benefit found) |
| Resource Usage            | Collected   | 08     | cloudwatch_metrics.csv              |
| Cold Start Latency        | Collected   | 06     | cold_start CSVs + run data          |
| Scale-up Interruption     | Collected   | 10     | cloudburst_scaling_timeline.csv     |
| Scale-down Interruption   | Collected   | —      | boki_scaling_down_c10.csv           |
| Scaling to Zero           | Categorical | —      | Lambda: yes, Boki/Cloudburst: no    |
| Worker/Server Distinction | Categorical | —      | Lambda: no, Boki/Cloudburst: yes    |


All 12 target metrics have data. 10 plots in `docs/plots/out/`.

### Plots Index


| #   | File                     | Description                               |
| --- | ------------------------ | ----------------------------------------- |
| 01  | throughput_scaling.png   | Throughput vs concurrency (all 3 systems) |
| 02  | latency_cdf.png          | Cumulative latency distribution           |
| 03  | latency_percentiles.png  | P50/P95/P99 grouped bars                  |
| 04  | write_read_breakdown.png | Write vs read P50 per system              |
| 05  | state_size_impact.png    | Write latency vs state size               |
| 06  | cold_start.png           | Cold start comparison (log scale)         |
| 07  | cost_per_invocation.png  | Cost per 1,000 invocations                |
| 08  | resource_usage.png       | CPU/memory during experiments             |
| 09  | state_placement.png      | Same-key vs unique-key (Cloudburst)       |
| 10  | scaling_timeline.png     | Cloudburst scale-out timeline (3 panels)  |


---

## Latency Drilldown — Edge (Laptop) Decomposition

Decomposes client-side E2E latency into three components using data already collected by `batch_invoke.py`:

```
ClientLatency = NetworkRTT + FunctionExecution + ServerlessOverhead
```

- **NetworkRTT** ≈ `http_startup` (pycurl `PRETRANSFER_TIME` = TCP handshake time). For Lambda this includes TLS negotiation (HTTPS via API Gateway); for Boki/Cloudburst this is plain HTTP to EC2 public IPs.
- **FunctionExecution** = `benchmark` (`end - begin` from function response). Includes state write + state read + compute.
- **ServerlessOverhead** = `client - benchmark - http_startup`. The residual: API Gateway routing, container dispatch, ZMQ/ZK overhead, scheduler queueing, serialization.

**Script:** `scripts/latency_drilldown.py`
**Data source:** `results/run2/` (all experiments, warm invocations only)

### Cross-System Comparison (latency-dist, P50, warm invocations)


| Component            | Lambda  | Boki    | Cloudburst |
| -------------------- | ------- | ------- | ---------- |
| Client E2E           | 55.3ms  | 50.9ms  | 142.1ms    |
| Network RTT          | 23.1ms  | 7.7ms   | 8.2ms      |
| Function execution   | 5.1ms   | 7.6ms   | 19.5ms     |
| Serverless overhead  | 25.5ms  | 35.1ms  | 115.6ms    |


### Percentage Breakdown (P50)


| Component    | Lambda | Boki  | Cloudburst |
| ------------ | ------ | ----- | ---------- |
| % Network    | 42.6%  | 16.9% | 6.0%       |
| % Function   | 8.7%   | 13.7% | 12.7%      |
| % Overhead   | 47.3%  | 66.9% | 81.0%      |


Samples: Lambda=191 (9 cold starts excluded), Boki=1000, Cloudburst=1000.

### Per-System Breakdown (all experiments, P50)


| System     | Experiment              | Client P50 | Network   | Function  | Overhead  |
| ---------- | ----------------------- | ---------- | --------- | --------- | --------- |
| Lambda     | latency-dist            | 55.3ms     | 23.1ms    | 5.1ms     | 25.5ms    |
| Lambda     | throughput-c1           | 45.8ms     | 17.8ms    | 2.1ms     | 24.9ms    |
| Lambda     | throughput-c10          | 50.3ms     | 21.8ms    | 2.3ms     | 24.6ms    |
| Lambda     | throughput-c50          | 54.1ms     | 24.7ms    | 2.1ms     | 25.3ms    |
| Lambda     | throughput-c100         | 68.0ms     | 33.1ms    | 2.2ms     | 29.4ms    |
| Lambda     | statesize-1kb           | 46.9ms     | 20.0ms    | 3.1ms     | 24.0ms    |
| Lambda     | statesize-64kb          | 53.5ms     | 25.9ms    | 4.0ms     | 24.2ms    |
| Lambda     | statesize-512kb         | 59.0ms     | 20.9ms    | 15.4ms    | 23.0ms    |
| Boki       | latency-dist            | 50.9ms     | 7.7ms     | 7.6ms     | 35.1ms    |
| Boki       | throughput-c1           | 22.4ms     | 5.0ms     | 6.4ms     | 11.1ms    |
| Boki       | throughput-c10          | 27.3ms     | 5.9ms     | 5.4ms     | 13.6ms    |
| Boki       | throughput-c50          | 45.7ms     | 7.2ms     | 7.5ms     | 32.6ms    |
| Boki       | throughput-c100         | 82.9ms     | 8.3ms     | 8.7ms     | 62.8ms    |
| Boki       | statesize-1kb           | 49.0ms     | 6.5ms     | 7.2ms     | 37.9ms    |
| Boki       | statesize-64kb          | 56.9ms     | 9.8ms     | 7.2ms     | 36.5ms    |
| Boki       | statesize-512kb         | 56.3ms     | 8.0ms     | 8.8ms     | 41.7ms    |
| Cloudburst | latency-dist            | 142.1ms    | 8.2ms     | 19.5ms    | 115.6ms   |
| Cloudburst | throughput-c1           | 38.0ms     | 6.0ms     | 21.6ms    | 9.8ms     |
| Cloudburst | throughput-c10          | 145.6ms    | 6.8ms     | 20.9ms    | 119.4ms   |
| Cloudburst | throughput-c50-threaded | 412.2ms    | 8.8ms     | 12.6ms    | 357.7ms   |
| Cloudburst | throughput-c100-threaded| 867.0ms    | 11.4ms    | 13.1ms    | 555.1ms   |
| Cloudburst | statesize-1kb           | 145.3ms    | 8.1ms     | 18.7ms    | 117.1ms   |
| Cloudburst | statesize-64kb          | 153.5ms    | 9.0ms     | 21.5ms    | 122.7ms   |
| Cloudburst | statesize-512kb         | 154.5ms    | 8.0ms     | 19.9ms    | 120.1ms   |


### Observations

1. **Lambda has the highest network RTT (23ms vs ~8ms)** because it routes through API Gateway (HTTPS with TLS handshake), while Boki/Cloudburst use plain HTTP to EC2 public IPs. The TCP+TLS handshake is ~3x more expensive than plain TCP.

2. **Serverless overhead dominates for all systems**, but especially Cloudburst (115ms = 81% of client latency). This is the HTTP→ZMQ→scheduler→executor dispatch chain — the "invisible cost" of Cloudburst's multi-hop architecture.

3. **Boki's overhead (35ms) exceeds Lambda's (25ms)** despite being self-hosted. This is the gateway's HTTP parsing + ZK-based engine dispatch + response serialization.

4. **Function execution is small for all systems** (5-20ms). The state operations themselves (write+read+compute) are not the bottleneck — the dispatch/routing layer is.

5. **Cloudburst overhead scales with concurrency:** 9.8ms at c=1 → 115ms at c=10 → 555ms at c=100. This is scheduler queueing contention — the single-threaded scheduler serializes all dispatch decisions.

6. **Lambda overhead is remarkably stable (~24-29ms)** across all concurrency levels. This is the API Gateway + container routing cost — a fixed overhead that doesn't grow with load because Lambda dispatches requests in parallel to independent containers.

7. **Boki overhead grows under load** (11ms at c=1 → 63ms at c=100) but less than Cloudburst. The gateway dispatches to a fixed pool of engines; at high concurrency, engine-level queueing increases.

### Measurement Caveat

`http_startup` (pycurl `PRETRANSFER_TIME`) measures time from connection start through TCP handshake (and TLS for HTTPS). It is a good proxy for network RTT but not identical to ICMP `ping`. For Lambda (HTTPS), it includes TLS negotiation overhead that is not purely network latency. For Boki/Cloudburst (HTTP), it closely approximates the TCP round-trip time.

### Next Step

Run the same benchmarks from EC2 instances inside each system's VPC (cloud-to-cloud) to eliminate network RTT and isolate the serverless overhead. This will show what microservice-to-function latency looks like versus edge-to-function latency. See `NEXT_STEPS.md` Phase B–D.
