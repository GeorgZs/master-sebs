
## Benchmark Applications

| Type 		   | Benchmark           | Languages          | Architecture       |  Description |
| :---         | :---:               | :---:              | :---:                | :---:                |
| Webapps      | 110.dynamic-html    | Python, Node.js    | x64, arm64 | Generate dynamic HTML from a template. |
| Webapps      | 120.uploader    | Python, Node.js    | x64, arm64 | Uploader file from provided URL to cloud storage. |
| Webapps      | 130.crud-api    | Python    | x64, arm64 | Simple CRUD application using NoSQL to store application data. |
| Multimedia      | 210.thumbnailer    | Python, Node.js    | x64, arm64 | Generate a thumbnail of an image. |
| Multimedia      | 220.video-processing    | Python    | x64, arm64 | Add a watermark and generate gif of a video file. |
| Utilities      | 311.compression    | Python   | x64, arm64 | Create a .zip file for a group of files in storage and return to user to download. |
| Inference      | 411.image-recognition    | Python    | x64 | Image recognition with ResNet and pytorch. |
| Scientific      | 501.graph-pagerank    | Python    | x64, arm64 | PageRank implementation with igraph. |
| Scientific      | 502.graph-mst    | Python    | x64, arm64 | Minimum spanning tree (MST)  implementation with igraph. |
| Scientific      | 503.graph-bfs    | Python    | x64, arm64 | Breadth-first search (BFS) implementation with igraph. |
| Scientific      | 504.dna-visualisation    | Python   | x64, arm64 | Creates a visualization data for DNA sequence. |
| Stateful        | 900.baseline-lambda-redis | Python  | x64 | Lambda + ElastiCache Redis stateful benchmark (SET/GET + compute). |
| Stateful        | 900.cloudburst-stateful   | Python  | x64 | Native Cloudburst executor with Anna KVS (put/get + compute). |
| Stateful        | 900.boki-shared-log       | Go      | x64 | Boki shared log benchmark via Go binary (Python stub is dead code). |

