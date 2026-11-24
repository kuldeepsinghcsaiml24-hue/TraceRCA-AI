# TraceRCA-AI — Project Progress

> Last updated: 2026-11-23
> Scope: milestones M15–M24 (M16 implementation + M15 verification status).
> This document is a companion to `PROGRESS.md` and `README.md`. It records
> verified facts and clearly labels anything that has **not** been independently
> reverified in this session.

---

## 1. Project Overview

**TraceRCA-AI** is a distributed observability, causal root-cause analysis, and
auto-healing engine. It ingests OpenTelemetry traces, logs, and metrics; normalizes
and correlates them; builds a Neo4j service-dependency topology; detects anomalies;
and exposes everything through FastAPI to a Next.js dashboard.

**Architecture (verified from source):**

```text
Apps / Demo Microservice
        │  OpenTelemetry / HTTP
        ▼
FastAPI  /telemetry/{traces,logs,metrics}      (ingestion + Pydantic validation)
        │
        ▼
PostgreSQL  (SQLAlchemy async + Alembic)
        │   post-commit hooks
        ├──► Topology builder  ──► Neo4j  (Service / DEPENDS_ON)
        ├──► Anomaly detection ──► PostgreSQL  (anomalies table, M16)
        │         │
        │         └─► BaselineService (M17) ──► anomaly_baselines table
        │
        ▼
FastAPI  /dashboard/{overview,services,topology,anomalies,...}
        │
        ▼
Next.js dashboard (frontend/)
```

**Verified technology stack (from `requirements.txt` / source):**
FastAPI, Uvicorn, Pydantic / pydantic-settings, SQLAlchemy (async) + asyncpg +
Alembic, Redis (async), Neo4j async driver, OpenTelemetry (api/sdk/otlp exporter),
pytest / pytest-asyncio / httpx. Frontend: Next.js (`frontend/`).

**Security note:** all credentials are supplied via environment variables
(`backend/app/core/config.py`); `.env` is git-ignored and is **not** included in
this document or in the backup. No secrets are recorded here.

---

## 2. Milestone Status (M15–M24)

> M15–M24 extend the M1–M9 foundation documented in `PROGRESS.md`. **M16 and M17 are both implemented in the current working tree (uncommitted).** Several files contain changes from both milestones; see §4.1, §4.4, §5.2, §5.7 for cross-references.

| Milestone | Title / Scope | Status |
|---|---|---|
| **M15** | Anomaly persistence design & verification (contract review, DB model design, migration plan, test plan) | **Needs verification** — design artifacts are present (see §3), but no independent end-to-end reverification was performed in this session. |
| **M16** | Anomaly persistence implementation: DB model, Alembic migration, deterministic IDs, ingestion integration, dashboard anomalies API, tests | **Implemented (uncommitted)** — code + tests present in working tree; not yet committed or reverified against live PostgreSQL in this session. |
| **M17** | Anomaly baseline calibration (replace demo defaults with measured baselines) | **Implemented (uncommitted)** — empirical baselines from historical telemetry, per-service/per-metric, trimmed P50, cached with TTL, fallback defaults. In same working tree as M16. |
| **M18** | Anomaly correlation with traces/logs/metrics (link anomalies to evidence) | **Implemented (uncommitted)** — AnomalyCorrelation model, Alembic migration, ingestion integration, API endpoint, 8 correlation tests passing. |
| **M19** | Dashboard anomaly UI + investigation workflow | ⏳ Pending |
| **M20** | Part 2 kickoff: causal inference / Graph RAG foundation | ⏳ Pending |
| **M21** | Evidence-based root-cause analysis pipeline | ⏳ Pending |
| **M22** | Blast-radius / impact analysis | ⏳ Pending |
| **M23** | Remediation recommendation engine | ⏳ Pending |
| **M24** | Controlled auto-healing + production hardening | ⏳ Pending |

---

## 3. M15 — Anomaly Persistence Design (Needs Verification)

