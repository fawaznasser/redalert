import type { Metadata } from "next";

import DashboardPage from "@/components/dashboard-page";
import type { DashboardPayload } from "@/lib/api";

export const metadata: Metadata = {
  title: "مراقبة العمليات العسكرية | Fire Monitor",
  description: "Cross-border fire activity dashboard for RNN and related alert sources",
};

export const dynamic = "force-dynamic";
const INITIAL_FETCH_TIMEOUT_MS = 1500;

async function fetchInitialFireMonitorPayload(): Promise<DashboardPayload | null> {
  const params = new URLSearchParams();
  params.set("limit", "24");
  params.set("map_limit", "80");
  params.set("raw_limit", "8");
  params.set("include_raw_messages", "false");
  params.set("include_regions", "false");
  params.set("include_pipeline", "false");
  params.set("combat_only", "true");
  params.set("active_only", "false");
  params.append("channel", "RNN_Alerts_AR_Lebanon");
  params.append("channel", "alichoeib1970");

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), INITIAL_FETCH_TIMEOUT_MS);
    const response = await fetch(`http://127.0.0.1:8091/dashboard?${params.toString()}`, {
      cache: "no-store",
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));
    if (!response.ok) {
      return null;
    }

    const payload = await response.json();
    return {
      stats: payload.stats,
      events: payload.events,
      map: payload.map,
      regions: payload.regions,
      rawMessages: payload.raw_messages,
      pipeline: payload.pipeline,
      snapshotAt: payload.snapshot_at,
    };
  } catch {
    return null;
  }
}

export default async function FireMonitorPage() {
  const initialPayload = await fetchInitialFireMonitorPayload();

  return (
    <DashboardPage
      channels={["RNN_Alerts_AR_Lebanon", "alichoeib1970"]}
      mode="firemonitor"
      titleAr="مراقبة العمليات العسكرية"
      titleEn="Fire Monitor"
      subtitleAr="النيران العابرة للحدود"
      subtitleEn="RNN & Cross-Border Fire Activity"
      initialPayload={initialPayload}
    />
  );
}
