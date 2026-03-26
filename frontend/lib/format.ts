import type { EventType } from "@/types";

const BEIRUT_TIMEZONE = "Asia/Beirut";

const eventLabels: Record<EventType, string> = {
  drone_movement: "Drone",
  fighter_jet_movement: "Fighter Jet",
  helicopter_movement: "Helicopter",
  ground_incursion: "Incursion",
};

export function eventTypeLabel(eventType: EventType): string {
  return eventLabels[eventType];
}

export function eventTypeDescription(eventType: EventType): string {
  if (eventType === "drone_movement") {
    return "Low-altitude drone activity";
  }
  if (eventType === "fighter_jet_movement") {
    return "Fast jet movement or overflight";
  }
  if (eventType === "ground_incursion") {
    return "Ground incursion or troop advance";
  }
  return "Rotary-wing aircraft movement";
}

function parseApiDate(value: string): Date {
  const hasExplicitTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  return new Date(hasExplicitTimezone ? value : `${value}Z`);
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: BEIRUT_TIMEZONE,
  }).format(parseApiDate(value));
}

export function formatRelativeTime(value: string): string {
  const diff = parseApiDate(value).getTime() - Date.now();
  const minutes = Math.round(diff / 60000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(minutes) < 60) {
    return formatter.format(minutes, "minute");
  }
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) {
    return formatter.format(hours, "hour");
  }
  const days = Math.round(hours / 24);
  return formatter.format(days, "day");
}

const eventDurations: Record<EventType, number> = {
  drone_movement: 300,
  fighter_jet_movement: 20,
  helicopter_movement: 30,
  ground_incursion: 300,
};

export function eventExpiryMinutes(eventType: EventType): number {
  return eventDurations[eventType];
}

export function formatTimeRemaining(eventType: EventType, eventTime: string): string {
  const expiresAt = new Date(parseApiDate(eventTime).getTime() + eventDurations[eventType] * 60000);
  const remainingMs = expiresAt.getTime() - Date.now();
  if (remainingMs <= 0) {
    return "Expired";
  }

  const remainingMinutes = Math.ceil(remainingMs / 60000);
  if (remainingMinutes < 60) {
    return `${remainingMinutes} min left`;
  }

  const hours = Math.floor(remainingMinutes / 60);
  const minutes = remainingMinutes % 60;
  if (minutes === 0) {
    return `${hours}h left`;
  }
  return `${hours}h ${minutes}m left`;
}
