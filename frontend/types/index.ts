export type EventType = "drone_movement" | "fighter_jet_movement" | "helicopter_movement";
export type LocationMode = "exact" | "regional";
export type Timeframe = "24h" | "7d" | "30d" | "all";

export interface EventRead {
  id: string;
  raw_message_id: string;
  event_type: EventType;
  location_mode: LocationMode;
  is_precise: boolean;
  location_id: string | null;
  region_id: string | null;
  location_name: string | null;
  region_slug: string | null;
  region_name: string | null;
  event_time: string;
  source_text: string;
  latitude: number | null;
  longitude: number | null;
}

export interface EventListResponse {
  items: EventRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface MapPoint {
  id: string;
  event_type: EventType;
  latitude: number;
  longitude: number;
  location_name: string | null;
  event_time: string;
  source_text: string;
}

export interface RegionalEvent {
  id: string;
  event_type: EventType;
  region_slug: string;
  region_name: string;
  event_time: string;
  source_text: string;
}

export interface MapEventsResponse {
  points: MapPoint[];
  regional_events: RegionalEvent[];
}

export interface StatsResponse {
  total_events: number;
  drone_count: number;
  fighter_count: number;
  helicopter_count: number;
  exact_count: number;
  regional_count: number;
  last_24h_total: number;
  last_24h_drone_count: number;
  last_24h_fighter_count: number;
  last_24h_helicopter_count: number;
}

export interface LocationRead {
  id: string;
  name_ar: string;
  name_en: string | null;
  alt_names: string[];
  district: string | null;
  governorate: string | null;
  latitude: number;
  longitude: number;
}

export interface RegionRead {
  id: string;
  slug: string;
  name: string;
  geojson: Record<string, unknown>;
}

export interface RawMessageRead {
  id: string;
  telegram_message_id: string | null;
  channel_name: string;
  message_text: string;
  message_date: string;
  ingested_at: string;
  parsed_event_type: EventType | null;
  event_types: EventType[];
  candidate_locations: string[];
  matched_locations: string[];
  unmatched_locations: string[];
}

export interface RawMessageListResponse {
  items: RawMessageRead[];
  total: number;
  limit: number;
}

export interface PipelineSummary {
  raw_messages_total: number;
  recent_raw_messages: number;
  recent_structured_messages: number;
  recent_mapped_messages: number;
  recent_unmatched_messages: number;
  active_feed_events: number;
  active_map_points: number;
}

export interface DashboardResponse {
  snapshot_at: string;
  stats: StatsResponse;
  events: EventListResponse;
  map: MapEventsResponse;
  regions: RegionRead[];
  raw_messages: RawMessageListResponse;
  pipeline: PipelineSummary;
}

export interface DashboardFilters {
  type: EventType | "all";
  timeframe: Timeframe;
}
