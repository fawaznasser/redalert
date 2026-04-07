import type {
  DashboardResponse,
  DashboardFilters,
  EventRead,
  Timeframe,
} from "@/types";

function normalizeBasePath(value: string | undefined): string {
  const raw = (value ?? "").trim();
  if (!raw || raw === "/") {
    return "";
  }
  return raw.startsWith("/") ? raw.replace(/\/+$/, "") : `/${raw.replace(/\/+$/, "")}`;
}

const SITE_BASE_PATH = normalizeBasePath(process.env.NEXT_PUBLIC_SITE_BASE_PATH);

function defaultApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const { origin, protocol, hostname } = window.location;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return `${protocol}//${hostname}:8090`;
    }
    if (SITE_BASE_PATH) {
      return `${origin}${SITE_BASE_PATH}/api`;
    }
    return `${origin}/api`;
  }
  return SITE_BASE_PATH ? `${SITE_BASE_PATH}/api` : "https://redalertt.onrender.com";
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? defaultApiBaseUrl();
const BEIRUT_TIME_ZONE = "Asia/Beirut";

export function normalizeSelectedDate(value: string | null | undefined): string | null {
  const raw = (value ?? "").trim();
  if (!raw) {
    return null;
  }

  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    return `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`;
  }

  const slashMatch = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (slashMatch) {
    const month = slashMatch[1].padStart(2, "0");
    const day = slashMatch[2].padStart(2, "0");
    return `${slashMatch[3]}-${month}-${day}`;
  }

  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, "0")}-${String(parsed.getDate()).padStart(2, "0")}`;
}

function resolveApiBaseUrl(overrideBaseUrl?: string): string {
  if (!overrideBaseUrl) {
    return API_BASE_URL;
  }
  if (overrideBaseUrl.startsWith("http://") || overrideBaseUrl.startsWith("https://")) {
    return overrideBaseUrl.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined") {
    return `${window.location.origin}${normalizeBasePath(overrideBaseUrl)}`;
  }
  return normalizeBasePath(overrideBaseUrl);
}

function getTimeZoneOffsetMinutes(date: Date, timeZone: string): number {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    timeZoneName: "shortOffset",
  });
  const zonePart = formatter.formatToParts(date).find((part) => part.type === "timeZoneName")?.value ?? "GMT+0";
  const match = zonePart.match(/^GMT([+-])(\d{1,2})(?::?(\d{2}))?$/i);
  if (!match) {
    return 0;
  }
  const sign = match[1] === "-" ? -1 : 1;
  const hours = Number(match[2] || 0);
  const minutes = Number(match[3] || 0);
  return sign * (hours * 60 + minutes);
}

function zonedDateTimeToUtcIso(
  timeZone: string,
  year: number,
  month: number,
  day: number,
  hour = 0,
  minute = 0,
  second = 0,
  millisecond = 0,
): string {
  let utcMillis = Date.UTC(year, month - 1, day, hour, minute, second, millisecond);
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const offsetMinutes = getTimeZoneOffsetMinutes(new Date(utcMillis), timeZone);
    utcMillis = Date.UTC(year, month - 1, day, hour, minute, second, millisecond) - offsetMinutes * 60_000;
  }
  return new Date(utcMillis).toISOString();
}

function getTodayInTimeZone(timeZone: string): string {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return formatter.format(new Date());
}

export function getTodayInBeirut(): string {
  return getTodayInTimeZone(BEIRUT_TIME_ZONE);
}

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
  const normalizedSelectedDate = normalizeSelectedDate(filters.selectedDate);
  if (normalizedSelectedDate) {
    const [year, month, day] = normalizedSelectedDate.split("-").map((value) => Number(value));
    const from = zonedDateTimeToUtcIso(BEIRUT_TIME_ZONE, year, month, day, 0, 0, 0, 0);
    const to = zonedDateTimeToUtcIso(BEIRUT_TIME_ZONE, year, month, day, 23, 59, 59, 999);
    params.set("from", from);
    params.set("to", to);
    params.set("active_only", "false");
    return params;
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

export interface DashboardQueryOptions {
  channels?: string[];
  baseUrl?: string;
  combatOnly?: boolean;
}

export async function fetchDashboardPayload(filters: DashboardFilters, options: DashboardQueryOptions = {}): Promise<DashboardPayload> {
  const filterParams = buildFilterParams(filters);
  filterParams.set("limit", filters.selectedDate ? "2000" : "30");
  filterParams.set("map_limit", filters.selectedDate ? "500" : "180");
  filterParams.set("raw_limit", filters.selectedDate ? "50" : "8");
  filterParams.set("include_raw_messages", "false");
  filterParams.set("include_regions", "false");
  filterParams.set("include_pipeline", "false");
  if (options.combatOnly) {
    filterParams.set("combat_only", "true");
    filterParams.set("active_only", "false");
    if (filters.selectedDate) {
      filterParams.set("limit", "160");
      filterParams.set("map_limit", "140");
    } else {
      filterParams.set("limit", "24");
      filterParams.set("map_limit", "80");
    }
  }
  for (const channel of options.channels ?? []) {
    if (channel.trim()) {
      filterParams.append("channel", channel.trim());
    }
  }
  const baseUrl = resolveApiBaseUrl(options.baseUrl);
  const suffix = Array.from(filterParams.keys()).length > 0 ? `?${filterParams.toString()}` : "";
  const response = await fetch(`${baseUrl}/dashboard${suffix}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed for /dashboard: ${response.status}`);
  }
  const payload = await response.json() as DashboardResponse;
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

export function eventsStreamUrl(baseUrl?: string): string {
  return `${resolveApiBaseUrl(baseUrl)}/events/stream`;
}
