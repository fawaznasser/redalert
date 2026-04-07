interface MapLegendProps {
  exactCount: number;
  lang?: "ar" | "en";
  showIncursion?: boolean;
  showAttacks?: boolean;
  mode?: "redalerts" | "firemonitor";
}

const copy = {
  en: {
    title: "Guide",
    drone: "Drone alert",
    fighter: "Fighter alert",
    helicopter: "Helicopter alert",
    incursion: "Incursion alert",
    attackEnemy: "Enemy attack spotlight",
    attackResistance: "Hezbollah attack spotlight",
    weaponGuide: "Weapon icons",
    weaponDrone: "Drone attack",
    weaponFighter: "Fighter attack",
    weaponArtillery: "Artillery attack",
    weaponMissile: "Missile attack",
    summary: (count: number) =>
      `Only exact named locations from the news appear on the map. ${count} active exact points are visible now.`,
  },
  ar: {
    title: "الدليل",
    drone: "مسيّرات",
    fighter: "مقاتلات",
    helicopter: "مروحيات",
    incursion: "توغل",
    attackEnemy: "إبراز هجوم معادٍ",
    attackResistance: "إبراز هجوم حزب الله",
    weaponGuide: "رموز الأسلحة",
    weaponDrone: "هجوم مسيّرة",
    weaponFighter: "هجوم مقاتلة",
    weaponArtillery: "قصف مدفعي",
    weaponMissile: "هجوم صاروخي",
    summary: (count: number) =>
      `تظهر على الخريطة فقط المواقع المسماة بدقة من الأخبار. يوجد الآن ${count} نقاط دقيقة نشطة.`,
  },
} as const;

function legendWeaponGlyph(kind: "ground" | "drone" | "fighter" | "artillery" | "missile"): string {
  if (kind === "ground") {
    return `
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <g fill="currentColor">
          <path d="M8 18.2h11.8l2.8-3.2h2.5c2 0 3.7 1.6 3.7 3.7v2.2H8z"/>
          <path d="M10.4 12.2h9.4v4.2h-9.4z"/>
          <path d="M19.6 13.4h5.7v1.8h-5.7z"/>
          <path d="M7 21.8h22v2.2H7z"/>
          <circle cx="11" cy="25.2" r="2.3"/>
          <circle cx="18.1" cy="25.2" r="2.3"/>
          <circle cx="25.1" cy="25.2" r="2.3"/>
          <path d="M9.5 11.1h8.8v1.5H9.5z"/>
          <path d="M18 11.55h7.2v1.1H18z"/>
        </g>
      </svg>
    `;
  }
  if (kind === "fighter") {
    return "✈";
  }
  if (kind === "artillery") {
    return "☄";
  }
  if (kind === "missile") {
    return `
      <svg viewBox="0 0 32 32" aria-hidden="true">
        <g transform="rotate(-28 16 16)" fill="currentColor">
          <path d="M25.7 6.2c1.2 5.1.2 9.4-3 12.9l-5.8 1.1-5.1-5.1L12.9 9c3.5-3.2 7.8-4.2 12.8-2.8Z"/>
          <path d="M11.9 14.8 17.2 20l-7.6 5.1-3-.8.8-3 4.5-6.5Z"/>
          <path d="M7.5 21.8 4 27.1l2.2.9 5.3-3.5-4-3.8Z"/>
          <path d="M20.7 8.8a2.1 2.1 0 1 1 0 4.2 2.1 2.1 0 0 1 0-4.2Z" fill="#ffffff" opacity=".85"/>
          <path d="M25.2 6.6 28 4l.7 4.2-3.5-1.6Z" opacity=".55"/>
        </g>
      </svg>
    `;
  }
  return `
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="8" cy="8" r="3.2"/>
        <circle cx="24" cy="8" r="3.2"/>
        <circle cx="8" cy="24" r="3.2"/>
        <circle cx="24" cy="24" r="3.2"/>
        <path d="M10.6 10.6 14.1 13.9m7.3-3.3-3.5 3.3m-7.3 4.2 3.5-3.3m7.3 3.3-3.5-3.3"/>
        <rect x="12" y="12.3" width="8" height="7.4" rx="2.2" fill="currentColor" stroke="none"/>
        <path d="M14.6 19.6v2.2m2.8-2.2v2.2"/>
        <path d="M13.6 12.3 12 10.7m6.4 1.6L20 10.7m-6.4 7.3L12 19.6m6.4-1.6 1.6 1.6"/>
      </g>
    </svg>
  `;
}

