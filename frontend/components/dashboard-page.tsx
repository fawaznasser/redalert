"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import MapLegend from "@/components/map-legend";
import RawMessageFeed from "@/components/raw-message-feed";
import { eventsStreamUrl, fetchDashboardPayload, normalizeSelectedDate, type DashboardPayload } from "@/lib/api";
import { isFireMonitorCombatEvent } from "@/lib/format";
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

interface LiveAction {
  id: string;
  event_type: string;
  location_name?: string | null;
  region_name?: string | null;
  attack_side?: "enemy_attack" | "resistance_attack" | null;
  event_time: string;
}

interface StreamPayload {
  kind?: string;
  actions?: LiveAction[];
}

const uiCopy = {
  redalerts: {
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
  },
  firemonitor: {
    ar: {
      monitor: "مراقبة العمليات العسكرية",
      title: "مراقبة العمليات العسكرية",
      subtitle: "النيران العابرة للحدود",
      tracking: "مراقبة النيران",
      activity: "نشاط ميداني",
      live: "مباشر",
      connecting: "جاري الاتصال",
      reconnecting: "إعادة الاتصال",
      history: "الأرشيف",
      day: "اليوم",
      liveNow: "الآن",
      liveFeed: "المتابعة الميدانية",
      news: "الأخبار",
      summary: "التوغلات والهجمات المعادية وهجمات المقاومة فقط، مع الموقع المطابق والتوقيت في بيروت.",
      items: "عنصر",
      langAr: "AR",
      langEn: "EN",
      loading: "جاري تحميل بيانات مراقبة العمليات العسكرية...",
    },
    en: {
      monitor: "Fire Monitor",
      title: "Fire Monitor",
      subtitle: "Cross-Border Fire Activity",
      tracking: "Fire monitor",
      activity: "Field activity",
      live: "Live",
      connecting: "Connecting",
      reconnecting: "Reconnecting",
      history: "History",
      day: "Day",
      liveNow: "Live now",
      liveFeed: "Field feed",
      news: "News",
      summary: "Only incursions, enemy attacks, and resistance actions with mapped locations and Beirut time.",
      items: "items",
      langAr: "AR",
      langEn: "EN",
      loading: "Loading Fire Monitor data...",
    },
  },
} as const;

export interface DashboardPageProps {
  channels: string[];
  titleAr?: string;
  titleEn?: string;
  subtitleAr?: string;
  subtitleEn?: string;
  mode?: "redalerts" | "firemonitor";
  initialPayload?: DashboardPayload | null;
}

