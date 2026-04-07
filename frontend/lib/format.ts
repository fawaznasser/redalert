import type { AttackSide, EventType } from "@/types";

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

function normalizeEventText(sourceText: string | null | undefined): string {
  return (sourceText ?? "").toLowerCase();
}

function hasDroneText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  return text.includes("مسي") || text.includes("درون") || text.includes("drone");
}

function hasMissileText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  return (
    text.includes("صاروخ") ||
    text.includes("صاروخي") ||
    text.includes("صواريخ") ||
    text.includes("rocket") ||
    text.includes("missile") ||
    text.includes("مضاد للدروع")
  );
}

function hasClashText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  return text.includes("اشتباك") || text.includes("اشتباكات") || text.includes("clash");
}

function hasHelicopterText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  return text.includes("مروحي") || text.includes("مروح") || text.includes("helicopter");
}

function isAirstrikeText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  return text.includes("غارة");
}

function isBombardmentText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  return text.includes("قصف");
}

function isDroneAttackText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  return (
    text.includes("هجوم بطائرات مسيرة") ||
    text.includes("هجوم بطائرات مسيّرة") ||
    text.includes("ضربة بطائرة مسيرة") ||
    text.includes("ضربة بطائرة مسيّرة") ||
    text.includes("إسقاط طائرة مسيرة") ||
    text.includes("إسقاط طائرة مسيّرة") ||
    text.includes("يسقط مسيرة") ||
    text.includes("يسقط طائرة") ||
    (hasDroneText(text) && text.includes("هجوم"))
  );
}

function isResistanceOperationText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  return (
    text.includes("عملية مقاومة") ||
    text.includes("عمليات المقاومة") ||
    text.includes("إطلاق صاروخ دفاع جوي") ||
    text.includes("اطلاق صاروخ دفاع جوي") ||
    text.includes("إطلاق صاروخ") ||
    text.includes("اطلاق صاروخ")
  );
}

export function isFireMonitorCombatEvent(event: {
  event_type: EventType;
  source_text?: string | null;
  attack_side?: AttackSide | null;
}): boolean {
  if (event.attack_side === "enemy_attack" || event.attack_side === "resistance_attack") {
    return true;
  }
  return event.event_type === "ground_incursion" && isActualIncursionText(event.source_text);
}

export function isActualIncursionText(sourceText: string | null | undefined): boolean {
  const text = normalizeEventText(sourceText);
  if (
    text.includes("توغل") ||
    text.includes("توغل بري") ||
    text.includes("تسلل بري") ||
    text.includes("متوغلة") ||
    text.includes("متوغل")
  ) {
    return true;
  }
  return text.includes("تسلل") && !text.includes("مسير") && !text.includes("طائرة") && !text.includes("مسي");
}