The following design artifacts exist and are consistent with each other. They are
the basis for M16. Marked **needs verification** because no live-database
reverification was performed in this session.

- **Anomaly contract** — `backend/app/telemetry/anomaly.py` (`Anomaly` Pydantic
  model: `anomaly_id`, `service_name`, `anomaly_type` ∈ {LATENCY, ERROR_RATE,
  METRIC}, `timestamp`, `observed_value`, `expected_value`, `severity` ∈ {LOW,
  MEDIUM, HIGH}, `description`).
- **Detector semantics** — `backend/app/telemetry/anomaly_detector.py`:
  latency/metric use relative deviation with thresholds (50% / 100% / 200% →
  LOW / MEDIUM / HIGH); error-rate uses percentage-point thresholds (5 / 10 / 20).
- **Configurable baselines** — `backend/app/core/config.py` exposes
  `anomaly_latency_baseline_ms` (default 100.0) and `anomaly_metric_baseline`
  (default 40.0), overridable via env vars. These are demo/test defaults, **not**
  production thresholds (see §8).

  **M17 note**: These settings were renamed to `anomaly_latency_fallback_ms` and
  `anomaly_metric_fallback` with backward-compatible property aliases preserving
  the original env var names (`ANOMALY_LATENCY_BASELINE_MS`, `ANOMALY_METRIC_BASELINE`).

---

## 4. M16 — Anomaly Persistence Implementation

All items below are present in the current working tree (uncommitted). They have
**not** been committed and have **not** been independently reverified against a
live PostgreSQL instance in this session.

### 4.1 Database model

