import { displayEventLocation, displayEventTypeLabel, formatDateTime, isResistanceActionEvent } from "@/lib/format";
import type { EventRead, EventType } from "@/types";

interface RawMessageFeedProps {
  events: EventRead[];
  lang?: "ar" | "en";
  showAttackSide?: boolean;
}

const badgeTone: Record<EventType, string> = {
  drone_movement: "border-[#7aaeff]/30 bg-[#eef5ff] text-[#35598e]",
  fighter_jet_movement: "border-[#7aaeff]/30 bg-[#eef5ff] text-[#35598e]",
  helicopter_movement: "border-[#7aaeff]/30 bg-[#eef5ff] text-[#35598e]",
  ground_incursion: "border-[#7fd2a7]/40 bg-[#eefaf3] text-[#2c6a48]",
};

const accentTone: Record<EventType, string> = {
  drone_movement: "bg-[#7aaeff]",
  fighter_jet_movement: "bg-[#ff8d97]",
  helicopter_movement: "bg-[#ffc491]",
  ground_incursion: "bg-[#29a46b]",
};

const copy = {
  en: {
    empty: "No mapped alert news is active right now.",
    threat: "Threat",
    village: "Village",
    time: "Time",
  },
  ar: {
    empty: "لا توجد أخبار إنذارات مع مواقع دقيقة في الوقت الحالي.",
    threat: "التهديد",
    village: "البلدة",
    time: "الوقت",
  },
} as const;

export default function RawMessageFeed({ events, lang = "en", showAttackSide = true }: RawMessageFeedProps) {
  const t = copy[lang];
  if (events.length === 0) {
    return (
      <div className="rounded-[1.45rem] border border-dashed border-[#c8d5ea] bg-[#fbfcff] p-5 text-sm text-[#607393]">
        {t.empty}
      </div>
    );
  }

  return (
    <div className="max-h-[24rem] space-y-2.5 overflow-y-auto pr-1 sm:max-h-[30rem] lg:max-h-[42rem]">
      {events.map((event) => {
        const isResistance = isResistanceActionEvent(event);
        const isEnemyAttack = showAttackSide && event.attack_side === "enemy_attack";
        const resolvedBadgeTone = isResistance
          ? "border-[#ffe896] bg-[#fff9d8] text-[#a57d00]"
          : isEnemyAttack
            ? "border-[#cfe0ff] bg-[#edf4ff] text-[#174bb8]"
            : badgeTone[event.event_type];
        const resolvedAccentTone = isResistance ? "bg-[#ffe44d]" : isEnemyAttack ? "bg-[#4f8dff]" : accentTone[event.event_type];
        const threatLabel = displayEventTypeLabel(event, lang);

        return (
          <article
            key={event.id}
            className="relative overflow-hidden rounded-[1.45rem] border border-[#d3ddec] bg-white p-4 transition-colors duration-150 hover:border-[#adc0e2] sm:p-4"
          >
            <span className={`absolute inset-y-0 left-0 w-1.5 rounded-l-[1.45rem] ${resolvedAccentTone}`} />
            <div className="pl-2.5">
              <div className="flex items-center gap-2.5">
                <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${resolvedBadgeTone}`}>
                  {threatLabel}
                </span>
              </div>

              <div className="mt-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6f82a4]">{t.village}</p>
                <p className="mt-1 text-base font-bold leading-7 text-[#173f91] sm:text-lg">
                  {displayEventLocation(event, lang)}
                </p>
              </div>

              <div className="mt-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6f82a4]">{t.time}</p>
                <p className="mt-1 text-sm font-medium text-[#607393]">
                  {formatDateTime(event.event_time)}
                </p>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
