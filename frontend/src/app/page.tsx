
"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface RecentEvent {
  id: number;
  event_type: string;
  timestamp: string;
  service_name: string;
  trace_id: string | null;
  operation_name: string | null;
  status: string | null;
  duration_ms: number | null;
  message: string | null;
  metric_name: string | null;
  metric_value: number | null;
}

interface Overview {
  database_status: string;
  total_events: number;
  trace_count: number;
  log_count: number;
  metric_count: number;
  service_count: number;
  error_trace_count: number;
  recent_events: RecentEvent[];
}

interface ServiceStats {
  service_name: string;
  event_count: number;
  error_trace_count: number;
  average_duration_ms: number;
  last_seen: string;
}

interface ServicesResponse {
  service_count: number;
  services: ServiceStats[];
}

interface TopologyService {
  service_name: string;
  first_seen: string;
  last_seen: string;
}

interface Dependency {
  source_service: string;
  target_service: string;
  first_seen: string;
  last_seen: string;
}

interface Topology {
  services: TopologyService[];
  dependencies: Dependency[];
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString();
}

function formatDuration(value: number | null | undefined) {
  if (value == null) return "—";
  return `${value.toFixed(1)} ms`;
}

function MetricCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: string;
}) {
  return (
    <article className="metric-card">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-slate-400">{label}</p>
        <span className="metric-icon">{icon}</span>
      </div>
      <p className="mt-4 text-3xl font-semibold tracking-tight text-white">
        {value}
      </p>
      <p className="mt-2 text-xs text-slate-500">{detail}</p>
    </article>
  );
}

function SectionTitle({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: string;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold text-white">{title}</h2>
        <p className="mt-1 text-xs text-slate-500">{description}</p>
      </div>
      {action && <span className="section-action">{action}</span>}
    </div>
  );
}