export default function MapLegend({
  exactCount,
  lang = "en",
  showIncursion = true,
  showAttacks = true,
  mode = "firemonitor",
}: MapLegendProps) {
  const t = copy[lang];
  const showAirThreats = mode !== "firemonitor";
  const summary = mode === "firemonitor" ? null : t.summary(exactCount);
  return (
    <div className="official-panel rounded-[1.7rem] p-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6f82a4]">{t.title}</p>
      <div className="mt-4 flex flex-col gap-3 text-sm text-[#173f91] sm:flex-row sm:flex-wrap sm:gap-5">
        {showAirThreats ? (
          <div className="flex items-center gap-2">
            <span className="relative flex h-5 w-5 items-center justify-center">
              <span className="absolute h-5 w-5 rounded-full bg-[#2d7cff]/25" />
              <span className="absolute h-3.5 w-3.5 rounded-full border border-[#75b5ff]" />
              <span className="h-2 w-2 rounded-full border border-white bg-[#2d7cff]" />
            </span>
            <span>{t.drone}</span>
          </div>
        ) : null}
        {showAirThreats ? (
          <div className="flex items-center gap-2">
            <span className="relative flex h-5 w-5 items-center justify-center">
              <span className="absolute h-5 w-5 rounded-full bg-[#ff4d5f]/25" />
              <span className="absolute h-3.5 w-3.5 rounded-full border border-[#ff99a2]" />
              <span className="h-2 w-2 rounded-full border border-white bg-[#ff4d5f]" />
            </span>
            <span>{t.fighter}</span>
          </div>
        ) : null}
        {showAirThreats ? (
          <div className="flex items-center gap-2">
            <span className="relative flex h-5 w-5 items-center justify-center">
              <span className="absolute h-5 w-5 rounded-full bg-[#ff8f3d]/25" />
              <span className="absolute h-3.5 w-3.5 rounded-full border border-[#ffc491]" />
              <span className="h-2 w-2 rounded-full border border-white bg-[#ff8f3d]" />
            </span>
            <span>{t.helicopter}</span>
          </div>
        ) : null}
        {showIncursion ? (
          <div className="flex items-center gap-2">
            <span className="legend-weapon-icon text-[#29a46b]" dangerouslySetInnerHTML={{ __html: legendWeaponGlyph("ground") }} />
            <span className="text-[#29a46b]">{t.incursion}</span>
          </div>
        ) : null}
        {showAttacks ? (
          <div className="flex items-center gap-2">
            <span className="relative flex h-5 w-5 items-center justify-center">
              <span className="absolute h-5 w-5 animate-ping rounded-full bg-[#6da3ff]/22" />
              <span className="absolute h-3.5 w-3.5 rounded-full border border-[#bfd6ff]" />
              <span className="flex h-2.5 w-2.5 items-center justify-center rounded-full bg-[#174bb8] text-[8px] text-white">✺</span>
            </span>
            <span>{t.attackEnemy}</span>
          </div>
        ) : null}
        {showAttacks ? (
          <div className="flex items-center gap-2">
            <span className="relative flex h-5 w-5 items-center justify-center">
              <span className="absolute h-5 w-5 animate-ping rounded-full bg-[#ffe44d]/28" />
              <span className="absolute h-3.5 w-3.5 rounded-full border border-[#fff0a6]" />
              <span className="flex h-2.5 w-2.5 items-center justify-center rounded-full bg-[#a57d00] text-[8px] text-white">➶</span>
            </span>
            <span>{t.attackResistance}</span>
          </div>
        ) : null}
      </div>
      {mode === "firemonitor" ? (
        <div className="mt-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6f82a4]">{t.weaponGuide}</p>
          <div className="mt-3 flex flex-col gap-3 text-sm text-[#173f91] sm:flex-row sm:flex-wrap sm:gap-5">
            <div className="flex items-center gap-2">
              <span className="legend-weapon-icon text-[#29a46b]" dangerouslySetInnerHTML={{ __html: legendWeaponGlyph("ground") }} />
              <span>{t.incursion}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="legend-weapon-icon text-[#2d7cff]" dangerouslySetInnerHTML={{ __html: legendWeaponGlyph("drone") }} />
              <span>{t.weaponDrone}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="legend-weapon-icon text-[#ff4d5f]" dangerouslySetInnerHTML={{ __html: legendWeaponGlyph("fighter") }} />
              <span>{t.weaponFighter}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="legend-weapon-icon text-[#ff8f3d]" dangerouslySetInnerHTML={{ __html: legendWeaponGlyph("artillery") }} />
              <span>{t.weaponArtillery}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="legend-weapon-icon text-[#8e5cf2]" dangerouslySetInnerHTML={{ __html: legendWeaponGlyph("missile") }} />
              <span>{t.weaponMissile}</span>
            </div>
          </div>
        </div>
      ) : null}
      {summary ? (
        <p className="mt-4 text-sm leading-7 text-[#607393]">
          {summary}
        </p>
      ) : null}
    </div>
  );
}
