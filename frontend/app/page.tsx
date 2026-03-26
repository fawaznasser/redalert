"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import MapLegend from "@/components/map-legend";
import RawMessageFeed from "@/components/raw-message-feed";
import { eventsStreamUrl, fetchDashboardPayload, type DashboardPayload } from "@/lib/api";
import type { DashboardFilters } from "@/types";

const DashboardMap = dynamic(() => import("@/components/dashboard-map"), {
  ssr: false,
  loading: () => (
    <div className="official-panel flex h-full min-h-[420px] items-center justify-center rounded-[1.75rem] text-sm text-[#4b628b]">
      Loading map...
    </div>
  ),
});

const defaultFilters: DashboardFilters = {
  type: "all",
  timeframe: "24h",
  selectedDate: null,
};

const uiCopy = {
  ar: {
    monitor: "لوحة متابعة لبنان",
    title: "الخروقات الجوية",
    subtitle: "Air Violations",
    tracking: "لوحة متابعة",
    activity: "نشاط جوي",
    live: "مباشر",
    connecting: "جاري الاتصال",
    reconnecting: "إعادة الاتصال",
    history: "الأرشيف",
    day: "اليوم",
    liveNow: "الآن",
    liveFeed: "البث المباشر",
    news: "الأخبار",
    summary: "نوع التهديد، البلدة المطابقة، والتوقيت في بيروت فقط.",
    items: "عنصر",
    langAr: "AR",
    langEn: "EN",
    loading: "جاري تحميل البيانات...",
  },
  en: {
    monitor: "Lebanon monitor",
    title: "Air Violations",
    subtitle: "الخروقات الجوية",
    tracking: "Monitor",
    activity: "Air activity",
    live: "Live",
    connecting: "Connecting",
    reconnecting: "Reconnecting",
    history: "History",
    day: "Day",
    liveNow: "Live now",
    liveFeed: "Live feed",
    news: "News",
    summary: "Threat type, mapped village, and Beirut time only.",
    items: "items",
    langAr: "AR",
    langEn: "EN",
    loading: "Loading dashboard data...",
  },
} as const;