function StatusDot({ good }: { good: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${
        good ? "bg-emerald-400" : "bg-rose-400"
      }`}
    />
  );
}

export default function Home() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [services, setServices] = useState<ServicesResponse | null>(null);
  const [topology, setTopology] = useState<Topology | null>(null);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const refreshDashboard = useCallback(async () => {
    const endpoints = [
      {
        key: "overview",
        path: "/dashboard/overview",
        save: (data: Overview) => setOverview(data),
      },
      {
        key: "services",
        path: "/dashboard/services",
        save: (data: ServicesResponse) => setServices(data),
      },
      {
        key: "topology",
        path: "/dashboard/topology",
        save: (data: Topology) => setTopology(data),
      },
    ];

    const nextErrors: Record<string, string> = {};

    await Promise.all(
      endpoints.map(async (endpoint) => {
        try {
          const response = await fetch(
            `${API_BASE}${endpoint.path}`,
            { cache: "no-store" },
          );

          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }

          const data: unknown = await response.json();
          endpoint.save(data as never);
        } catch (error) {
          nextErrors[endpoint.key] =
            error instanceof Error
              ? error.message
              : "Request failed";
        }
      }),
    );

    setErrors(nextErrors);
    setLastUpdated(new Date().toISOString());
    setLoading(false);
  }, []);

  
useEffect(() => {
  const initialRefresh = setTimeout(() => {
    void refreshDashboard();
  }, 0);

  const interval = setInterval(() => {
    void refreshDashboard();
  }, 15000);

  return () => {
    clearTimeout(initialRefresh);
    clearInterval(interval);
  };
}, [refreshDashboard]);


  const backendConnected =
    !errors.overview && overview !== null;

  const databaseConnected =
    overview?.database_status === "connected";

  return (
    <main className="min-h-screen bg-[#080b12] text-slate-100">
      <div className="flex min-h-screen">
        <aside className="sidebar hidden w-64 shrink-0 flex-col border-r border-white/[0.07] px-5 py-6 lg:flex">
          <div className="flex items-center gap-3 px-2">
            <div className="brand-mark">T</div>
            <div>
              <h1 className="font-semibold tracking-wide text-white">
                TraceRCA
              </h1>
              <p className="text-[10px] tracking-[0.2em] text-slate-500">
                OBSERVABILITY AI
              </p>
            </div>
          </div>

          <div className="mt-10">
            <p className="nav-heading">WORKSPACE</p>
            <nav className="mt-3 space-y-1">
              <a className="nav-link nav-link-active" href="#overview">
                <span>▦</span> Overview
              </a>
              <a className="nav-link" href="#services">
                <span>◈</span> Services
              </a>
              <a className="nav-link" href="#topology">
                <span>⌘</span> Service topology
              </a>
              <a className="nav-link" href="#events">
                <span>≋</span> Telemetry events
              </a>
            </nav>
          </div>

          <div className="mt-9">
            <p className="nav-heading">PLATFORM</p>
            <div className="mt-3 space-y-1">
              <div className="nav-link opacity-60">
                <span>⌁</span> Root cause analysis
                <span className="ml-auto text-[9px]">LATER</span>
              </div>
              <div className="nav-link opacity-60">
                <span>↻</span> Auto-healing
                <span className="ml-auto text-[9px]">LATER</span>
              </div>
            </div>
          </div>

          <div className="mt-auto rounded-xl border border-white/[0.08] bg-white/[0.025] p-4">
            <p className="text-xs font-medium text-slate-300">
              Data connections
            </p>
            <div className="mt-4 space-y-3 text-xs">
              <div className="flex items-center gap-2">
                <StatusDot good={backendConnected} />
                <span className="text-slate-400">FastAPI</span>
                <span className="ml-auto text-slate-500">
                  {backendConnected ? "Online" : "Offline"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <StatusDot good={databaseConnected} />
                <span className="text-slate-400">PostgreSQL</span>
                <span className="ml-auto text-slate-500">
                  {overview?.database_status ?? "Unknown"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <StatusDot good={!errors.topology && topology !== null} />
                <span className="text-slate-400">Neo4j API</span>
                <span className="ml-auto text-slate-500">
                  {!errors.topology && topology !== null
                    ? "Online"
                    : "Unknown"}
                </span>
              </div>
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.07] bg-[#080b12]/90 px-5 py-4 backdrop-blur-xl sm:px-8">
            <div>
              <p className="text-xs text-slate-500">
                TraceRCA AI / Workspace
              </p>
              <h2 className="mt-1 text-lg font-semibold text-white">
                Observability overview
              </h2>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 rounded-full border border-white/[0.08] px-3 py-2 text-xs">
                <StatusDot good={backendConnected && databaseConnected} />
                <span className="text-slate-300">
                  {backendConnected && databaseConnected
                    ? "System connected"
                    : "Connection issue"}
                </span>
              </div>
              <button
                onClick={() => void refreshDashboard()}
                className="rounded-lg border border-white/[0.12] bg-white/[0.04] px-4 py-2 text-xs font-medium text-slate-200 transition hover:bg-white/[0.08]"
              >
                ↻ Refresh
              </button>
            </div>
          </header>

          <div className="mx-auto max-w-[1600px] space-y-8 px-5 py-8 sm:px-8">
            <section id="overview">
              <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold text-white">
                    System overview
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Live telemetry from your TraceRCA backend
                  </p>
                </div>
                <p className="text-xs text-slate-500">
                  Auto-refresh: 15 seconds
                  {lastUpdated && (
                    <> · Updated {new Date(lastUpdated).toLocaleTimeString()}</>
                  )}
                </p>
              </div>

              {Object.entries(errors).map(([key, message]) => (
                <div
                  key={key}
                  className="mb-3 rounded-lg border border-rose-500/20 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-300"
                >
                  <strong className="capitalize">{key} API:</strong>{" "}
                  {message}. Check that FastAPI is running and CORS allows
                  requests from this frontend.
                </div>
              ))}

              {loading && !overview && (
                <p className="mb-4 text-sm text-slate-400">
                  Loading live telemetry…
                </p>
              )}

              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label="Total telemetry events"
                  value={overview?.total_events ?? "—"}
                  detail="Persisted trace, log and metric records"
                  icon="≋"
                />
                <MetricCard
                  label="Trace spans"
                  value={overview?.trace_count ?? "—"}
                  detail="Trace events stored in PostgreSQL"
                  icon="⌁"
                />
                <MetricCard
                  label="Observed services"
                  value={overview?.service_count ?? "—"}
                  detail="Services reported by telemetry"
                  icon="◈"
                />
                <MetricCard
                  label="Error traces"
                  value={overview?.error_trace_count ?? "—"}
                  detail="As reported by the overview API"
                  icon="⚠"
                />
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <MetricCard
                  label="Logs received"
                  value={overview?.log_count ?? "—"}
                  detail="Persisted log events"
                  icon="≡"
                />
                <MetricCard
                  label="Metrics received"
                  value={overview?.metric_count ?? "—"}
                  detail="Persisted metric events"
                  icon="⌗"
                />
              </div>
            </section>

            <section id="topology" className="panel">
              <SectionTitle
                title="Service topology"
                description="Service dependencies returned by the Neo4j-backed API"
                action={
                  topology
                    ? `${topology.services.length} services · ${topology.dependencies.length} dependencies`
                    : "Waiting for topology"
                }
              />

              {errors.topology ? (
                <p className="empty-state">
                  Topology could not be loaded. Check the API connection.
                </p>
              ) : topology && topology.services.length === 0 ? (
                <p className="empty-state">
                  No services discovered yet. Send telemetry to populate the
                  topology.
                </p>
              ) : topology ? (
                <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
                  <div className="flex flex-wrap items-center justify-center gap-4 rounded-xl border border-white/[0.06] bg-[#090d16] p-6">
                    {topology.services.map((service, index) => (
                      <div
                        key={service.service_name}
                        className="flex min-w-40 items-center gap-3 rounded-xl border border-cyan-400/20 bg-cyan-400/[0.045] px-4 py-4"
                      >
                        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-400/10 text-lg text-cyan-300">
                          ◈
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-100">
                            {service.service_name}
                          </p>
                          <p className="mt-1 text-[10px] text-slate-500">
                            Service {index + 1}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div>
                    <p className="mb-3 text-xs font-medium uppercase tracking-wider text-slate-500">
                      Observed dependencies
                    </p>
                    {topology.dependencies.length === 0 ? (
                      <p className="text-sm text-slate-500">
                        No dependencies discovered yet.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {topology.dependencies.map((dependency, index) => (
                          <div
                            key={`${dependency.source_service}-${dependency.target_service}-${index}`}
                            className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3"
                          >
                            <p className="text-xs text-slate-300">
                              {dependency.source_service}
                            </p>
                            <p className="my-1 text-cyan-400">↓</p>
                            <p className="text-xs text-slate-300">
                              {dependency.target_service}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="empty-state">Loading topology…</p>
              )}
            </section>

            <section id="services" className="panel">
              <SectionTitle
                title="Services"
                description="Statistics aggregated by your dashboard services API"
              />

              {errors.services ? (
                <p className="empty-state">
                  Service statistics could not be loaded.
                </p>
              ) : services && services.services.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[620px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-white/[0.07] text-xs text-slate-500">
                        <th className="px-3 py-3 font-medium">Service</th>
                        <th className="px-3 py-3 font-medium">Events</th>
                        <th className="px-3 py-3 font-medium">Avg duration</th>
                        <th className="px-3 py-3 font-medium">Error traces</th>
                        <th className="px-3 py-3 font-medium">Last seen</th>
                      </tr>
                    </thead>
                    <tbody>
                      {services.services.map((service) => (
                        <tr
                          key={service.service_name}
                          className="border-b border-white/[0.045] transition hover:bg-white/[0.025]"
                        >
                          <td className="px-3 py-4 font-medium text-slate-200">
                            <span className="mr-2 text-cyan-400">◈</span>
                            {service.service_name}
                          </td>
                          <td className="px-3 py-4 text-slate-300">
                            {service.event_count}
                          </td>
                          <td className="px-3 py-4 text-slate-300">
                            {formatDuration(service.average_duration_ms)}
                          </td>
                          <td className="px-3 py-4 text-slate-300">
                            {service.error_trace_count}
                          </td>
                          <td className="px-3 py-4 text-xs text-slate-500">
                            {formatDate(service.last_seen)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty-state">
                  {loading ? "Loading services…" : "No services available."}
                </p>
              )}
            </section>

            <section id="events" className="panel">
              <SectionTitle
                title="Recent telemetry events"
                description="Latest records returned by the overview API"
                action={
                  overview ? `${overview.recent_events.length} shown` : undefined
                }
              />

              {errors.overview ? (
                <p className="empty-state">
                  Recent events could not be loaded.
                </p>
              ) : overview && overview.recent_events.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[680px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-white/[0.07] text-xs text-slate-500">
                        <th className="px-3 py-3 font-medium">Type</th>
                        <th className="px-3 py-3 font-medium">Service</th>
                        <th className="px-3 py-3 font-medium">Operation / detail</th>
                        <th className="px-3 py-3 font-medium">Status</th>
                        <th className="px-3 py-3 font-medium">Duration</th>
                        <th className="px-3 py-3 font-medium">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overview.recent_events.map((event) => (
                        <tr
                          key={event.id}
                          className="border-b border-white/[0.045] hover:bg-white/[0.025]"
                        >
                          <td className="px-3 py-4">
                            <span className="rounded-md border border-white/[0.08] px-2 py-1 text-xs capitalize text-slate-300">
                              {event.event_type}
                            </span>
                          </td>
                          <td className="px-3 py-4 text-slate-300">
                            {event.service_name}
                          </td>
                          <td className="max-w-56 truncate px-3 py-4 text-slate-400">
                            {event.operation_name ??
                              event.message ??
                              event.metric_name ??
                              "—"}
                          </td>
                          <td className="px-3 py-4">
                            <span
                              className={
                                event.status === "ERROR"
                                  ? "text-rose-400"
                                  : event.status === "OK"
                                    ? "text-emerald-400"
                                    : "text-slate-500"
                              }
                            >
                              {event.status ?? "—"}
                            </span>
                          </td>
                          <td className="px-3 py-4 text-slate-400">
                            {formatDuration(event.duration_ms)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-4 text-xs text-slate-500">
                            {formatDate(event.timestamp)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="empty-state">
                  {loading ? "Loading events…" : "No recent events available."}
                </p>
              )}
            </section>

            <footer className="flex flex-wrap justify-between gap-2 border-t border-white/[0.07] pt-5 text-xs text-slate-600">
              <span>TraceRCA AI · Observability Foundation</span>
              <span>Live API data · Refresh interval 15 seconds</span>
            </footer>
          </div>
        </div>
      </div>
    </main>
  );
}
