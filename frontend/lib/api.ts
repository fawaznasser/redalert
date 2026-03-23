import type {
  DashboardResponse,
  DashboardFilters,
  EventRead,
  Timeframe,
} from "@/types";

function defaultApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? defaultApiBaseUrl();

function timeframeToFrom(timeframe: Timeframe): string | null {
  if (timeframe === "all") {
    return null;
  }

  const now = new Date();
  const next = new Date(now);
  if (timeframe === "24h") {
    next.setHours(now.getHours() - 24);
  }
  if (timeframe === "7d") {
    next.setDate(now.getDate() - 7);
  }
  if (timeframe === "30d") {
    next.setDate(now.getDate() - 30);
  }
  return next.toISOString();
}

function buildFilterParams(filters: DashboardFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.type !== "all") {
    params.set("type", filters.type);
  }
  const from = timeframeToFrom(filters.timeframe);
  if (from) {
    params.set("from", from);
  }
  return params;
}

async function fetchJson<T>(path: string, params?: URLSearchParams): Promise<T> {
  const suffix = params && Array.from(params.keys()).length > 0 ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}${path}${suffix}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed for ${path}: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export interface DashboardPayload {
  stats: DashboardResponse["stats"];
  events: DashboardResponse["events"];
  map: DashboardResponse["map"];
  regions: DashboardResponse["regions"];
  rawMessages: DashboardResponse["raw_messages"];
  pipeline: DashboardResponse["pipeline"];
  snapshotAt: DashboardResponse["snapshot_at"];
}

export async function fetchDashboardPayload(filters: DashboardFilters): Promise<DashboardPayload> {
  const filterParams = buildFilterParams(filters);
  filterParams.set("limit", "100");
  filterParams.set("raw_limit", "20");
  const payload = await fetchJson<DashboardResponse>("/dashboard", filterParams);
  return {
    stats: payload.stats,
    events: payload.events,
    map: payload.map,
    regions: payload.regions,
    rawMessages: payload.raw_messages,
    pipeline: payload.pipeline,
    snapshotAt: payload.snapshot_at,
  };
}

export function getEventDisplayName(event: EventRead): string {
  return event.location_name ?? event.region_name ?? "Unknown area";
}

export function eventsStreamUrl(): string {
  return `${API_BASE_URL}/events/stream`;
}
