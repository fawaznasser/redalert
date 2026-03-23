interface MapLegendProps {
  exactCount: number;
}

export default function MapLegend({ exactCount }: MapLegendProps) {
  return (
    <div className="rounded-[1.5rem] border border-[#ff5a66]/20 bg-[#081a31]/88 p-4 shadow-panel backdrop-blur">
      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#ff8a93]">Guide</p>
      <div className="mt-3 flex flex-col gap-3 text-sm text-[#ff8a93] sm:flex-row sm:flex-wrap sm:gap-4">
        <div className="flex items-center gap-2">
          <span className="relative flex h-5 w-5 items-center justify-center">
            <span className="absolute h-5 w-5 rounded-full bg-[#2d7cff]/25" />
            <span className="absolute h-3.5 w-3.5 rounded-full border border-[#75b5ff]" />
            <span className="h-2 w-2 rounded-full border border-white bg-[#2d7cff]" />
          </span>
          <span>Drone alert</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-5 w-5 items-center justify-center">
            <span className="absolute h-5 w-5 rounded-full bg-[#ff4d5f]/25" />
            <span className="absolute h-3.5 w-3.5 rounded-full border border-[#ff99a2]" />
            <span className="h-2 w-2 rounded-full border border-white bg-[#ff4d5f]" />
          </span>
          <span>Fighter alert</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-5 w-5 items-center justify-center">
            <span className="absolute h-5 w-5 rounded-full bg-[#ff8f3d]/25" />
            <span className="absolute h-3.5 w-3.5 rounded-full border border-[#ffc491]" />
            <span className="h-2 w-2 rounded-full border border-white bg-[#ff8f3d]" />
          </span>
          <span>Helicopter alert</span>
        </div>
      </div>
      <p className="mt-3 text-sm leading-6 text-[#ff8a93]">
        Only exact named locations from the news appear on the map. {exactCount} active exact points are visible now.
      </p>
    </div>
  );
}