Below, we discuss the most important implementation details of each benchmark. For more details on benchmark selection and their characterization, please refer to [our paper](../README.md#publication).

> [!NOTE] 
> Benchmarks whose number starts with the digit 0, such as `020.server-reply` are internal microbenchmarks used by specific experiments. They are not intended to be directly invoked by users.

> [!NOTE] 
> ARM architecture is supported on AWS Lambda only.

> [!WARNING] 
> Benchmark 411.image-recognition contains PyTorch which is often too large to fit into a code package. Up to Python 3.7, we can directly ship the dependencies. For Python 3.8, we use an additional zipping step that requires additional setup during the first run, making cold invocations slower. Warm invocations are not affected.

> [!WARNING] 
> Benchmark `411.image-recognition` does not work on AWS with Python 3.9 due to excessive code size. While it is possible to ship the benchmark by zipping `torchvision` and `numpy` (see `benchmarks/400.inference/411.image-recognition/python/package.sh`), this significantly affects cold startup. On the lowest supported memory configuration of 512 MB, the cold startup can reach 30 seconds, making HTTP trigger unusable due to 30 second timeout of API gateway. In future, we might support Docker-based deployment on AWS that are not affected by code size limitations.

> [!WARNING] 
> Benchmark `411.image-recognition` does not work on GCP with Python 3.8+ due to excessive code size. To the best of our knowledge, there is no way of circumventing that limit, as Google Cloud offers neither layers nor custom Docker images.

## Webapps

### Dynamic HTML

The benchmark represents a dynamic generation of webpage contents through a serverless function. It generates an HTML from an existing template, with random numbers inserted to control the output. It uses the `jinja2` and `mustache` libraries on Python and Node.js, respectively.

### Uploader

The benchmark implements the common workflow of uploading user-defined data to the persistent cloud storage. It accepts a URL, downloads file contents, and uploads them to the storage. Python implementation uses the standard library `requests`, while the Node.js version uses the third-party `requests` library installed with `npm`.

### CRUD API

The benchmark implements a simple CRUD application simulating a webstore cart. It offers three basic methods: add new item (`PUT`), get an item (`GET`), and query all items in a cart. It uses the NoSQL storage, with each item stored using cart id as primary key and item id as secondary key. The Python implementation uses 
cloud-native libraries to access the database.

## Multimedia

### Thumbnailer

This benchmark implements one of the most common functions implemented with serverless functions. It downloads an image from the cloud storage, resizes it to a thumbnail size, uploads the new smaller version to the cloud storage, and returns the location to the caller, allowing them to insert the newly created thumbnail. To resize the image, it uses the `Pillow` and `sharp` libraries on Python and Node.js, respectively.

### Video Processing

The benchmark implements two operations on video files: adding a watermark and creating a gif. Both input and output media are passed through the cloud storage. To process the video, the benchmark uses `ffmpeg`. The benchmark installs the most recent static binary of `ffmpeg` provided by [John van Sickle](https://johnvansickle.com/ffmpeg/).

## Utilities

### Compression

The benchmark implements a common functionality of websites managing file operations - gather a set of files in cloud storage, compress them together, and return a single archive to the user.
It implements the .zip file creation with the help of the `shutil` standard library in Python.

## Inference

### Image Recognition

The benchmark is inspired by MLPerf and implements image recognition with Resnet50. It downloads the input and model from the storage and uses the CPU-only `pytorch` library in Python.

## Scientific

### Graph PageRank, BFS, MST

The benchmark represents scientific computations offloaded to serverless functions. It uses the `python-igraph` library to generate an input graph and process it with the selected algorithm.

### DNA Visualization

This benchmark is inspired by the [DNAVisualization](https://github.com/Benjamin-Lee/DNAvisualization.org) project and it implements processing the `.fasta` file with the `squiggle` Python library.

## Stateful Benchmarks (900.stateful)

The `900.stateful` benchmark suite compares stateful serverless runtimes. Each benchmark performs a configurable KV state read/write plus lightweight compute and returns standardised timing in the SeBS `ExecutionResult` format (`request_id`, `is_cold`, `begin`, `end`, `measurement`).

For an architectural overview of all three systems, see [diagrams/three\_system\_comparison.puml](diagrams/three_system_comparison.puml).

State size tiers: `test` = 1 KB, `small` = 64 KB, `large` = 512 KB.

| Benchmark | System | State Backend | Invocation Path |
|-----------|--------|---------------|-----------------|
| `baseline-lambda-redis` | AWS Lambda | ElastiCache Redis | HTTP via API Gateway → Lambda → Redis `SET`/`GET` |
| `cloudburst-stateful` | Cloudburst | Anna KVS | Native Cloudburst executor via `cloudburst.put()`/`cloudburst.get()` |
| `boki-shared-log` | Boki | Shared log (slib) | Go binary via Boki gateway HTTP (Python stub is dead code) |

### Baseline Lambda + Redis

Deployed via Terraform (`integrations/baseline/aws/`). The benchmark function (`function.py`) uses a module-level `redis.ConnectionPool` for connection reuse across warm Lambda invocations. Cold-start detection uses a module-level `_is_cold` flag set on first import. The Terraform-deployed Lambda handler (`integrations/baseline/aws/lambda/handler.py`) is a thin wrapper that parses API Gateway events and calls the benchmark function.

**Infrastructure:** ElastiCache Redis (cluster mode disabled) in the same VPC as Lambda. Redis endpoint is injected via `REDIS_HOST`/`REDIS_PORT` environment variables (set by Terraform).

### Cloudburst Stateful

Deployed via Terraform (`integrations/cloudburst/aws/`). The benchmark function follows the Cloudburst executor convention: `def stateful_benchmark(cloudburst, state_key, state_size_kb, ops, request_id)` where `cloudburst` is the user\_library object injected by the executor.

**Architecture:** Cloudburst uses a Scheduler + Executor + Anna KVS topology. The scheduler dispatches function calls to executors via ZMQ. Executors run the benchmark function and access state through the `CloudburstUserLibrary` which wraps Anna KVS operations. See [diagrams/cloudburst\_architecture.puml](diagrams/cloudburst_architecture.puml) for the full deployment diagram and [diagrams/cloudburst\_benchmark\_flow.puml](diagrams/cloudburst_benchmark_flow.puml) for the per-invocation sequence.

**Anna KVS dependency:** Cloudburst requires [Anna KVS](https://github.com/hydro-project/anna) (a C++ distributed KVS) as its state backend. Anna is deployed as Docker containers on a dedicated EC2 node (routing + KVS + monitor processes). In single-node benchmarking mode, Cloudburst uses `local=True` which bypasses Anna's routing tier and talks directly to the KVS on port 6450.

**Key patches applied to upstream Cloudburst ([hydro-project/cloudburst](https://github.com/hydro-project/cloudburst)):**
- `executor/server.py`: read `anna.private_ip` from config instead of hardcoding `127.0.0.1` in local mode.
- `client/run_benchmark.py`: accept `CLOUDBURST_LOCAL=true` env var for remote single-node Anna deployments.
- `server/benchmarks/stateful.py`: new benchmark module for SeBS-compatible stateful workload.

A benchmark runner module (`master-cloudburst/cloudburst/server/benchmarks/stateful.py`) registers the function with the Cloudburst scheduler and runs it via `CloudburstConnection`. It is invoked as:

```bash
CLOUDBURST_LOCAL=true STATE_SIZE_KB=64 python3 cloudburst/client/run_benchmark.py stateful <scheduler_ip> <num_requests> <client_ip>
```

Or via the integration runner:

```bash
CLOUDBURST_LOCAL=true STATE_SIZE_KB=64 ./integrations/cloudburst/run_cloudburst_bench.sh stateful 200
```

Output is parsed by `collect_cloudburst_results.py` and normalized via `cloudburst_to_common_schema.py`.

**Preliminary results (64KB state, 5 invocations):** E2E median 21ms, scheduler overhead ~1ms, KVS latency ~20ms. See [PRELIM\_RESULTS.md](../../PRELIM_RESULTS.md) for full data.

### Boki Shared Log

The Python stub in `boki-shared-log/python/function.py` is **dead code** — Boki's shared log API (`BokiStore`, `BokiQueue` in `slib/lib.go`) is Go-only. The real benchmark is a Go binary registered with the Boki Launcher. SeBS sends HTTP requests to the Boki gateway; the Go function handles log operations and returns a JSON response.

## Serverless Workflows

**(WiP)** Coming soon!

## Applications

**(WiP)** Coming soon!