export default function DashboardPage({
  channels,
  titleAr,
  titleEn,
  subtitleAr,
  subtitleEn,
  mode = "firemonitor",
  initialPayload = null,
}: DashboardPageProps) {
  const [lang, setLang] = useState<"ar" | "en">("ar");
  const [payload, setPayload] = useState<DashboardPayload | null>(initialPayload);
  const [loadedSelectedDate, setLoadedSelectedDate] = useState<string | null>(initialPayload ? null : null);
  const [loading, setLoading] = useState(initialPayload == null);
  const [error, setError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "live" | "reconnecting">("connecting");
  const [selectedDate, setSelectedDate] = useState<string>("");
  const normalizedSelectedDate = normalizeSelectedDate(selectedDate) ?? "";
  const apiBaseUrl =
    typeof window !== "undefined"
      ? window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
        ? mode === "redalerts"
          ? `${window.location.protocol}//${window.location.hostname}:8090`
          : `${window.location.protocol}//${window.location.hostname}:8091`
        : `${window.location.origin}${mode === "redalerts" ? "/redalerts/api" : "/firemonitor/api"}`
      : mode === "redalerts"
        ? "/redalerts/api"
        : "/firemonitor/api";
  const fireMonitorHref =
    typeof window !== "undefined"
      ? window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
        ? `${window.location.origin}/redalerts/firemonitor`
        : `${window.location.origin}/firemonitor`
      : "/firemonitor";
  const redAlertsHref =
    typeof window !== "undefined"
      ? `${window.location.origin}/redalerts`
      : "/redalerts";

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => {
    let cancelled = false;
    let stream: EventSource | null = null;
    const canReuseInitialPayload = !selectedDate && payload !== null && loadedSelectedDate === null;

    async function loadData(isInitialLoad = false) {
      try {
        const preserveExistingPayload = isInitialLoad && !selectedDate && payload !== null;
        if (!cancelled && isInitialLoad && !preserveExistingPayload) {
          setLoading(true);
          setError(null);
          setPayload(null);
        }
        const nextPayload = await fetchDashboardPayload(
          { ...defaultFilters, selectedDate: normalizedSelectedDate || null },
          { channels, baseUrl: apiBaseUrl, combatOnly: mode === "firemonitor" },
        );
        if (cancelled) {
          return;
        }
        setPayload(nextPayload);
        setLoadedSelectedDate(normalizedSelectedDate || null);
        setError(null);
      } catch (nextError) {
        if (!cancelled) {
          setPayload(null);
          setLoadedSelectedDate(null);
          setError(nextError instanceof Error ? nextError.message : "Unable to load dashboard data");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    if (!canReuseInitialPayload) {
      void loadData(true);
    } else {
      setLoading(false);
      setError(null);
    }

    if (!selectedDate) {
      stream = new EventSource(eventsStreamUrl(apiBaseUrl));
      stream.onopen = () => {
        if (!cancelled) {
          setStreamStatus("live");
        }
      };
      stream.onmessage = (event) => {
        try {
          JSON.parse(event.data as string) as StreamPayload;
        } catch {
          // Keep the stream resilient even if an update payload is malformed.
        }
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
  }, [selectedDate, normalizedSelectedDate, channels, apiBaseUrl, mode]);

  const ui = uiCopy[mode][lang];
  const isPayloadCurrent =
    normalizedSelectedDate
      ? loadedSelectedDate === normalizedSelectedDate
      : loadedSelectedDate === null;
  const currentPayload = isPayloadCurrent ? payload : null;
  const feedEvents = currentPayload?.events.items ?? [];
  const mapPoints = currentPayload?.map.points ?? [];
  const regionalEvents = currentPayload?.map.regional_events ?? [];
  const hideAttackAndIncursion = mode === "redalerts";
  const fireMonitorOnlyCombat = mode === "firemonitor";
  const visibleEvents = hideAttackAndIncursion
    ? feedEvents.filter((event) => event.event_type !== "ground_incursion" && !event.attack_side)
    : fireMonitorOnlyCombat
      ? feedEvents.filter((event) => isFireMonitorCombatEvent(event))
      : feedEvents;
  const visibleMapPoints = hideAttackAndIncursion
    ? mapPoints.filter((point) => point.event_type !== "ground_incursion" && !point.attack_side)
    : fireMonitorOnlyCombat
      ? mapPoints.filter((point) => isFireMonitorCombatEvent(point))
      : mapPoints;
  const visibleRegionalEvents = hideAttackAndIncursion
    ? regionalEvents.filter((event) => event.event_type !== "ground_incursion" && !event.attack_side)
    : fireMonitorOnlyCombat
      ? regionalEvents.filter((event) => isFireMonitorCombatEvent(event))
      : regionalEvents;
  const isFlightThreatText = (value: string) => {
    const text = value.toLowerCase();
    return (
      text.includes("تحليق") ||
      text.includes("حربي بالاجواء") ||
      text.includes("حربي بالأجواء") ||
      text.includes("فوق بيروت") ||
      text.includes("باتجاه بيروت") ||
      text.includes("الساحل")
    );
  };
  const effectiveStreamStatus =
    selectedDate
      ? "historical"
      : payload && !error && streamStatus !== "reconnecting"
        ? "live"
        : streamStatus;
  const effectiveStreamTone =
    effectiveStreamStatus === "live"
      ? "bg-emerald-500"
      : effectiveStreamStatus === "historical"
        ? "bg-slate-400"
        : effectiveStreamStatus === "connecting"
          ? "bg-amber-500"
          : "bg-rose-500";
  const fighterEvents = visibleEvents.filter(
    (event) => event.event_type === "fighter_jet_movement" && isFlightThreatText(event.source_text),
  );
  const showSharedThreatOverlays = mode === "redalerts";

  const hasKeyword = (value: string, keywords: string[]) => keywords.some((keyword) => value.includes(keyword));
  const coastKeywords = ["الساحل", "ساحل"];
  const beirutKeywords = ["فوق بيروت", "فوق_بيروت", "اعلى بيروت", "أعلى بيروت"];
  const beirutBoundKeywords = ["باتجاه بيروت", "باتجاه_بيروت", "اتجاه بيروت"];
  const southKeywords = ["فوق الجنوب", "فوق_الجنوب", "فوق جنوب", "جنوب لبنان", "الجنوب"];

  const hasActiveFighterAlert = showSharedThreatOverlays && fighterEvents.length > 0;
  const hasActiveHelicopterAlert =
    showSharedThreatOverlays && visibleEvents.some((event) => event.event_type === "helicopter_movement");

  const renderCoastFighterThreat = showSharedThreatOverlays && fighterEvents.some(
    (event) =>
      (event.location_name ? hasKeyword(event.location_name, coastKeywords) : false) ||
      hasKeyword(event.source_text, coastKeywords),
  );

  const renderBeirutFighterThreat =
    showSharedThreatOverlays && fighterEvents.some((event) => hasKeyword(event.source_text, beirutKeywords));
  const renderBeirutBoundFighterThreat =
    showSharedThreatOverlays && fighterEvents.some((event) => hasKeyword(event.source_text, beirutBoundKeywords));
  const renderSouthFighterThreat = showSharedThreatOverlays && fighterEvents.some((event) => {
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
            <h1 className="text-[1.85rem] font-bold tracking-[0.04em] text-[#ff5a66] sm:text-[2.5rem]">
              {lang === "ar" ? (titleAr ?? ui.title) : (titleEn ?? ui.title)}
            </h1>
            <p className="text-sm font-semibold tracking-[0.22em] text-[#173f91]">
              {lang === "ar" ? (subtitleAr ?? ui.subtitle) : (subtitleEn ?? ui.subtitle)}
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:items-end">
            {mode === "firemonitor" ? (
              <a
                href={redAlertsHref}
                target="_top"
                className="official-pill self-start rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] sm:self-end"
              >
                {lang === "ar" ? "العودة إلى Red Alerts" : "Back to Red Alerts"}
              </a>
            ) : null}
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
              {mode === "redalerts" ? (
                <>
                  <span className="official-subtle-pill rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                    {ui.tracking}
                  </span>
                  <span className="official-subtle-pill rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
                    {ui.activity}
                  </span>
                </>
              ) : null}
              {mode === "redalerts" ? (
                <a
                  href={fireMonitorHref}
                  className="official-pill rounded-full px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.16em]"
                >
                  Fire Monitor
                </a>
              ) : null}
            </div>
            <div className="inline-flex items-center gap-3 self-start rounded-full border border-[#ced9ef] bg-white px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#35598e] shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] sm:self-auto">
              <span
                className={`h-2.5 w-2.5 rounded-full ${effectiveStreamTone} ${effectiveStreamStatus === "live" ? "animate-pulse" : ""}`}
              />
              {selectedDate
                ? `${ui.history} ${normalizedSelectedDate || selectedDate}`
                : effectiveStreamStatus === "live"
                  ? ui.live
                  : effectiveStreamStatus === "connecting"
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
                value={normalizedSelectedDate}
                onChange={(event) => setSelectedDate(normalizeSelectedDate(event.target.value) ?? "")}
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
                points={visibleMapPoints}
                regionalEvents={visibleRegionalEvents}
                lang={lang}
                mode={mode}
                historicalMode={Boolean(selectedDate)}
                hasActiveFighterAlert={hasActiveFighterAlert}
                hasActiveHelicopterAlert={hasActiveHelicopterAlert}
                hasCoastFighterThreat={renderCoastFighterThreat}
                hasBeirutFighterThreat={renderBeirutFighterThreat}
                hasBeirutBoundFighterThreat={renderBeirutBoundFighterThreat}
                hasSouthFighterThreat={renderSouthFighterThreat}
              />
            </div>
            <div className="space-y-4 lg:col-start-2">
              <MapLegend
                exactCount={visibleMapPoints.length}
                lang={lang}
                showIncursion={!hideAttackAndIncursion}
                showAttacks={!hideAttackAndIncursion}
                mode={mode}
              />
              {loading && !currentPayload ? (
                <div className="official-panel rounded-[1.75rem] p-5 text-sm text-[#607393]">{ui.loading}</div>
              ) : (
                <div className="official-panel rounded-[1.75rem] p-5">
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6f82a4]">{ui.news}</p>
                      <h2 className="mt-2 text-xl font-bold tracking-[0.04em] text-[#173f91]">{ui.liveFeed}</h2>
                    </div>
                    <span className="official-subtle-pill rounded-full px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em]">
                      {visibleEvents.length} {ui.items}
                    </span>
                  </div>
                  <p className="mb-4 text-sm leading-7 text-[#607393]">{ui.summary}</p>
                  <RawMessageFeed events={visibleEvents} lang={lang} showAttackSide={!hideAttackAndIncursion} />
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
