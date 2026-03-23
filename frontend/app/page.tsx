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
    <div className="flex h-full min-h-[420px] items-center justify-center rounded-[2rem] border border-[#ff5a66]/20 bg-[#081a31]/88 text-sm text-[#ff8a93] shadow-panel backdrop-blur">
      Loading map...
    </div>
  ),
});

const defaultFilters: DashboardFilters = {
  type: "all",
  timeframe: "24h",
};

export default function HomePage() {
  const [payload, setPayload] = useState<DashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "live" | "reconnecting">("connecting");

  useEffect(() => {
    let cancelled = false;
    let stream: EventSource | null = null;

    async function loadData(isInitialLoad = false) {
      try {
        if (!cancelled && isInitialLoad) {
          setLoading(true);
          setError(null);
        }
        const nextPayload = await fetchDashboardPayload(defaultFilters);
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

    const interval = window.setInterval(() => {
      void loadData();
    }, 10000);

    return () => {
      cancelled = true;
      stream?.close();
      window.clearInterval(interval);
    };
  }, []);

  const streamTone =
    streamStatus === "live"
      ? "bg-emerald-500"
      : streamStatus === "connecting"
        ? "bg-amber-500"
        : "bg-ember";

  const feedEvents = payload?.events.items ?? [];
  const hasActiveFighterAlert = feedEvents.some((event) => event.event_type === "fighter_jet_movement");
  const hasActiveHelicopterAlert = feedEvents.some((event) => event.event_type === "helicopter_movement");

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-[1420px] px-4 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-8">
        <header className="mb-4 flex flex-col gap-3 rounded-[1.8rem] border border-[#ff5a66]/20 bg-[#081a31]/88 px-5 py-4 shadow-panel backdrop-blur sm:mb-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <h1 className="text-[2rem] font-semibold uppercase tracking-[0.18em] text-[#ff5a66] sm:text-[2.7rem] sm:tracking-[0.28em]">
            Red Alert
          </h1>
          <div className="inline-flex items-center gap-3 self-start rounded-full border border-[#ff5a66]/18 bg-[#061325] px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#ff8a93] shadow-panel sm:self-auto">
            <span className={`h-2.5 w-2.5 rounded-full ${streamTone} ${streamStatus === "live" ? "animate-pulse" : ""}`} />
            {streamStatus === "live" ? "Live" : streamStatus === "connecting" ? "Connecting" : "Reconnecting"}
          </div>
        </header>

        {error ? (
          <div className="mb-5 rounded-[1.8rem] border border-[#ff5a66]/35 bg-[#3a0d17]/45 p-4 text-sm text-[#ff7b86] shadow-panel">
            {error}
          </div>
        ) : null}

        <section className="space-y-4 sm:space-y-5">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,380px)] lg:gap-5">
            <div className="lg:col-start-1">
              <DashboardMap
                points={payload?.map.points ?? []}
                hasActiveFighterAlert={hasActiveFighterAlert}
                hasActiveHelicopterAlert={hasActiveHelicopterAlert}
              />
            </div>
            <div className="lg:col-start-1">
              <MapLegend exactCount={payload?.map.points.length ?? 0} />
            </div>

            <aside className="rounded-[1.8rem] border border-[#ff5a66]/20 bg-[#081a31]/90 p-4 shadow-panel backdrop-blur sm:p-5 lg:col-start-2 lg:row-span-2 lg:row-start-1">
              <div>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#ff8a93]">Live feed</p>
                    <h2 className="mt-2 text-xl font-semibold text-[#ff5a66] sm:text-2xl">News</h2>
                  </div>
                  <div className="rounded-full border border-[#ff5a66]/18 bg-[#061325] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#ff8a93]">
                    {feedEvents.length} items
                  </div>
                </div>
                <p className="mt-2 text-sm leading-6 text-[#ff8a93]">
                  Threat type, mapped village, and Beirut time only.
                </p>
              </div>

              {loading && !payload ? (
                <div className="mt-4 rounded-[1.5rem] border border-[#ff5a66]/18 bg-[#061325] p-5 text-sm text-[#ff8a93] shadow-panel backdrop-blur">
                  Loading dashboard data...
                </div>
              ) : null}

              {payload ? <div className="mt-4"><RawMessageFeed events={feedEvents} /></div> : null}
            </aside>
          </div>
        </section>
      </div>
    </main>
  );
}
