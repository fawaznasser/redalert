interface PipelineStatusProps {
  rawMessages: number;
  structuredMessages: number;
  mappedMessages: number;
  visiblePoints: number;
}

const cards = [
  { key: "raw", label: "Telegram Input", tone: "text-slate-900" },
  { key: "structured", label: "Parsed Alerts", tone: "text-ember" },
  { key: "mapped", label: "Mapped Locations", tone: "text-steel" },
  { key: "visible", label: "Visible Points", tone: "text-olive" },
] as const;

export default function PipelineStatus({
  rawMessages,
  structuredMessages,
  mappedMessages,
  visiblePoints,
}: PipelineStatusProps) {
  const values = {
    raw: rawMessages,
    structured: structuredMessages,
    mapped: mappedMessages,
    visible: visiblePoints,
  } as const;

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <div key={card.key} className="rounded-[1.5rem] border border-white/60 bg-white/82 p-4 shadow-panel backdrop-blur">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">{card.label}</p>
          <p className={`mt-3 text-3xl font-semibold ${card.tone}`}>{values[card.key]}</p>
        </div>
      ))}
    </div>
  );
}
