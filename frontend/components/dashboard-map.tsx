"use client";

import { CircleMarker, MapContainer, Pane, Polyline, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useEffect, useMemo, useState } from "react";

import { eventTypeLabel, formatDateTime, formatRelativeTime } from "@/lib/format";
import type { MapPoint } from "@/types";

interface DashboardMapProps {
  points: MapPoint[];
  lang?: "ar" | "en";
  hasActiveFighterAlert?: boolean;
  hasActiveHelicopterAlert?: boolean;
  hasCoastFighterThreat?: boolean;
  hasBeirutFighterThreat?: boolean;
  hasBeirutBoundFighterThreat?: boolean;
  hasSouthFighterThreat?: boolean;
}

interface DroneCluster {
  id: string;
  points: MapPoint[];
  center: [number, number];
}

const markerStyles = {
  drone_movement: { radius: 9, fill: "#2d7cff", ring: "#75b5ff" },
  fighter_jet_movement: { radius: 8, fill: "#ff4d5f", ring: "#ff99a2" },
  helicopter_movement: { radius: 8, fill: "#ff8f3d", ring: "#ffc491" },
  ground_incursion: { radius: 8, fill: "#29a46b", ring: "#7fd2a7" },
} as const;

const LEBANON_BOUNDS: [[number, number], [number, number]] = [
  [33.0, 35.05],
  [34.72, 36.7],
];
const MAP_CENTER: [number, number] = [33.88, 35.86];
const MAP_DEFAULT_ZOOM = 9;
const MAP_MAX_ZOOM = 18;
const DRONE_CLUSTER_THRESHOLD = 0.03;

const COAST_FIGHTER_PATH: [number, number][] = [
  [33.1205, 35.1032],
  [33.272, 35.2038],
  [33.45, 35.3],
  [33.62, 35.37],
  [33.76, 35.48],
  [33.89, 35.54],
];
const COAST_FIGHTER_MARKERS: [number, number][] = [
  [33.272, 35.2038],
  [33.62, 35.37],
  [33.89, 35.54],
];
const BEIRUT_FIGHTER_PATH: [number, number][] = [
  [33.9505, 35.4311],
  [33.9175, 35.4625],
  [33.895, 35.494],
];
const SOUTH_FIGHTER_PATH: [number, number][] = [
  [33.24, 35.25],
  [33.32, 35.42],
  [33.4, 35.56],
];

function interpolatePath(path: [number, number][], progress: number): [number, number] {
  if (path.length === 0) {
    return [33.9175, 35.4625];
  }
  if (path.length === 1) {
    return path[0];
  }

  const clamped = Math.max(0, Math.min(0.9999, progress));
  const scaled = clamped * (path.length - 1);
  const index = Math.floor(scaled);
  const segmentProgress = scaled - index;
  const start = path[index];
  const end = path[Math.min(index + 1, path.length - 1)];

  return [
    start[0] + (end[0] - start[0]) * segmentProgress,
    start[1] + (end[1] - start[1]) * segmentProgress,
  ];
}

function circleOrbit(center: [number, number], progress: number, radius: number): [number, number] {
  const angle = progress * Math.PI * 2;
  return [center[0] + Math.sin(angle) * radius, center[1] + Math.cos(angle) * radius];
}

function buildOrbitPath(center: [number, number], radius: number, steps = 28): [number, number][] {
  return Array.from({ length: steps + 1 }, (_, index) => {
    const angle = (index / steps) * Math.PI * 2;
    return [center[0] + Math.sin(angle) * radius, center[1] + Math.cos(angle) * radius];
  });
}

function distance(a: [number, number], b: [number, number]): number {
  const lat = a[0] - b[0];
  const lng = a[1] - b[1];
  return Math.sqrt(lat * lat + lng * lng);
}

