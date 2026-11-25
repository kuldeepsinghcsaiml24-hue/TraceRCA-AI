# TraceRCA AI — Frontend

Next.js 15 (App Router) dashboard for the TraceRCA AI observability platform.

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` — the dashboard connects to the FastAPI backend at `http://localhost:8000` (configured via `NEXT_PUBLIC_API_BASE_URL`).

## Tech Stack

- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind CSS v4
- **Fonts**: Geist Sans / Geist Mono via `next/font`
- **State**: React hooks + TanStack Query (planned)
- **Charts**: To be decided (planned for anomaly visualization)

## Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx          # Main dashboard (overview, services, topology, events)
│   │   ├── layout.tsx        # Root layout + global styles
│   │   └── globals.css       # Tailwind v4 + custom dark theme
│   └── lib/                  # API client, shared utilities (to be added)
├── public/                   # Static assets
├── package.json
├── tsconfig.json
├── next.config.ts
└── eslint.config.mjs
```

## Current Dashboard Sections

| Section | Route | Status |
|---|---|---|
| Overview | `/` | ✅ Live metrics from `/dashboard/overview` |
| Services | `/` (anchor) | ✅ Table from `/dashboard/services` |
| Service Topology | `/` (anchor) | ✅ Graph from `/dashboard/topology` (Neo4j) |
| Telemetry Events | `/` (anchor) | ✅ Table from `/dashboard/overview` |
| **Anomalies** | `/anomalies` | 🔄 Planned (M19) |
| **Anomaly Investigation** | `/anomalies/[id]` | 🔄 Planned (M19) |

All data flows through FastAPI — the frontend never accesses PostgreSQL, Redis, or Neo4j directly.

## Development

### Commands

| Command | Description |
|---|---|
| `npm run dev` | Start dev server with Turbopack |
| `npm run build` | Production build |
| `npm run start` | Run production server |
| `npm run lint` | ESLint (Next.js core-web-vitals + TypeScript) |

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | FastAPI backend base URL |

Create `.env.local` to override:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Styling Conventions

- **Dark theme only** — background `#080b12`, foreground `#e2e8f0`
- **Accent color**: Cyan `#67e8f9` (primary), Emerald `#34d399` (success), Rose `#f87171` (error)
- **Reusable classes** (defined in `globals.css`):
  - `.sidebar`, `.brand-mark`, `.nav-link`, `.nav-link-active`
  - `.metric-card`, `.metric-icon`
  - `.panel`, `.section-action`, `.empty-state`
- **Fonts**: Geist Sans (UI), Geist Mono (code/tables)

## Adding New Pages (App Router)

```bash
# New route segment
mkdir -p src/app/anomalies/[anomalyId]
# Create page.tsx and layout.tsx as needed
```

## API Integration Pattern

```typescript
// src/lib/api.ts (to be created)
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchAnomalies(params?: { limit?: number }) {
  const url = new URL(`${API_BASE}/dashboard/anomalies`);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
```

## Roadmap (M19+)

- [ ] Centralized API client with TanStack Query
- [ ] TypeScript types generated from backend OpenAPI schema
- [ ] Anomaly list page (`/anomalies`) with filters, pagination, sorting
- [ ] Anomaly investigation page (`/anomalies/[id]`) with correlation graph + evidence table
- [ ] Real-time updates via SSE/WebSocket
- [ ] Responsive mobile layout
- [ ] Component library (Button, Table, Badge, Drawer, etc.)
- [ ] Unit/integration tests with Vitest + React Testing Library

## Related

- [Backend README](../backend/README.md) — FastAPI service, ingestion, normalization, correlation, topology, anomaly detection
- [Root README](../README.md) — Full project documentation