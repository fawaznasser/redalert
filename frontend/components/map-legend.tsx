interface MapLegendProps {
  exactCount: number;
  lang?: "ar" | "en";
}

const copy = {
  en: {
    title: "Guide",
    drone: "Drone alert",
    fighter: "Fighter alert",
    helicopter: "Helicopter alert",
    incursion: "Incursion alert",
    summary: (count: number) =>
      `Only exact named locations from the news appear on the map. ${count} active exact points are visible now.`,
  },
  ar: {
    title: "الدليل",
    drone: "إنذار مسيّرات",
    fighter: "إنذار مقاتلات",
    helicopter: "إنذار مروحيات",
    incursion: "إنذار توغل",
    summary: (count: number) =>
      `تظهر على الخريطة فقط المواقع المسماة بدقة من الأخبار. يوجد الآن ${count} نقاط دقيقة نشطة.`,
  },
} as const;

export default function MapLegend({ exactCount, lang = "en" }: MapLegendProps) {
  const t = copy[lang];
  return (
    <div className="official-panel rounded-[1.7rem] p-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6f82a4]">{t.title}</p>
      <div className="mt-4 flex flex-col gap-3 text-sm text-[#173f91] sm:flex-row sm:flex-wrap sm:gap-5">
        <div className="flex items-center gap-2">
          <span className="relative flex h-5 w-5 items-center justify-center">
            <span className="absolute h-5 w-5 rounded-full bg-[#2d7cff]/25" />
            <span className="absolute h-3.5 w-3.5 rounded-full border border-[#75b5ff]" />
            <span className="h-2 w-2 rounded-full border border-white bg-[#2d7cff]" />
          </span>
          <span>{t.drone}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-5 w-5 items-center justify-center">
            <span className="absolute h-5 w-5 rounded-full bg-[#ff4d5f]/25" />
            <span className="absolute h-3.5 w-3.5 rounded-full border border-[#ff99a2]" />
            <span className="h-2 w-2 rounded-full border border-white bg-[#ff4d5f]" />
          </span>
          <span>{t.fighter}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-5 w-5 items-center justify-center">
            <span className="absolute h-5 w-5 rounded-full bg-[#ff8f3d]/25" />
            <span className="absolute h-3.5 w-3.5 rounded-full border border-[#ffc491]" />
            <span className="h-2 w-2 rounded-full border border-white bg-[#ff8f3d]" />
          </span>
          <span>{t.helicopter}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-5 w-5 items-center justify-center">
            <span className="absolute h-5 w-5 rounded-full bg-[#29a46b]/25" />
            <span className="absolute h-3.5 w-3.5 rounded-full border border-[#7fd2a7]" />
            <span className="h-2 w-2 rounded-full border border-white bg-[#29a46b]" />
          </span>
          <span>{t.incursion}</span>
        </div>
      </div>
      <p className="mt-4 text-sm leading-7 text-[#607393]">
        {t.summary(exactCount)}
      </p>
    </div>
  );
}
