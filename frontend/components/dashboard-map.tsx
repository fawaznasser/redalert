"use client";

import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useEffect } from "react";

import { eventTypeLabel, formatDateTime, formatRelativeTime } from "@/lib/format";
import type { EventRead, MapPoint } from "@/types";

interface DashboardMapProps {
  points: MapPoint[];
  hasActiveFighterAlert?: boolean;
  hasActiveHelicopterAlert?: boolean;
}

const markerStyles = {
  drone_movement: { radius: 9, fill: "#2d7cff", ring: "#75b5ff" },
  fighter_jet_movement: { radius: 8, fill: "#ff4d5f", ring: "#ff99a2" },
  helicopter_movement: { radius: 8, fill: "#ff8f3d", ring: "#ffc491" },
} as const;

const LEBANON_BOUNDS: [[number, number], [number, number]] = [
  [33.0, 35.05],
  [34.72, 36.7],
];
const MAP_CENTER: [number, number] = [33.88, 35.86];
const MAP_DEFAULT_ZOOM = 9;
const MAP_MAX_ZOOM = 18;

function MapViewportController() {
  const map = useMap();

  useEffect(() => {
    map.fitBounds(LEBANON_BOUNDS, { padding: [12, 12] });
    map.setMaxBounds(LEBANON_BOUNDS);
  }, [map]);

  return null;
}

export default function DashboardMap({
  points,
  hasActiveFighterAlert = false,
  hasActiveHelicopterAlert = false,
}: DashboardMapProps) {
  return (
    <div className="relative h-full min-h-[380px] overflow-hidden rounded-[1.8rem] border border-[#ff5a66]/20 bg-[#081a31] shadow-panel sm:min-h-[460px] lg:min-h-[640px]">
      {hasActiveFighterAlert || hasActiveHelicopterAlert ? (
        <div className="pointer-events-none absolute right-3 top-3 z-[1000] flex flex-col items-end gap-2 sm:right-4 sm:top-4">
          {hasActiveFighterAlert ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-[#ff7f89]/35 bg-[#460b16]/92 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#ff9ea6] shadow-panel backdrop-blur">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#ff4d5f] opacity-60" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-[#ff4d5f]" />
              </span>
              Fighters Threat
            </div>
          ) : null}
          {hasActiveHelicopterAlert ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-[#ffc491]/35 bg-[#4a2200]/92 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#ffc491] shadow-panel backdrop-blur">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#ff8f3d] opacity-60" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-[#ff8f3d]" />
              </span>
              Helicopter Threat
            </div>
          ) : null}
        </div>
      ) : null}

      <MapContainer
        center={MAP_CENTER}
        zoom={MAP_DEFAULT_ZOOM}
        className="h-full w-full"
        maxBounds={LEBANON_BOUNDS}
        maxBoundsViscosity={1}
        maxZoom={MAP_MAX_ZOOM}
        minZoom={8}
        scrollWheelZoom
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapViewportController />

        {points.map((point) => (
          <CircleMarker
            key={point.id}
            center={[point.latitude, point.longitude]}
            radius={markerStyles[point.event_type].radius}
            pathOptions={{
              color: markerStyles[point.event_type].ring,
              fillColor: markerStyles[point.event_type].fill,
              fillOpacity: 0.92,
              weight: 3,
            }}
          >
            <Tooltip direction="top" offset={[0, -18]}>
              <div className="space-y-1">
                <p className="font-semibold">{point.location_name ?? "Unknown location"}</p>
                <p className="text-xs">{eventTypeLabel(point.event_type)}</p>
              </div>
            </Tooltip>
            <Popup>
              <div className="space-y-1">
                <p className="font-semibold">{point.location_name ?? "Unknown location"}</p>
                <p>{eventTypeLabel(point.event_type)}</p>
                <p>{formatDateTime(point.event_time)}</p>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>

      {points.length === 0 ? (
        <div className="pointer-events-none absolute inset-x-3 bottom-3 rounded-2xl border border-[#ff5a66]/18 bg-[#061325]/92 p-3 text-sm text-[#ff8a93] shadow-panel backdrop-blur sm:inset-x-4 sm:bottom-4 sm:p-4">
          No exact locations are active on the map right now.
        </div>
      ) : (
        <div className="pointer-events-none absolute right-4 top-24 hidden w-[17rem] rounded-2xl border border-[#ff5a66]/18 bg-[#061325]/94 p-4 text-sm text-[#ff8a93] shadow-panel backdrop-blur sm:block">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#ff8a93]">Plotted now</p>
          <div className="mt-3 space-y-2">
            {points.slice(0, 6).map((point) => (
              <div key={point.id} className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-[#ff5a66]">{point.location_name ?? "Unknown location"}</p>
                  <p className="text-xs text-[#ff8a93]">{eventTypeLabel(point.event_type)}</p>
                </div>
                <p className="text-xs font-medium text-[#ff8a93]">{formatRelativeTime(point.event_time)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
