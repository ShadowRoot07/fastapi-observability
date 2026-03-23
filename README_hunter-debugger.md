# 🔍 Core Observability & Performance Fixes (Security & Logic Audit)

This PR addresses several architectural flaws and "glitches" identified during deep-dive testing on **Python 3.13** using `siege` and `locust`. These fixes ensure the observability stack remains reliable under high concurrency and prevents "blind spots" in Grafana dashboards.

---

## 🛠️ Identified Issues & Fixes

### 1. Event Loop Blocking (Asynchronous Bottleneck)
* **Glitch:** The use of `time.sleep()` within `async def` endpoints (`/io_task`, `/random_sleep`).
* **Root Cause:** Synchronous blocking calls in FastAPI/Starlette freeze the entire event loop.
* **Impact:** Under concurrent load (as seen in `request-script.sh`), the process hangs, causing massive artificial latency and preventing other requests from being processed.
* **Fix:** Replaced with `await asyncio.sleep()`.

### 2. Load Testing Logic Failure (Task Shadowing)
* **Glitch:** Duplicated method names in `locustfile.py`.
* **Impact:** In Python, the second definition of `random_sleep` overrides the first. This meant the actual "sleep" scenario was never executed during load tests, leading to false performance results.
* **Fix:** Renamed tasks to unique identifiers.

### 3. Fragile Log Parsing (Observability Blind Spots)
* **Glitch:** High dependency on the `| pattern` operator in Loki queries (`dashboard.json`).
* **Impact:** Critical errors (like Python Tracebacks or Crashes) that don't follow the exact Uvicorn format are ignored by the dashboard. This creates a "False Negative" where the system looks healthy while failing.
* **Fix:** Updated queries to be more resilient to non-standard log formats.

### 4. Version Instability & Security
* **Glitch:** Mismatch between stable OTel SDKs and Beta-stage instrumentations (`0.54b0`).
* **Security Risk:** The Tempo gRPC receiver was listening on `0.0.0.0` without encryption, exposing the telemetry port.
* **Fix:** Pinning stable versions and restricting Tempo listener to internal networks where applicable.

---

## 🚀 How to Verify
1. Run `siege -c 5 -r 10 http://localhost:8000/random_sleep`.
2. Check the **PR 99 Requests Duration** panel in Grafana.
3. Observe that the event loop no longer blocks and the logs are correctly captured even during simulated failures.

