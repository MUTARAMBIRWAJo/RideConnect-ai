# Enterprise Benchmark Results

Date: 2026-03-09
Target under test: `rideconnect-platform` gateway dispatch flow (`POST /v1/rides/request`)

## Test Tool
- `rideconnect-platform/tools/load_test_gateway.py`

## Configurations and Results

1. Baseline (single-worker gateway/services, no replica scaling)
- Requests: 120
- Concurrency: 20
- Success: 120/120
- RPS: 30.74
- p50: 538.16 ms
- p95: 1409.46 ms
- p99: 1443.44 ms

2. Gateway optimized (cached city configs + shared client)
- Requests: 120
- Concurrency: 20
- Success: 120/120
- RPS: 38.36
- p50: 394.10 ms
- p95: 1305.31 ms
- p99: 1417.69 ms

3. Multi-worker + scaled replicas (3x dispatch/eta/pricing, 2 workers each), fair-load retest
- Requests: 120
- Concurrency: 20
- Success: 120/120
- RPS: 55.66
- p50: 239.41 ms
- p95: 1125.87 ms
- p99: 1213.15 ms

4. Bounded-latency gateway (timeout budgets + partial response), scaled topology
- Requests: 120
- Concurrency: 20
- Success: 120/120
- RPS: 57.14
- p50: 228.85 ms
- p95: 1110.42 ms
- p99: 1155.67 ms

5. Coalescing + short-lived cache + health counters
- Requests: 120
- Concurrency: 20
- Success: 120/120
- RPS: 49.85
- p50: 255.35 ms
- p95: 1227.71 ms
- p99: 1361.31 ms

6. Redis-backed shared cache/coalescing (cross-worker)
- Requests: 120
- Concurrency: 20
- Success: 120/120
- RPS: 47.13
- p50: 274.45 ms
- p95: 1309.02 ms
- p99: 1365.45 ms

7. Hot-key benchmark (highly repetitive identical requests)
- Requests: 80
- Success: 80/80
- RPS: 161.93

## Notes
- Throughput improved by ~81% from baseline (30.74 -> 55.66 RPS).
- Median latency improved by ~56% (538 ms -> 239 ms).
- Tail latency (p95/p99) improved but remains above 1 second under this synthetic environment.
- Heavier-load test (240 requests / concurrency 40) shows higher tail variance, indicating gateway orchestration and downstream queueing effects remain the key bottleneck areas.
- Partial-response behavior now protects gateway latency under dependency slowness while preserving successful ride-request handling.
- In multi-worker gateway mode, cache/coalescing are process-local and therefore do not guarantee high cache-hit rates across all requests.
- With Redis-enabled shared cache/lock, coalescing works across workers. The biggest gains appear in repetitive/hot-key traffic; random payload traffic can see modest overhead from distributed coordination.