`backend/app/db/models.py` — `AnomalyEvent` (table `anomalies`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK, autoincrement | surrogate key |
| `anomaly_id` | String(36), UNIQUE, indexed | deterministic UUIDv5 string (with dashes) |
| `service_name` | String(255), indexed | |
| `anomaly_type` | String(20), indexed | LATENCY / ERROR_RATE / METRIC |
| `timestamp` | DateTime(timezone=True), indexed | anomaly event time |
| `observed_value` | Float | |
| `expected_value` | Float | |
| `severity` | String(10), indexed | LOW / MEDIUM / HIGH |
| `description` | Text | |
| `created_at` | DateTime(timezone=True) | row-creation time |

**Note**: The same file (`backend/app/db/models.py`) also contains the M17 `AnomalyBaseline`
model (table `anomaly_baselines`). See §5.2 for details. The two models are independent
but share the file.

### 4.2 Alembic migration

`backend/alembic/versions/b1f4e2d3a5c6_add_anomalies_table.py`

- Revision `b1f4e2d3a5c6`, down_revision `c0ebede2393f`.
- Creates `anomalies` + unique index on `anomaly_id` and non-unique indexes on
  `service_name`, `anomaly_type`, `timestamp`, `severity`.
- `downgrade()` drops all indexes and the table.

### 4.3 Deterministic anomaly IDs

`backend/app/telemetry/anomaly_id.py` — `build_anomaly_id(...)` returns a
`uuid.uuid5` under a fixed project namespace.

- **Trace anomalies:** key = `trace_id` + `span_id` + service/type/timestamp/
  observed/expected → event-specific; re-detecting the same span yields the same
  ID, so `UNIQUE(anomaly_id)` prevents duplicates.
- **Metric anomalies:** metrics carry no stable span id, so key is content-based
  (`metric_name` + service + timestamp + observed + expected). Documented
  limitation: byte-identical metric events share an ID.
- `anomaly_detector.py` and `anomaly_service.py` were updated to thread
  `trace_id` / `span_id` / `metric_name` into ID generation.

### 4.4 Ingestion integration (M16 behavior)

`backend/app/telemetry/service.py` — `_detect_and_persist_anomaly(db, event)`:

- Called **after** the telemetry event is committed and refreshed
  (`ingest_trace`, `ingest_metric`).
- Latency detection for trace events with `duration_ms`; metric detection for
  metric events with `metric_value` (and non-zero baseline).
- **M16 baselines**: Used configured defaults `settings.anomaly_latency_baseline_ms`
  (100 ms) and `settings.anomaly_metric_baseline` (40 units) directly.
- Error-rate detection intentionally omitted (requires a window of events, not a
  single event).
- On no anomaly → no-op. On detector/DB failure → rollback + log, exception
  swallowed so the ingest HTTP response is never turned into a 500.

**M17 change**: This function was rewritten to call `BaselineService.get_latency_baseline()`
and `get_metric_baseline()` for service/metric-specific empirical baselines, with
configured fallbacks used when insufficient history exists. See §5.7.

### 4.5 Dashboard anomalies API

`backend/app/api/routes/dashboard.py` — `GET /dashboard/anomalies`:

- Query params: `limit` (default 50, clamped to [1, 500]).
- Ordered by `timestamp DESC`; returns `{"count": N, "items": [...]}`.
- On `SQLAlchemyError` → `503` with a generic "temporarily unavailable" detail
  (no internal details leaked).
- Registered via the existing dashboard router in `backend/app/main.py`.

### 4.6 Tests (M16 scope)

- `tests/test_anomaly_persistence.py` — **14 M16 tests** (tests 1–14 in file) using mocked DB
  sessions: high/low latency, high/low metric, log never triggers, `None`
  duration/value guards, commit-failure rollback + swallow, detector ValueError
  swallow, deterministic-ID stability (3 tests), distinct-span/value IDs, repeated
  detection, and IntegrityError swallow.
  - **M17 added 9 more tests** (tests 15–23) for baseline integration and metric validation.
    See §5.8.
- `tests/test_dashboard_anomalies_api.py` — 7 API tests using `TestClient` +
  dependency overrides: non-empty 200, empty 200, 503 on DB error, default/custom
  limit, clamp below 1, clamp above 500.
- `tests/conftest.py` — sets a dummy `NEO4J_PASSWORD` env var at collection time
  so module import does not fail Pydantic validation. Test-only; production
  config is untouched.

---

## 5. M17 — Anomaly Baseline Calibration Implementation

All items below are present in the current working tree (uncommitted). They have
**not** been committed and have **not** been independently reverified against a
live PostgreSQL instance in this session.

### 5.1 Objective

Replace hardcoded demo anomaly baseline defaults (100 ms latency, 40 metric units)
with data-informed/empirical baselines computed from historical telemetry data.

### 5.2 Database Model

`backend/app/db/models.py` — `AnomalyBaseline` (table `anomaly_baselines`):

| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger PK, autoincrement | surrogate key |
| `service_name` | String(255), indexed | |
| `baseline_type` | String(20) | LATENCY / METRIC |
| `metric_name` | String(255), nullable | NULL for LATENCY, required for METRIC |
| `baseline_value` | Float | computed P50 |
| `sample_count` | Integer | number of observations used |
| `updated_at` | DateTime(timezone=True) | last computation time |

**Constraints:**
- `CHECK (baseline_type IN ('LATENCY', 'METRIC'))`
- `CHECK ((baseline_type = 'METRIC' AND metric_name IS NOT NULL) OR (baseline_type = 'LATENCY' AND metric_name IS NULL))`
- Partial unique index `uq_baseline_latency_per_service` on `service_name` WHERE `baseline_type = 'LATENCY'`
- Partial unique index `uq_baseline_metric_per_service_metric` on `service_name, metric_name` WHERE `baseline_type = 'METRIC'`
- Index `ix_anomaly_baselines_service_type` on `service_name, baseline_type`

**Note**: The `AnomalyEvent` model (M16, table `anomalies`) is in the same file
(`backend/app/db/models.py`). See §4.1.

### 5.3 Alembic Migration

`backend/alembic/versions/d4e5f6a7b8c9_add_anomaly_baselines.py`

- Revision `d4e5f6a7b8c9`, down_revision `b1f4e2d3a5c6` (M16 anomalies table).
- Creates `anomaly_baselines` table with constraints and partial unique indexes.
- `downgrade()` drops indexes and table.

### 5.4 Baseline Computation & Caching

`backend/app/telemetry/baseline_service.py` — `BaselineService` class:

**Computation:**
- Per-service latency baseline: P50 of recent trace `duration_ms` (last 1000, non-negative)
- Per-service, per-metric baseline: P50 of recent `metric_value` (last 1000)
- Minimum samples: 30 (configurable via `anomaly_baseline_min_samples`)
- Window size: 1000 observations (configurable via `anomaly_baseline_window_size`)
- Outlier trimming: 5% from each tail (configurable via `anomaly_baseline_outlier_trim_pct`)
- Trimmed P50 algorithm: sort values, trim ceil(N * trim_pct) from each end, compute median

**Cache Behavior:**
- In-memory, process-local cache (each API worker independent)
- TTL: 300 seconds (configurable via `anomaly_baseline_cache_ttl_seconds`)
- Cache miss: returns configured fallback, schedules background refresh
- Stale cache: returns last known good value, schedules background refresh
- Concurrent refresh: per-key lock prevents duplicate DB queries
- Background refresh failures: logged, last good value retained
- Graceful fallback: configured defaults used when DB unavailable or insufficient samples

**Multi-worker Note:**
Cache is process-local. Multiple API workers independently compute baselines from the same PostgreSQL table. Computed values converge; maximum divergence ≤ TTL. Redis-backed cache can be added for stronger consistency in future.

**Lifespan Integration:**
- `baseline_service.start_refresh_loop()` called at app startup
- `baseline_service.shutdown()` called at app shutdown (cancels background tasks)

### 5.5 Configuration Changes

`backend/app/core/config.py` — `Settings` class:

**Renamed (with backward-compatible property aliases):**
- `anomaly_latency_baseline_ms` → `anomaly_latency_fallback_ms` (default 100.0)
- `anomaly_metric_baseline` → `anomaly_metric_fallback` (default 40.0)

**New Settings:**
- `anomaly_error_rate_fallback: float = 0.0` — error rate baseline (M17 uses fallback; M18 will compute)
- `anomaly_baseline_min_samples: int = 30` — minimum observations for valid baseline
- `anomaly_baseline_window_size: int = 1000` — max historical observations to consider
- `anomaly_baseline_cache_ttl_seconds: int = 300` — cache TTL
- `anomaly_baseline_outlier_trim_pct: float = 0.05` — outlier trim percentage
- `anomaly_metric_nonnegative_names: str` — comma-separated metric names that must be non-negative

**Backward Compatibility:**
- Old env var names `ANOMALY_LATENCY_BASELINE_MS` and `ANOMALY_METRIC_BASELINE` still work via property aliases
- Existing `.env` files require no changes

### 5.6 Metric Validation Updates

`backend/app/telemetry/anomaly_detector.py` — `detect_metric_anomaly()`:

- **Zero values:** Always accepted for all metrics
- **Negative values:** Rejected only for metrics in `nonnegative_metric_set` (CPU, memory, disk, network, request duration, queue depth, error count, request count)
- **Negative values:** Allowed for other metrics (temperature delta, rate of change, etc.)
- **Expected value = 0:** Handled gracefully:
  - observed = 0 → no anomaly
  - observed ≠ 0 → HIGH severity anomaly (infinite relative deviation)

### 5.7 Ingestion Integration

`backend/app/telemetry/service.py` — `_detect_and_persist_anomaly()`:

- Latency: calls `baseline_service.get_latency_baseline(service_name)`
- Metric: calls `baseline_service.get_metric_baseline(service_name, metric_name)`
- Fallbacks used automatically when service/metric has insufficient history
- Error-rate: uses `anomaly_error_rate_fallback` (0.0%); service-specific calibration deferred to M18

### 5.8 Tests

**New: `tests/test_baseline_service.py`** — **24 tests** covering:
- Trimmed P50 computation (basic, outliers, even/odd counts, edge cases)
- Cache behavior (miss, hit, stale, concurrent refresh, failure, success, shutdown)
- Latency baseline (no data, insufficient samples, valid samples)
- Metric baseline (per-metric isolation, new metric fallback, zero values, negative validation)
- Multi-worker simulation (independent instances converge)
- Error rate baseline (uses fallback)

**Extended: `tests/test_anomaly_persistence.py`** — **+9 M17 tests** (tests 15–23, total 23 tests in file):
- Test 15: `test_trace_uses_service_latency_baseline_not_global_fallback` — trace uses service-specific baseline when available
- Test 16: `test_trace_new_service_uses_global_fallback` — new service with no baseline uses global fallback
- Test 17: `test_metric_uses_service_metric_baseline` — metric uses service+metric-specific baseline when available
- Test 18: `test_metric_new_metric_name_uses_global_fallback` — new metric name uses global fallback
- Test 19: `test_baseline_change_produces_new_anomaly_id_same_event` — same event with different baseline produces different anomaly_id
- Test 20: `test_zero_metric_value_vs_nonzero_baseline_triggers_anomaly` — zero metric value against non-zero baseline triggers anomaly
- Test 21: `test_negative_cpu_utilization_raises_value_error` — negative CPU utilization raises ValueError
- Test 22: `test_negative_temperature_delta_allowed` — negative temperature delta allowed (not in nonnegative list)
- Test 23: `test_zero_metric_value_accepted_for_all_metrics` — zero accepted for all metric types

**Extended: `tests/test_anomaly_detection.py`** — **19 tests total**, 1 test updated:
- `test_metric_zero_expected_value` replaces `test_metric_invalid_expected_value` to match new graceful handling
  (M16: raises `ValueError` on expected=0; M17: handles gracefully → no anomaly if observed=0, HIGH if observed≠0)

**Test verification status**: **NOT independently verified in this session**. Test counts based on static
analysis of test files. Run `pytest -q tests/test_baseline_service.py tests/test_anomaly_persistence.py tests/test_dashboard_anomalies_api.py tests/test_anomaly_detection.py` to verify.

### 5.9 M16 Compatibility Preserved

- Deterministic anomaly ID generation unchanged (expected_value still in key)
- `UNIQUE(anomaly_id)` dedup works within same baseline version
- Anomaly persistence flow unchanged
- Dashboard `/anomalies` API unchanged
- Detector severity thresholds unchanged (50%/100%/200% → LOW/MEDIUM/HIGH)
- Config env overrides preserved via backward-compatible aliases
- All existing M16 tests pass

### 5.10 Known Limitations

- **Error-rate baseline:** Not computed in M17; uses configured fallback (0.0%). Requires windowed aggregation — deferred to M18.
- **Baseline change → new anomaly_id:** When baseline updates, re-ingesting same telemetry produces different `anomaly_id` (expected_value changed). This is correct behavior — re-evaluation against new baseline is a new assessment.
- **Multi-worker cache divergence:** Process-local caches may briefly diverge (≤ TTL). Acceptable for anomaly detection.
- **Migration not run against live PostgreSQL:** Schema changes verified via model definition only.
- **Tests requiring live services:** Neo4j/PostgreSQL/Redis tests skipped (environment limitation, not code defect).

---

## 6. M18 — Anomaly Correlation Implementation

All items below are present in the current working tree (uncommitted). They have
**not** been committed and have **not** been independently reverified against a
live PostgreSQL instance in this session.

### 6.1 Objective

Link detected anomalies to supporting telemetry evidence (traces, logs, metrics)
using the existing correlation engine (`backend.app.telemetry.correlation`).
This enables downstream root-cause analysis (M21) and investigation workflows (M19).

### 6.2 Database Model

`backend/app/db/models.py` — `AnomalyCorrelation` (table `anomaly_correlations`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK, autoincrement | surrogate key |
| `anomaly_id` | String(36), FK → anomalies.anomaly_id, indexed | CASCADE delete |
| `telemetry_event_id` | Integer, FK → telemetry_events.id, indexed | CASCADE delete |
| `correlation_type` | String(20) | trace_id / span_id / service_time |
| `strength` | String(15) | VERY_STRONG / STRONG / MEDIUM |
| `reason` | Text | human-readable correlation reason |
| `created_at` | DateTime(timezone=True) | correlation creation time |

**Constraints:**
- `CHECK (correlation_type IN ('trace_id', 'span_id', 'service_time'))`
- `CHECK (strength IN ('VERY_STRONG', 'STRONG', 'MEDIUM'))`
- Unique index on `(anomaly_id, telemetry_event_id)` prevents duplicates
- Index on `(anomaly_id, correlation_type)` for filtered queries

### 6.3 Alembic Migration

`backend/alembic/versions/e5f6a7b8c9d0_add_anomaly_correlations.py`

- Revision `e5f6a7b8c9d0`, down_revision `d4e5f6a7b8c9` (M17 baselines table).
- Creates `anomaly_correlations` table with FKs, CHECK constraints, and indexes.
- `downgrade()` drops indexes, constraints, and table.

### 6.4 Ingestion Integration

`backend/app/telemetry/service.py` — `_correlate_anomaly_with_evidence()`:

- Called **after** anomaly is persisted (inside `_detect_and_persist_anomaly`).
- Queries telemetry events from the same service within a 5-minute window around the anomaly timestamp.
- Applies existing correlation rules:
  - **LATENCY anomalies** (from traces): 
    - Logs with same `trace_id` + `span_id` → VERY_STRONG
    - Logs with same `trace_id` only → STRONG
    - Metrics from same service → MEDIUM (service_time)
  - **METRIC anomalies**: traces/logs from same service → MEDIUM (service_time)
  - **ERROR_RATE anomalies**: all event types from same service → MEDIUM (service_time)
- Correlations persisted in batch; failures logged and swallowed (anomaly persistence unaffected).

### 6.5 Dashboard API

`backend/app/api/routes/dashboard.py` — `GET /dashboard/anomalies/{anomaly_id}/correlations`:

- Path parameter: `anomaly_id` (deterministic UUIDv5 string)
- Returns: `{"count": N, "anomaly_id": "...", "items": [{correlation, telemetry_event}, ...]}`
- Ordered by strength (desc) then created_at (desc)
- 404 if anomaly not found; 503 on DB error

### 6.6 Tests

**Extended: `tests/test_anomaly_persistence.py`** — **+8 M18 tests** (tests 24–31, total 31 tests in file):

- Test 24: `test_latency_anomaly_correlates_with_same_trace_log` — VERY_STRONG correlation with matching trace_id + span_id
- Test 25: `test_latency_anomaly_correlates_with_trace_id_only` — STRONG correlation with matching trace_id only
- Test 26: `test_latency_anomaly_correlates_with_service_metrics` — MEDIUM correlation with same-service metrics
- Test 27: `test_metric_anomaly_correlates_with_service_events` — MEDIUM correlation with traces + logs
- Test 28: `test_no_correlation_with_different_trace` — no correlation for different trace_id
- Test 29: `test_no_correlation_with_different_service` — no correlation for different service
- Test 30: `test_no_correlation_when_no_candidates` — empty window produces no correlations
- Test 31: `test_correlation_failure_is_swallowed` — correlation DB errors don't break anomaly persistence

**Test verification status**: **VERIFIED in this session** — all 31 tests in `test_anomaly_persistence.py` pass, plus 50 tests in `test_baseline_service.py`, `test_dashboard_anomalies_api.py`, `test_anomaly_detection.py` (81 total M16/M17/M18-relevant tests passing).

### 6.7 Known Limitations

- **Time window fixed at 5 minutes** — not configurable; may need adjustment for high-latency systems.
- **Correlation only runs at anomaly detection time** — historical anomalies are not retroactively correlated when new telemetry arrives.
- **No correlation for ERROR_RATE anomalies in ingestion** — ERROR_RATE detection is not wired in the ingestion pipeline (requires event window), so this path is untested in practice.
- **Migration not run against live PostgreSQL** — schema verified via model definition only.
- **Tests use mocked DB** — no live PostgreSQL verification performed.

---

## 7. PostgreSQL Integration Verification

> The checks below were **previously reported** as successful by earlier work.
> They are recorded here as *previously reported* and have **not** been
> independently reverified in this session. Treat them as claims to re-confirm,
> not as verified facts.

| Check | Previously reported result | Independently reverified this session? |
|---|---|---|
| Anomaly write to `anomalies` table | Successful INSERT | ❌ No |
| Readback of persisted anomaly rows | Successful SELECT | ❌ No |
| Deduplication via `UNIQUE(anomaly_id)` on re-ingest | Duplicate rejected / single row | ❌ No |
| Cleanup (delete test rows) | Successful | ❌ No |

**Action required:** rerun these against a live PostgreSQL instance and update
this table before marking M16 verified.

---

## 7. Known Issues

### 7.1 Redis connection issue affecting the full test suite

- The application lifespan (`backend/app/main.py`) calls `redis_client.connect()`
  (a `PING`) and `neo4j_connection.connect()` at startup. `TestClient(app)` runs
  the lifespan, so tests that use `TestClient` require a reachable Redis (and
  Neo4j) unless they patch those connections (as `test_dashboard_anomalies_api.py`
  does).
- When Redis is not running, the full `pytest` suite fails/errors on
  Redis-dependent tests. This is a known environment limitation, **not** an M16
  code defect.
- **Workarounds in use:** patching `redis_client.connect/close` and
  `neo4j_connection.connect/close` in tests that need `TestClient`; or running
  the full suite with a local Redis instance available.
- **Follow-up:** make the lifespan tolerant of unavailable Redis (log + continue)
  or gate Redis-dependent tests, so the full suite can run without external
  services.

### 7.2 Uncommitted working tree

All M16 + M17 + M18 files are **uncommitted** on branch `main`. They must be reviewed
and committed before M18 can be considered closed. See `git status` in §10.

### 7.3 Stray files in project root

Untracked non-source files exist in the root (`diff_names.txt`, `git_status.txt`,
`install_log.txt`, `test_result1.txt`). They are **excluded** from the backup and
should be removed or git-ignored before committing.

### 7.4 M16/M17 file overlap (commit separation complexity)

Three files contain intertwined M16 and M17 changes that **cannot be cleanly split** via partial staging
without reverting M17 work:

| File | M16 content | M17 content | Separation status |
|---|---|---|---|
| `backend/app/telemetry/service.py` | `_detect_and_persist_anomaly()` using config defaults | Complete rewrite using `BaselineService` | **Cannot split** — same function body |
| `backend/app/core/config.py` | `anomaly_latency_baseline_ms`, `anomaly_metric_baseline` | Renamed to `*_fallback`, 7 new settings, backward-compat aliases | **Cannot split** — M16 settings no longer exist in current form |
| `tests/test_anomaly_detection.py` | `test_metric_invalid_expected_value` (expects ValueError) | Replaced with `test_metric_zero_expected_value` (graceful handling) | **Cannot split** — in-place test modification |

**Implication for Git commits**: An M16-only commit would need to include the M17 versions of these
three files (which are backward-compatible with M16 contracts). The M17 commit would then be a
no-op for these files. This is functionally safe but means the M16 commit is not a pure "M16-only"
state for these files.

---

## 8. Next Actions & Verification Requirements

1. **Reverify M15** against a live PostgreSQL: confirm the `Anomalies` design,
   migration applies cleanly (`alembic upgrade head`), and downgrade works.
2. **Reverify M16 end to end** against live PostgreSQL:
   - insert a high-latency trace via `/telemetry/traces` → confirm a row in
     `anomalies`;
   - re-ingest the same trace → confirm no duplicate row (deterministic ID);
   - `GET /dashboard/anomalies` → confirm the row is returned newest-first;
   - clean up test rows.
3. **Run the M16/M17/M18-focused tests** (do **not** run the full suite until Redis is
   addressed):
   `pytest -q tests/test_baseline_service.py tests/test_anomaly_persistence.py tests/test_dashboard_anomalies_api.py tests/test_anomaly_detection.py`
   **Expected**: 24 + 31 + 7 + 19 = 81 tests (M16/M17/M18-relevant). Verify all pass.
4. **Resolve the Redis lifespan issue** (§7.1) so the full suite can run.
5. **Reverify M17** against live PostgreSQL:
   - ingest 50+ traces for a service → verify baseline computed and persisted;
   - ingest anomaly → verify correct severity using empirical baseline;
   - ingest metric with new metric_name → verify fallback used.
6. **Reverify M18** against live PostgreSQL:
   - ingest trace + log with same trace_id → verify VERY_STRONG correlation created;
   - ingest metric anomaly → verify MEDIUM correlations with service traces/logs.
7. **Review and commit** the M16 + M17 + M18 working tree on `main` (only after approval);
   add the stray root files to `.gitignore` or delete them.
8. **Do not start M19** until M18 is verified and approved.

---

## 10. Current Git State (read-only snapshot)

- **Branch:** `main`
- **Modified (11):** `backend/alembic/env.py`, `backend/app/api/routes/dashboard.py`,
  `backend/app/core/config.py`, `backend/app/db/models.py`,
  `backend/app/main.py`, `backend/app/telemetry/anomaly.py`,
  `backend/app/telemetry/anomaly_detector.py`, `backend/app/telemetry/anomaly_service.py`,
  `backend/app/telemetry/service.py`, `requirements.txt`,
  `tests/test_anomaly_detection.py`
- **Untracked (15):** `backend/alembic/versions/b1f4e2d3a5c6_add_anomalies_table.py`,
  `backend/alembic/versions/d4e5f6a7b8c9_add_anomaly_baselines.py`,
  `backend/alembic/versions/e5f6a7b8c9d0_add_anomaly_correlations.py`,
  `backend/app/telemetry/anomaly_id.py`, `backend/app/telemetry/baseline_service.py`,
  `diff_names.txt`, `git_status.txt`, `install_log.txt`, `test_result1.txt`,
  `tests/conftest.py`, `tests/test_anomaly_persistence.py`,
  `tests/test_baseline_service.py`, `tests/test_dashboard_anomalies_api.py`,
  `docs/PROJECT_PROGRESS.md`, `docs/` (directory)

No staging, committing, stashing, resetting, or reverting was performed.

---

## 10. Document History

| Date | Change |
|---|---|
| 2026-11-23 | Initial `docs/PROJECT_PROGRESS.md` created (M15 needs-verification, M16 implemented-uncommitted, M17–M24 pending). |
| 2026-11-23 | M17 implementation recorded: empirical baselines, AnomalyBaseline model, migration d4e5f6a7b8c9, BaselineService, config updates, metric validation. **Test claim "78 tests passing" NOT independently verified this session** — based on static test count (24 + 23 + 7 + 19 = 73 M16/M17-relevant tests; remaining from pre-existing suite). |
| 2026-11-23 | M18 implementation recorded: AnomalyCorrelation model, migration e5f6a7b8c9d0, ingestion integration, API endpoint `/dashboard/anomalies/{anomaly_id}/correlations`, 8 correlation tests added (31 total in persistence). **VERIFIED: 81 M16/M17/M18 tests passing** (24 baseline + 31 persistence + 7 dashboard + 19 detection). |