function clusterDronePoints(points: MapPoint[]): { clusters: DroneCluster[]; singles: MapPoint[] } {
  const drones = points.filter((point) => point.event_type === "drone_movement");
  const nonDrones = points.filter((point) => point.event_type !== "drone_movement");
  const dronesByMessage = new Map<string, MapPoint[]>();

  for (const point of drones) {
    const bucket = dronesByMessage.get(point.raw_message_id) ?? [];
    bucket.push(point);
    dronesByMessage.set(point.raw_message_id, bucket);
  }

  const clusters: DroneCluster[] = [];
  const singles: MapPoint[] = [...nonDrones];
  let clusterIndex = 0;

  dronesByMessage.forEach((messagePoints, rawMessageId) => {
    const provisional: { points: MapPoint[]; center: [number, number] }[] = [];

    for (const point of messagePoints) {
      const pointCenter: [number, number] = [point.latitude, point.longitude];
      const existing = provisional.find((cluster) => distance(cluster.center, pointCenter) <= DRONE_CLUSTER_THRESHOLD);
      if (!existing) {
        provisional.push({ points: [point], center: pointCenter });
        continue;
      }

      existing.points.push(point);
      const lat = existing.points.reduce((sum, item) => sum + item.latitude, 0) / existing.points.length;
      const lng = existing.points.reduce((sum, item) => sum + item.longitude, 0) / existing.points.length;
      existing.center = [lat, lng];
    }

    provisional.forEach((cluster) => {
      if (cluster.points.length < 2) {
        singles.push(cluster.points[0]);
        return;
      }
      clusters.push({
        id: `drone-cluster-${rawMessageId}-${clusterIndex++}`,
        points: cluster.points,
        center: cluster.center,
      });
    });
  });

  return { clusters, singles };
}

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
  lang = "en",
  hasActiveFighterAlert = false,
  hasActiveHelicopterAlert = false,
  hasCoastFighterThreat = false,
  hasBeirutFighterThreat = false,
  hasBeirutBoundFighterThreat = false,
  hasSouthFighterThreat = false,
}: DashboardMapProps) {
  const t =
    lang === "ar"
      ? {
          fightersThreat: "تهديد المقاتلات",
          helicopterThreat: "تهديد المروحيات",
          coast: "الساحل",
          towardBeirut: "باتجاه بيروت",
          aboveBeirut: "فوق بيروت",
          aboveSouth: "فوق الجنوب",
          fighterMovement: "حركة مقاتلات",
          droneSwarm: "تحليق مسيّرات فوق عدة بلدات",
          villages: "البلدات",
          unknown: "موقع غير معروف",
          coastActive: "هناك حركة مقاتلات نشطة على الساحل الآن.",
          beirutBoundActive: "هناك حركة مقاتلات باتجاه بيروت الآن.",
          beirutActive: "هناك حركة مقاتلات فوق بيروت الآن.",
          noneActive: "لا توجد مواقع دقيقة نشطة على الخريطة الآن.",
          plottedNow: "المعروض الآن",
        }
      : {
          fightersThreat: "Fighters Threat",
          helicopterThreat: "Helicopter Threat",
          coast: "Coast",
          towardBeirut: "Toward Beirut",
          aboveBeirut: "Above Beirut",
          aboveSouth: "Above South",
          fighterMovement: "Fighter movement",
          droneSwarm: "Drone movement above nearby villages",
          villages: "Villages",
          unknown: "Unknown location",
          coastActive: "Coastal fighter movement is active right now.",
          beirutBoundActive: "Fighter movement toward Beirut is active right now.",
          beirutActive: "Fighter movement above Beirut is active right now.",
          noneActive: "No exact locations are active on the map right now.",
          plottedNow: "Plotted now",
        };

  const [beirutBoundProgress, setBeirutBoundProgress] = useState(0);
  const [fighterSweepProgress, setFighterSweepProgress] = useState(0);
  const [droneOrbitProgress, setDroneOrbitProgress] = useState(0);

  const { clusters: droneClusters, singles: renderedPoints } = useMemo(() => clusterDronePoints(points), [points]);

  useEffect(() => {
    if (!hasBeirutBoundFighterThreat && !hasSouthFighterThreat && !points.some((point) => point.event_type === "fighter_jet_movement")) {
      setBeirutBoundProgress(0);
      setFighterSweepProgress(0);
      return;
    }

    const interval = window.setInterval(() => {
      setBeirutBoundProgress((current) => {
        const next = current + 0.04;
        return next >= 1 ? 0 : next;
      });
      setFighterSweepProgress((current) => {
        const next = current + 0.05;
        return next >= 1 ? 0 : next;
      });
    }, 180);

    return () => window.clearInterval(interval);
  }, [hasBeirutBoundFighterThreat, hasSouthFighterThreat, points]);

  useEffect(() => {
    if (droneClusters.length === 0) {
      setDroneOrbitProgress(0);
      return;
    }

    const interval = window.setInterval(() => {
      setDroneOrbitProgress((current) => {
        const next = current + 0.025;
        return next >= 1 ? 0 : next;
      });
    }, 140);

    return () => window.clearInterval(interval);
  }, [droneClusters.length]);

  const beirutBoundCenter = interpolatePath(BEIRUT_FIGHTER_PATH, beirutBoundProgress);
  const southFighterCenter = interpolatePath(SOUTH_FIGHTER_PATH, fighterSweepProgress);

  return (
    <div className="official-panel relative h-full min-h-[380px] overflow-hidden rounded-[1.8rem] sm:min-h-[460px] lg:min-h-[640px]">
      {hasActiveFighterAlert || hasActiveHelicopterAlert ? (
        <div className="pointer-events-none absolute right-3 top-3 z-[1000] flex flex-col items-end gap-2 sm:right-4 sm:top-4">
          {hasActiveFighterAlert ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-[#d4deed] bg-white/98 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#173f91] shadow-[0_10px_24px_rgba(17,39,84,0.1)]">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#ff4d5f] opacity-60" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-[#ff4d5f]" />
              </span>
              {t.fightersThreat}
            </div>
          ) : null}
          {hasActiveHelicopterAlert ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-[#d4deed] bg-white/98 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#173f91] shadow-[0_10px_24px_rgba(17,39,84,0.1)]">
              <span className="relative flex h-3 w-3">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#ff8f3d] opacity-60" />
                <span className="relative inline-flex h-3 w-3 rounded-full bg-[#ff8f3d]" />
              </span>
              {t.helicopterThreat}
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
        <Pane name="drone-pane" style={{ zIndex: 610 }} />
        <Pane name="incursion-pane" style={{ zIndex: 615 }} />
        <Pane name="helicopter-pane" style={{ zIndex: 620 }} />
        <Pane name="fighter-pane" style={{ zIndex: 680 }} />
        <MapViewportController />

        {hasCoastFighterThreat ? (
          <>
            <Polyline
              pane="fighter-pane"
              positions={COAST_FIGHTER_PATH}
              pathOptions={{ color: "#ff4d5f", weight: 5, opacity: 0.9, lineCap: "round", lineJoin: "round", dashArray: "12 10" }}
            />
            {COAST_FIGHTER_MARKERS.map((center, index) => (
              <CircleMarker
                key={`coast-fighter-${index}`}
                center={center}
                pane="fighter-pane"
                radius={7}
                pathOptions={{ color: "#ff99a2", fillColor: "#ff4d5f", fillOpacity: 0.95, weight: 3 }}
              >
                <Tooltip direction="top" offset={[0, -18]}>
                  <div className="space-y-1">
                    <p className="font-semibold">{t.coast}</p>
                    <p className="text-xs">{t.fighterMovement}</p>
                  </div>
                </Tooltip>
              </CircleMarker>
            ))}
          </>
        ) : null}

        {hasBeirutBoundFighterThreat ? (
          <CircleMarker
            center={beirutBoundCenter}
            pane="fighter-pane"
            radius={9}
            pathOptions={{ color: "#ff99a2", fillColor: "#ff4d5f", fillOpacity: 0.95, weight: 3 }}
          >
            <Tooltip direction="top" offset={[0, -18]}>
              <div className="space-y-1">
                <p className="font-semibold">{t.towardBeirut}</p>
                <p className="text-xs">{t.fighterMovement}</p>
              </div>
            </Tooltip>
          </CircleMarker>
        ) : null}

        {hasBeirutFighterThreat ? (
          <>
            <Polyline
              pane="fighter-pane"
              positions={BEIRUT_FIGHTER_PATH}
              pathOptions={{ color: "#ff4d5f", weight: 5, opacity: 0.9, lineCap: "round", lineJoin: "round", dashArray: "10 8" }}
            />
            <CircleMarker
              center={BEIRUT_FIGHTER_PATH[1]}
              pane="fighter-pane"
              radius={7}
              pathOptions={{ color: "#ff99a2", fillColor: "#ff4d5f", fillOpacity: 0.95, weight: 3 }}
            >
              <Tooltip direction="top" offset={[0, -18]}>
                <div className="space-y-1">
                  <p className="font-semibold">{t.aboveBeirut}</p>
                  <p className="text-xs">{t.fighterMovement}</p>
                </div>
              </Tooltip>
            </CircleMarker>
          </>
        ) : null}

        {hasSouthFighterThreat ? (
          <CircleMarker
            center={southFighterCenter}
            pane="fighter-pane"
            radius={9}
            pathOptions={{ color: "#ff99a2", fillColor: "#ff4d5f", fillOpacity: 0.95, weight: 3 }}
          >
            <Tooltip direction="top" offset={[0, -18]}>
              <div className="space-y-1">
                <p className="font-semibold">{t.aboveSouth}</p>
                <p className="text-xs">{t.fighterMovement}</p>
              </div>
            </Tooltip>
          </CircleMarker>
        ) : null}

        {droneClusters.map((cluster) => {
          const radius = 0.005 + Math.min(cluster.points.length, 6) * 0.00055;
          const orbitCenter = circleOrbit(cluster.center, droneOrbitProgress, radius);
          const orbitPath = buildOrbitPath(cluster.center, radius);
          const villageNames = Array.from(new Set(cluster.points.map((point) => point.location_name).filter(Boolean))) as string[];

          return (
            <div key={cluster.id}>
              <Polyline
                pane="drone-pane"
                positions={orbitPath}
                pathOptions={{ color: "#75b5ff", weight: 2, opacity: 0.7, dashArray: "5 6" }}
              />
              <CircleMarker
                center={cluster.center}
                pane="drone-pane"
                radius={Math.min(36, 20 + cluster.points.length * 2)}
                pathOptions={{ color: "#75b5ff", fillColor: "#2d7cff", fillOpacity: 0.12, weight: 2 }}
              />
              <CircleMarker
                center={orbitCenter}
                pane="drone-pane"
                radius={10}
                pathOptions={{ color: "#75b5ff", fillColor: "#2d7cff", fillOpacity: 0.96, weight: 3 }}
              >
                <Tooltip direction="top" offset={[0, -18]}>
                  <div className="space-y-1">
                    <p className="font-semibold">{t.droneSwarm}</p>
                    <p className="text-xs">
                      {t.villages}: {villageNames.join("، ")}
                    </p>
                  </div>
                </Tooltip>
                <Popup>
                  <div className="space-y-1">
                    <p className="font-semibold">{t.droneSwarm}</p>
                    <p>{t.villages}: {villageNames.join("، ")}</p>
                    <p>{cluster.points.length} points</p>
                  </div>
                </Popup>
              </CircleMarker>
            </div>
          );
        })}

        {renderedPoints.map((point) => (
          <CircleMarker
            key={point.id}
            center={
              point.event_type === "fighter_jet_movement"
                ? interpolatePath(
                    [
                      [point.latitude - 0.01, point.longitude - 0.01],
                      [point.latitude, point.longitude + 0.012],
                      [point.latitude + 0.01, point.longitude - 0.004],
                    ],
                    fighterSweepProgress,
                  )
                : [point.latitude, point.longitude]
            }
            pane={
              point.event_type === "fighter_jet_movement"
                ? "fighter-pane"
                : point.event_type === "ground_incursion"
                  ? "incursion-pane"
                  : point.event_type === "helicopter_movement"
                    ? "helicopter-pane"
                    : "drone-pane"
            }
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
                <p className="font-semibold">{point.location_name ?? t.unknown}</p>
                <p className="text-xs">{eventTypeLabel(point.event_type)}</p>
              </div>
            </Tooltip>
            <Popup>
              <div className="space-y-1">
                <p className="font-semibold">{point.location_name ?? t.unknown}</p>
                <p>{eventTypeLabel(point.event_type)}</p>
                <p>{formatDateTime(point.event_time)}</p>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>

      {points.length === 0 ? (
        <div className="pointer-events-none absolute inset-x-3 bottom-3 rounded-2xl border border-[#d4deed] bg-white/98 p-3 text-sm text-[#607393] shadow-[0_10px_28px_rgba(16,40,84,0.08)] sm:inset-x-4 sm:bottom-4 sm:p-4">
          {hasCoastFighterThreat
            ? t.coastActive
            : hasBeirutBoundFighterThreat
              ? t.beirutBoundActive
              : hasBeirutFighterThreat
                ? t.beirutActive
                : t.noneActive}
        </div>
      ) : (
        <div className="pointer-events-none absolute right-4 top-24 hidden w-[17rem] rounded-2xl border border-[#d4deed] bg-white/98 p-4 text-sm text-[#607393] shadow-[0_12px_30px_rgba(16,40,84,0.08)] sm:block">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6f82a4]">{t.plottedNow}</p>
          <div className="mt-3 space-y-2">
            {points.slice(0, 6).map((point) => (
              <div key={point.id} className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-[#173f91]">{point.location_name ?? t.unknown}</p>
                  <p className="text-xs text-[#607393]">{eventTypeLabel(point.event_type)}</p>
                </div>
                <p className="text-xs font-medium text-[#607393]">{formatRelativeTime(point.event_time)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
