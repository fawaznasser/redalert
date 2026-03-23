import { formatDateTime } from "@/lib/format";
import type { EventRead, EventType } from "@/types";

interface RawMessageFeedProps {
  events: EventRead[];
}

const badgeTone: Record<EventType, string> = {
  drone_movement: "border-[#ff5a66]/24 bg-[#102c4b] text-[#ff8a93]",
  fighter_jet_movement: "border-[#ff5a66]/24 bg-[#3f1220] text-[#ff8a93]",
  helicopter_movement: "border-[#ff5a66]/24 bg-[#3b1622] text-[#ff8a93]",
};

const badgeLabel: Record<EventType, string> = {
  drone_movement: "Drone",
  fighter_jet_movement: "Fighter",
  helicopter_movement: "Helicopter",
};

function displayLocation(event: EventRead): string {
  return event.location_name ?? event.region_name ?? "South Lebanon";
}

export default function RawMessageFeed({ events }: RawMessageFeedProps) {
  if (events.length === 0) {
    return (
      <div className="rounded-[1.5rem] border border-dashed border-[#ff5a66]/22 bg-[#061325] p-5 text-sm text-[#ff8a93]">
        No mapped alert news is active right now.
      </div>
    );
  }

  return (
    <div className="max-h-[24rem] space-y-2.5 overflow-y-auto pr-1 sm:max-h-[30rem] lg:max-h-[42rem]">
      {events.map((event) => (
        <article
          key={event.id}
          className="relative overflow-hidden rounded-[1.35rem] border border-[#ff5a66]/16 bg-[#061325]/96 p-3.5 shadow-panel backdrop-blur transition-colors duration-150 hover:border-[#ff5a66]/28 sm:p-4"
        >
          <span className="absolute inset-y-0 left-0 w-1.5 rounded-l-[1.35rem] bg-[#ff5a66]" />
          <div className="pl-2">
            <div className="flex items-center gap-2">
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${badgeTone[event.event_type]}`}>
                Threat
              </span>
              <span className="text-sm font-semibold uppercase tracking-[0.18em] text-[#ff8a93]">
                {badgeLabel[event.event_type]}
              </span>
            </div>

            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#ff8a93]">Village</p>
              <p className="mt-1 text-base font-semibold leading-7 text-[#ff5a66] sm:text-lg">
                {displayLocation(event)}
              </p>
            </div>

            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#ff8a93]">Time</p>
              <p className="mt-1 text-sm font-medium text-[#ff5a66]">
                {formatDateTime(event.event_time)}
              </p>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