export function displayEventTypeLabel(
  event: { event_type: EventType; source_text?: string | null; attack_side?: AttackSide | null },
  lang: "ar" | "en" = "en",
): string {
  if (event.attack_side === "enemy_attack") {
    if (isAirstrikeText(event.source_text)) {
      return lang === "ar" ? "غارة" : "Airstrike";
    }
    if (isBombardmentText(event.source_text)) {
      return lang === "ar" ? "قصف" : "Bombardment";
    }
    if (hasMissileText(event.source_text)) {
      return lang === "ar" ? "هجوم صاروخي" : "Missile Attack";
    }
    if (isDroneAttackText(event.source_text)) {
      return lang === "ar" ? "هجوم مسيّرات" : "Drone Attack";
    }
    return attackSideLabel("enemy_attack", lang);
  }

  if (event.attack_side === "resistance_attack" || isResistanceActionEvent(event)) {
    if (hasClashText(event.source_text)) {
      return lang === "ar" ? "اشتباكات" : "Clashes";
    }
    if (hasMissileText(event.source_text)) {
      return lang === "ar" ? "هجوم صاروخي" : "Missile Attack";
    }
    if (isDroneAttackText(event.source_text)) {
      return lang === "ar" ? "هجوم مسيّرات" : "Drone Attack";
    }
    if (isActualIncursionText(event.source_text)) {
      return lang === "ar" ? "توغل" : "Incursion";
    }
    return attackSideLabel("resistance_attack", lang);
  }

  if (event.event_type === "fighter_jet_movement") {
    if (isAirstrikeText(event.source_text)) {
      return lang === "ar" ? "غارة" : "Airstrike";
    }
    if (isBombardmentText(event.source_text)) {
      return lang === "ar" ? "قصف" : "Bombardment";
    }
    if (hasMissileText(event.source_text)) {
      return lang === "ar" ? "هجوم صاروخي" : "Missile Attack";
    }
  }

  if (event.event_type === "ground_incursion") {
    if (hasClashText(event.source_text)) {
      return lang === "ar" ? "اشتباكات" : "Clashes";
    }
    if (!isActualIncursionText(event.source_text) && isResistanceOperationText(event.source_text)) {
      return lang === "ar" ? "هجوم مقاومة" : "Resistance Attack";
    }
  }

  if (lang === "ar") {
    if (event.event_type === "drone_movement") {
      return isDroneAttackText(event.source_text) ? "هجوم مسيّرات" : "مسيّرات";
    }
    if (event.event_type === "fighter_jet_movement") {
      return "مقاتلات";
    }
    if (event.event_type === "helicopter_movement") {
      return "مروحيات";
    }
    return "توغل";
  }

  if (event.event_type === "drone_movement") {
    return isDroneAttackText(event.source_text) ? "Drone Attack" : "Drones";
  }
  if (event.event_type === "helicopter_movement") {
    return hasHelicopterText(event.source_text) ? "Helicopters" : "Helicopter";
  }
  return eventTypeLabel(event.event_type);
}

export function isResistanceActionEvent(event: {
  event_type: EventType;
  source_text?: string | null;
  attack_side?: AttackSide | null;
}): boolean {
  if (event.attack_side === "resistance_attack") {
    return true;
  }
  return event.event_type === "ground_incursion" && !isActualIncursionText(event.source_text) && isResistanceOperationText(event.source_text);
}

export function displayNewsIcon(event: {
  event_type: EventType;
  source_text?: string | null;
}): string {
  if (hasClashText(event.source_text)) {
    return "⚔";
  }
  if (hasMissileText(event.source_text)) {
    return "🚀";
  }
  if (hasDroneText(event.source_text) || event.event_type === "drone_movement") {
    return "🛸";
  }
  if (event.event_type === "fighter_jet_movement") {
    return "✈";
  }
  if (event.event_type === "helicopter_movement") {
    return "🚁";
  }
  return "◉";
}

export function attackSideLabel(attackSide: AttackSide, lang: "ar" | "en"): string {
  if (lang === "ar") {
    return attackSide === "enemy_attack" ? "هجوم معادٍ" : "هجوم حزب الله";
  }
  return attackSide === "enemy_attack" ? "Enemy Attack" : "Hezbollah Attack";
}

export function localizeSouthLebanon(lang: "ar" | "en"): string {
  return lang === "ar" ? "جنوب لبنان" : "South Lebanon";
}

export function displayEventLocation(
  event: { location_name: string | null; region_slug?: string | null; region_name?: string | null },
  lang: "ar" | "en",
): string {
  if (event.location_name) {
    return event.location_name;
  }
  if (event.region_slug === "south-lebanon") {
    return localizeSouthLebanon(lang);
  }
  if (event.region_name === "South Lebanon" || event.region_name === "جنوب لبنان") {
    return localizeSouthLebanon(lang);
  }
  return event.region_name ?? localizeSouthLebanon(lang);
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
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: BEIRUT_TIMEZONE,
  }).formatToParts(parseApiDate(value));

  const lookup = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((part) => part.type === type)?.value ?? "";

  const day = lookup("day");
  const month = lookup("month");
  const year = lookup("year");
  const hour = lookup("hour");
  const minute = lookup("minute");
  return `\u200E${day} ${month} ${year}, ${hour}:${minute}\u200E`;
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
