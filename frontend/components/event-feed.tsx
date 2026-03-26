import { eventTypeLabel, formatDateTime, formatRelativeTime, formatTimeRemaining } from "@/lib/format";
import type { EventRead } from "@/types";

interface EventFeedProps {
  events: EventRead[];
}

const badgeTone: Record<string, string> = {
  drone_movement: "bg-steel/15 text-steel",
  fighter_jet_movement: "bg-ember/15 text-ember",
  helicopter_movement: "bg-olive/15 text-olive",
  ground_incursion: "bg-emerald-100 text-emerald-700",
};

function excerpt(text: string): string {
  if (text.length <= 140) {
    return text;
  }
  return `${text.slice(0, 137)}...`;
}

export default function EventFeed({ events }: EventFeedProps) {
  if (events.length === 0) {
    return (
      <div className="rounded-[1.8rem] border border-dashed border-slate-300 bg-slate-50/80 p-6 text-sm text-slate-500">
        No active alerts match the current filters.
      </div>
    );
  }

  return (
    <div className="max-h-[34rem] space-y-3 overflow-y-auto pr-1">
      {events.map((event) => (
        <article key={event.id} className="rounded-[1.6rem] border border-white/60 bg-white/80 p-4 shadow-panel backdrop-blur">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeTone[event.event_type]}`}>
              {eventTypeLabel(event.event_type)}
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              {event.location_mode === "exact" ? "Exact" : "Regional"}
            </span>
          </div>
          <div className="mt-3 flex items-start justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-slate-900">
                {event.location_name ?? event.region_name ?? "South Lebanon"}
              </h3>
              <p className="mt-1 text-xs text-slate-500">{formatDateTime(event.event_time)}</p>
              <p className="mt-1 text-xs font-medium text-slate-400">{formatTimeRemaining(event.event_type, event.event_time)}</p>
            </div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
              {formatRelativeTime(event.event_time)}
            </p>
          </div>
          <p className="mt-3 whitespace-pre-line text-sm leading-6 text-slate-600">{excerpt(event.source_text)}</p>
        </article>
      ))}
    </div>
  );
}
