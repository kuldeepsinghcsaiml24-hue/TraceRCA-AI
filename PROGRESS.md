# TraceRCA AI — Project Progress Tracker

## Project Overview

**Project:** TraceRCA AI  
**Goal:** Build a distributed observability, causal root-cause analysis, and auto-healing engine using OpenTelemetry, FastAPI, PostgreSQL, Redis, Neo4j, and Next.js.

## Part 1 — Observability Foundation

**Status:** Completed

### Milestone Status

| Milestone | Description | Status |
|---|---|---|
| M1 | Project Foundation | Completed |
| M2 | PostgreSQL, SQLAlchemy, and Alembic | Completed |
| M3 | Redis Integration | Completed |
| M4 | OpenTelemetry Foundation | Completed |
| M5 | Telemetry Ingestion API | Completed |
| M6 | Telemetry Normalization | Completed |
| M7 | Telemetry Correlation | Completed |
| M8 | Service Topology and Neo4j | Completed |
| M9 | Basic Anomaly Detection | Completed |

### Final Verification

- Full test suite: **112 tests passed**.
- Telemetry ingestion and topology integration tests: **18 tests passed**.
- Dashboard displays the discovered services and dependencies.
- Synthetic parent-child spans demonstrate dependency discovery between `api-gateway` and `demo-payment-service`.
- Neo4j stores service nodes and dependency relationships.
- A regression test verifies repeated service upserts retain one service node and preserve the earliest `first_seen` and latest `last_seen` timestamps.

### Testing Limitations

- The demo microservice currently generates synthetic parent-child span relationships.
- Automatic distributed tracing across real HTTP calls has not yet been fully verified.
- End-to-end root-cause analysis and automatic remediation have not yet been validated.

## Current Project State

- **Part 1:** Completed.
- **Dashboard:** Connected to the backend and displaying topology data.
- **Demo microservice:** Available for basic telemetry and topology testing.
- **Next phase:** Part 2 — advanced correlation and causal inference.

## Development Rules

1. Work through one implementation step at a time.
2. Inspect existing code before modifying it.
3. Run relevant tests after each change.
4. Record implementation decisions, test results, and known limitations.
5. Update this file and `README.md` when closing a milestone.
6. Do not start the next milestone until the current milestone's work and documentation are complete.

## Progress Log

### 2026-10-12 — Part 1 Verification

- Confirmed the dashboard displays three services and two dependencies.
- Verified the synthetic dependency `api-gateway → demo-payment-service`.
- Confirmed the focused ingestion and topology test suite passes: 18 tests.
- Confirmed the full test suite passes: 112 tests.
- Recorded the remaining limitations for realistic distributed tracing and end-to-end RCA validation.