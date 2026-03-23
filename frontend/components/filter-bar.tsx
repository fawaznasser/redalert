import type { DashboardFilters, EventType, Timeframe } from "@/types";

interface FilterBarProps {
  filters: DashboardFilters;
  resultCount: number;
  mapPointCount: number;
  onTypeChange: (value: EventType | "all") => void;
  onTimeframeChange: (value: Timeframe) => void;
}

export default function FilterBar({
  filters,
  resultCount,
  mapPointCount,
  onTypeChange,
  onTimeframeChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-col gap-4 rounded-[1.8rem] border border-white/60 bg-white/80 p-4 shadow-panel backdrop-blur lg:flex-row lg:items-center lg:justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">Operational Filters</p>
        <p className="mt-2 text-sm text-slate-600">
          {resultCount} active alerts in feed, {mapPointCount} exact points on map.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Type
          <select
            value={filters.type}
            onChange={(event) => onTypeChange(event.target.value as EventType | "all")}
            className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium normal-case tracking-normal text-slate-700 outline-none transition focus:border-ember"
          >
            <option value="all">All alerts</option>
            <option value="drone_movement">Drone</option>
            <option value="fighter_jet_movement">Fighter jet</option>
            <option value="helicopter_movement">Helicopter</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
          Time
          <select
            value={filters.timeframe}
            onChange={(event) => onTimeframeChange(event.target.value as Timeframe)}
            className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium normal-case tracking-normal text-slate-700 outline-none transition focus:border-ember"
          >
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All time</option>
          </select>
        </label>
      </div>
    </div>
  );
}