export default function HomePage() {
  const [lang, setLang] = useState<"ar" | "en">("ar");
  const [payload, setPayload] = useState<DashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "live" | "reconnecting">("connecting");
  const [selectedDate, setSelectedDate] = useState<string>("");

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => {
    let cancelled = false;
    let stream: EventSource | null = null;

    async function loadData(isInitialLoad = false) {
      try {
        if (!cancelled && isInitialLoad) {
          setLoading(true);
          setError(null);
        }
        const nextPayload = await fetchDashboardPayload({ ...defaultFilters, selectedDate: selectedDate || null });
        if (cancelled) {
          return;
        }
        setPayload(nextPayload);
        setError(null);
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Unable to load dashboard data");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadData(true);

    if (!selectedDate) {
      stream = new EventSource(eventsStreamUrl());
      stream.onopen = () => {
        if (!cancelled) {
          setStreamStatus("live");
        }
      };
      stream.onmessage = () => {
        void loadData();
      };
      stream.onerror = () => {
        if (!cancelled) {
          setStreamStatus("reconnecting");
        }
      };
    } else {
      setStreamStatus("live");
    }

    return () => {
      cancelled = true;
      stream?.close();
    };
  }, [selectedDate]);

  const streamTone =
    streamStatus === "live"
      ? "bg-emerald-500"
      : streamStatus === "connecting"
        ? "bg-amber-500"
        : "bg-rose-500";

  const ui = uiCopy[lang];
  const feedEvents = payload?.events.items ?? [];
  const fighterEvents = feedEvents.filter((event) => event.event_type === "fighter_jet_movement");

  const hasKeyword = (value: string, keywords: string[]) => keywords.some((keyword) => value.includes(keyword));
  const coastKeywords = ["الساحل", "ساحل"];
  const beirutKeywords = ["فوق بيروت", "فوق_بيروت", "اعلى بيروت", "أعلى بيروت"];
  const beirutBoundKeywords = ["باتجاه بيروت", "باتجاه_بيروت", "اتجاه بيروت"];
  const southKeywords = ["فوق الجنوب", "فوق_الجنوب", "فوق جنوب", "جنوب لبنان", "الجنوب"];

  const hasActiveFighterAlert = fighterEvents.length > 0;
  const hasActiveHelicopterAlert = feedEvents.some((event) => event.event_type === "helicopter_movement");

  const renderCoastFighterThreat = fighterEvents.some(
    (event) =>
      (event.location_name ? hasKeyword(event.location_name, coastKeywords) : false) ||
      hasKeyword(event.source_text, coastKeywords),
  );

  const renderBeirutFighterThreat = fighterEvents.some((event) => hasKeyword(event.source_text, beirutKeywords));

  const renderBeirutBoundFighterThreat = fighterEvents.some((event) =>
    hasKeyword(event.source_text, beirutBoundKeywords),
  );

  const renderSouthFighterThreat = fighterEvents.some((event) => {
    const regionalSouthFighter =
      !event.location_name &&
      (event.region_slug === "south-lebanon" ||
        event.region_name === "South Lebanon" ||
        event.region_name === "جنوب لبنان");

    return (
      regionalSouthFighter &&
      !hasKeyword(event.source_text, coastKeywords) &&
      !hasKeyword(event.source_text, beirutKeywords) &&
      !hasKeyword(event.source_text, beirutBoundKeywords) &&
      (hasKeyword(event.source_text, southKeywords) || regionalSouthFighter)
    );
  });

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-[1440px] px-4 py-5 sm:px-6 sm:py-7 lg:px-7 lg:py-8">
        <header className="official-panel mb-4 flex flex-col gap-4 rounded-[2rem] px-5 py-5 sm:mb-6 sm:flex-row sm:items-center sm:justify-between sm:px-7 sm:py-6">
          <div className="space-y-2">
            <p className="text-[11px] font-semibold tracking-[0.18em] text-[#6f82a4]">{ui.monitor}</p>
            <h1 className="text-[1.85rem] font-bold tracking-[0.04em] text-[#ff5a66] sm:text-[2.5rem]">{ui.title}</h1>
            <p className="text-sm font-semibold tracking-[0.22em] text-[#173f91]">{ui.subtitle}</p>
          </div>
          <div className="flex flex-col gap-3 sm:items-end">
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex overflow-hidden rounded-full border border-[#ced9ef] bg-white">
                <button
                  type="button"
                  onClick={() => setLang("ar")}
                  className={`px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                    lang === "ar" ? "bg-[#173f91] text-white" : "text-[#35598e]"
                  }`}
                >
                  {ui.langAr}
                </button>
                <button
                  type="button"
                  onClick={() => setLang("en")}
                  className={`px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                    lang === "en" ? "bg-[#173f91] text-white" : "text-[#35598e]"
                  }`}
                >
                  {ui.langEn}
                </button>
              </div>
              <span className="official-subtle-pill rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                {ui.tracking}
              </span>
              <span className="official-subtle-pill rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                {ui.activity}
              </span>
            </div>
            <div className="inline-flex items-center gap-3 self-start rounded-full border border-[#ced9ef] bg-white px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#35598e] shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] sm:self-auto">
              <span className={`h-2.5 w-2.5 rounded-full ${streamTone} ${streamStatus === "live" ? "animate-pulse" : ""}`} />
              {selectedDate
                ? `${ui.history} ${selectedDate}`
                : streamStatus === "live"
                  ? ui.live
                  : streamStatus === "connecting"
                    ? ui.connecting
                    : ui.reconnecting}
            </div>
          </div>
        </header>

        <div className="official-panel mb-4 rounded-[1.75rem] px-4 py-3 sm:mb-6 sm:px-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="official-pill rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.16em]">
              {ui.day}
            </span>
            <label className="official-subtle-pill flex items-center gap-2 rounded-full px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em]">
              <input
                type="date"
                min="2026-03-02"
                max={new Date().toISOString().slice(0, 10)}
                value={selectedDate}
                onChange={(event) => setSelectedDate(event.target.value)}
                className="min-w-[10.5rem] bg-transparent text-[#35598e] outline-none"
              />
            </label>
            {selectedDate ? (
              <button
                type="button"
                onClick={() => setSelectedDate("")}
                className="official-pill rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.16em]"
              >
                {ui.liveNow}
              </button>
            ) : null}
          </div>
        </div>

        {error ? (
          <div className="mb-5 rounded-[1.5rem] border border-[#f3c7cb] bg-[#fff7f8] p-4 text-sm text-[#8d4250]">
            {error}
          </div>
        ) : null}

        <section className="space-y-4 sm:space-y-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(320px,400px)] lg:gap-6">
            <div className="lg:col-start-1">
              <DashboardMap
                points={payload?.map.points ?? []}
                lang={lang}
                hasActiveFighterAlert={hasActiveFighterAlert}
                hasActiveHelicopterAlert={hasActiveHelicopterAlert}
                hasCoastFighterThreat={renderCoastFighterThreat}
                hasBeirutFighterThreat={renderBeirutFighterThreat}
                hasBeirutBoundFighterThreat={renderBeirutBoundFighterThreat}
                hasSouthFighterThreat={renderSouthFighterThreat}
              />
            </div>
            <aside className="official-panel rounded-[1.8rem] p-5 lg:col-start-2 lg:row-span-2 lg:row-start-1">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6f82a4]">{ui.liveFeed}</p>
                  <h2 className="mt-3 text-[2rem] font-bold text-[#173f91]">{ui.news}</h2>
                </div>
                <div className="official-subtle-pill rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.16em]">
                  {feedEvents.length} {ui.items}
                </div>
              </div>
              <p className="mt-3 text-sm leading-7 text-[#607393]">{ui.summary}</p>

              {loading && !payload ? (
                <div className="mt-5 rounded-[1.4rem] border border-[#d5deed] bg-[#fbfcff] p-5 text-sm text-[#607393]">
                  {ui.loading}
                </div>
              ) : null}

              {payload ? (
                <div className="mt-5">
                  <RawMessageFeed events={feedEvents} lang={lang} />
                </div>
              ) : null}
            </aside>
            <div className="lg:col-start-1">
              <MapLegend exactCount={payload?.map.points.length ?? 0} lang={lang} />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
