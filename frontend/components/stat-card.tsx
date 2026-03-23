interface StatCardProps {
  label: string;
  value: string | number;
  accent: string;
  helper?: string;
}

export default function StatCard({ label, value, accent, helper }: StatCardProps) {
  return (
    <div className="rounded-[1.6rem] border border-white/60 bg-white/85 p-4 shadow-panel backdrop-blur">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <div className="mt-3 flex items-end justify-between gap-3">
        <p className={`text-3xl font-semibold ${accent}`}>{value}</p>
        {helper ? <p className="max-w-[7rem] text-right text-xs text-slate-500">{helper}</p> : null}
      </div>
    </div>
  );
}
