"use client";

import L from "leaflet";
import { Circle, CircleMarker, MapContainer, Marker, Pane, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { Fragment, useEffect, useMemo, useState } from "react";

import { attackSideLabel, displayEventLocation, displayEventTypeLabel, formatDateTime } from "@/lib/format";
import type { AttackSide, MapPoint, RegionalEvent } from "@/types";

interface DashboardMapProps {
  points: MapPoint[];
  regionalEvents?: RegionalEvent[];
  lang?: "ar" | "en";
  mode?: "redalerts" | "firemonitor";
  historicalMode?: boolean;
  hasActiveFighterAlert?: boolean;
  hasActiveHelicopterAlert?: boolean;
  hasCoastFighterThreat?: boolean;
  hasBeirutFighterThreat?: boolean;
  hasBeirutBoundFighterThreat?: boolean;
  hasSouthFighterThreat?: boolean;
}

const markerStyles = {
  drone_movement: { radius: 9, fill: "#2d7cff", ring: "#75b5ff" },
  fighter_jet_movement: { radius: 8, fill: "#ff4d5f", ring: "#ff99a2" },
  helicopter_movement: { radius: 8, fill: "#ff8f3d", ring: "#ffc491" },
  ground_incursion: { radius: 8, fill: "#29a46b", ring: "#7fd2a7" },
} as const;

const FIREMONITOR_BOUNDS: [[number, number], [number, number]] = [
  [31.0, 34.15],
  [34.95, 36.9],
];
const FIREMONITOR_CENTER: [number, number] = [33.25, 35.35];
const FIREMONITOR_DEFAULT_ZOOM = 8;
const REDALERTS_BOUNDS: [[number, number], [number, number]] = [
  [33.05, 35.08],
  [34.72, 36.62],
];
const REDALERTS_CENTER: [number, number] = [33.88, 35.72];
const REDALERTS_DEFAULT_ZOOM = 9;
const MAP_MAX_ZOOM = 18;
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
const ATTACK_VISUAL_WINDOW_MS = 15 * 60 * 1000;
const SOUTH_BORDER_LATITUDE = 33.12;
const LEBANON_BOUNDS = REDALERTS_BOUNDS;
const DRONE_CLUSTER_DISTANCE_METERS = 5200;
const DRONE_CLUSTER_MIN_AREA_RADIUS_METERS = 2600;
const DRONE_CLUSTER_AREA_PADDING_METERS = 1200;
const DRONE_CLUSTER_ORBIT_PADDING_METERS = 900;

type AttackMarkerTone = "enemy" | "resistance";

type AttackWeaponKind = "airstrike" | "rocket" | "artillery" | "drone" | "ground" | "clash" | "blast";

interface DroneCluster {
  id: string;
  rawMessageId: string;
  center: [number, number];
  villageNames: string[];
  pointIds: string[];
  sourceText: string | null;
  areaRadiusMeters: number;
  orbitRadiusMeters: number;
}

interface DroneClusterResult {
  clusters: DroneCluster[];
  groupedPointIds: Set<string>;
}

const SOUTH_GROUND_BORDER_PATH: [number, number][] = [
  [33.089, 35.319],
  [33.103, 35.348],
  [33.118, 35.381],
  [33.132, 35.417],
  [33.149, 35.455],
  [33.168, 35.498],
  [33.184, 35.535],
  [33.202, 35.571],
];

function inferAttackWeapon(point: MapPoint): AttackWeaponKind {
  const text = `${point.source_text} ${point.location_name ?? ""}`.toLowerCase();

  if (text.includes("اشتباك") || text.includes("اشتباكات") || text.includes("clash")) {
    return "clash";
  }
  if (
    text.includes("غارة") ||
    text.includes("حربي") ||
    text.includes("مقاتلات") ||
    text.includes("طيران")
  ) {
    return "airstrike";
  }
  if (
    text.includes("صاروخ") ||
    text.includes("صواريخ") ||
    text.includes("مضاد للدروع") ||
    text.includes("كاتيوشا") ||
    text.includes("راجمة") ||
    text.includes("rocket") ||
    text.includes("missile")
  ) {
    return "rocket";
  }
  if (
    text.includes("مدفعي") ||
    text.includes("قذائف") ||
    text.includes("هاون") ||
    text.includes("shell") ||
    text.includes("artillery")
  ) {
    return "artillery";
  }
  if (
    text.includes("مسيرة") ||
    text.includes("مسيّرة") ||
    text.includes("مسيرات") ||
    text.includes("مسيّرات") ||
    text.includes("درون") ||
    text.includes("drone")
  ) {
    return "drone";
  }
  if (
    text.includes("توغل") ||
    text.includes("دبابة") ||
    text.includes("ميركافا") ||
    text.includes("آلية") ||
    text.includes("ground")
  ) {
    return "ground";
  }
  return "blast";
}

function attackWeaponGlyph(kind: AttackWeaponKind): string {
  if (kind === "airstrike") {
    return "✈";
  }
  if (kind === "rocket") {
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
  if (kind === "artillery") {
    return "☄";
  }
  if (kind === "drone") {
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
  if (kind === "clash") {
    return "⚔";
  }
  return "✹";
}

function attackWeaponLabel(kind: AttackWeaponKind, lang: "ar" | "en"): string {
  const labels =
    lang === "ar"
      ? {
          airstrike: "غارة",
          rocket: "صاروخ",
          artillery: "قصف مدفعي",
          drone: "مسيّرة",
          ground: "هجوم بري",
          clash: "اشتباكات",
          blast: "هجوم",
        }
      : {
          airstrike: "Airstrike",
          rocket: "Rocket",
          artillery: "Artillery",
          drone: "Drone",
          ground: "Ground attack",
          clash: "Clashes",
          blast: "Attack",
        };
  return labels[kind];
}

function isLikelyIsraelTarget(point: MapPoint): boolean {
  const mappedText = `${point.location_name ?? ""} ${point.region_name ?? ""}`.toLowerCase();
  const keywords = [
    "كريات شمونة",
    "كريات_شمونة",
    "المطلة",
    "مرجليوت",
    "مرغليوت",
    "شلومي",
    "صفد",
    "نهاريا",
    "طبريا",
    "بحيرة طبريا",
    "حيفا",
    "تل ابيب",
    "تل أبيب",
    "ميرون",
    "ميرون",
    "عميعاد",
    "قاعدة عميعاد",
    "افيفيم",
    "أفيفيم",
    "ادميت",
    "أدميت",
    "روش بينا",
    "الجليل",
    "كرميئيل",
    "ديشون",
    "مسكاف عام",
    "المنارة",
    "منارة",
  ];

  if (keywords.some((keyword) => mappedText.includes(keyword.toLowerCase()))) {
    return true;
  }

  if (point.location_name || point.region_name) {
    return false;
  }

  return sourceMentionsIsraelTarget(point);
}

function sourceMentionsIsraelTarget(point: MapPoint): boolean {
  const sourceText = (point.source_text ?? "").toLowerCase();
  return [
    "كريات شمونة",
    "كريات_شمونة",
    "المطلة",
    "مرجليوت",
    "مرغليوت",
    "شلومي",
    "صفد",
    "نهاريا",
    "طبريا",
    "بحيرة طبريا",
    "حيفا",
    "تل ابيب",
    "تل أبيب",
    "ميرون",
    "عميعاد",
    "قاعدة عميعاد",
    "افيفيم",
    "أفيفيم",
    "ادميت",
    "أدميت",
    "روش بينا",
    "الجليل",
    "كرميئيل",
    "ديشون",
    "مسكاف عام",
    "المنارة",
    "منارة",
  ].some((keyword) => sourceText.includes(keyword.toLowerCase()));
}

function isMappedIsraelTarget(point: MapPoint): boolean {
  const mappedText = `${point.location_name ?? ""} ${point.region_name ?? ""}`.toLowerCase();
  return [
    "كريات شمونة",
    "كريات_شمونة",
    "المطلة",
    "مرجليوت",
    "مرغليوت",
    "شلومي",
    "صفد",
    "نهاريا",
    "طبريا",
    "بحيرة طبريا",
    "حيفا",
    "تل ابيب",
    "تل أبيب",
    "ميرون",
    "عميعاد",
    "قاعدة عميعاد",
    "افيفيم",
    "أفيفيم",
    "ادميت",
    "أدميت",
    "روش بينا",
    "الجليل",
    "كرميئيل",
    "ديشون",
    "مسكاف عام",
    "المنارة",
    "منارة",
  ].some((keyword) => mappedText.includes(keyword.toLowerCase()));
}

function isStrictlyOutsideLebanonPoint(point: MapPoint): boolean {
  if (isMappedIsraelTarget(point)) {
    return true;
  }
  const [[minLat, minLng], [maxLat, maxLng]] = LEBANON_BOUNDS;
  return point.latitude < minLat || point.latitude > maxLat || point.longitude < minLng || point.longitude > maxLng;
}

function isLocalLebanonPoint(point: MapPoint): boolean {
  return !isStrictlyOutsideLebanonPoint(point);
}

function isMixedCrossBorderResistancePoint(point: MapPoint): boolean {
  if (!isLocalLebanonPoint(point)) {
    return false;
  }
  if (!sourceMentionsIsraelTarget(point)) {
    return false;
  }
  return point.attack_side === "resistance_attack" || isResistanceOperation(point);
}

function isOutsideLebanonLocation(point: MapPoint): boolean {
  if (isLikelyIsraelTarget(point)) {
    return true;
  }
  const [[minLat, minLng], [maxLat, maxLng]] = LEBANON_BOUNDS;
  return point.latitude < minLat || point.latitude > maxLat || point.longitude < minLng || point.longitude > maxLng;
}

function isFlightOnlyThreat(point: MapPoint): boolean {
  const text = point.source_text.toLowerCase();
  return (
    text.includes("تحليق") ||
    text.includes("حربي بالاجواء") ||
    text.includes("حربي بالأجواء") ||
    text.includes("فوق بيروت") ||
    text.includes("باتجاه بيروت")
  );
}

function isActualIncursion(point: MapPoint): boolean {
  const text = point.source_text.toLowerCase();
  return text.includes("توغل") || text.includes("تسلل") || text.includes("متوغلة") || text.includes("متوغل");
}

function isResistanceOperation(point: MapPoint): boolean {
  const text = point.source_text.toLowerCase();
  return (
    text.includes("عملية مقاومة") ||
    text.includes("عمليات المقاومة") ||
    text.includes("إطلاق صاروخ دفاع جوي") ||
    text.includes("اطلاق صاروخ دفاع جوي") ||
    text.includes("إطلاق صاروخ") ||
    text.includes("اطلاق صاروخ")
  );
}

function isDirectAttackText(point: MapPoint): boolean {
  const text = point.source_text.toLowerCase();
  if (isFlightOnlyThreat(point)) {
    return false;
  }
  if (isResistanceOperation(point)) {
    return true;
  }
  return (
    text.includes("غارة") ||
    text.includes("قصف") ||
    text.includes("استهداف") ||
    text.includes("ضربة") ||
    text.includes("هجوم بصاروخ") ||
    text.includes("هجوم بطائرات مسيرة") ||
    text.includes("هجوم بطائرات مسيّرة") ||
    text.includes("صاروخ مضاد للدروع")
  );
}

function resolveAttackTone(point: MapPoint): AttackMarkerTone | null {
  if (point.attack_side === "enemy_attack") {
    return "enemy";
  }
  if (isMixedCrossBorderResistancePoint(point)) {
    return null;
  }
  if (point.attack_side === "resistance_attack") {
    return "resistance";
  }
  if (isLikelyIsraelTarget(point)) {
    return "resistance";
  }
  if (isResistanceOperation(point)) {
    return "resistance";
  }
  if (isDirectAttackText(point)) {
    return "enemy";
  }
  return null;
}

function buildAttackMarkerIcon(tone: AttackMarkerTone, weaponKind: AttackWeaponKind, scale: number): L.DivIcon {
  const sideClass = tone === "enemy" ? "attack-marker--enemy" : "attack-marker--resistance";
  const glyph = attackWeaponGlyph(weaponKind);
  const size = Math.round(32 * Math.max(0.9, scale));
  const anchor = Math.round(size / 2);
  return L.divIcon({
    className: "attack-marker-wrapper",
    html: `
      <div class="attack-marker ${sideClass}" style="--attack-marker-size:${size}px;">
        <span class="attack-marker__glyph">${glyph}</span>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [anchor, anchor],
  });
}

function buildProjectileIcon(tone: AttackMarkerTone, weaponKind: AttackWeaponKind, scale: number): L.DivIcon {
  const sideClass = tone === "enemy" ? "projectile-marker--enemy" : "projectile-marker--resistance";
  const glyph = attackWeaponGlyph(weaponKind);
  const size = Math.round(24 * Math.max(0.9, scale));
  const anchor = Math.round(size / 2);
  return L.divIcon({
    className: "projectile-marker-wrapper",
    html: `<div class="projectile-marker ${sideClass}" style="--projectile-marker-size:${size}px;"><span class="projectile-marker__glyph">${glyph}</span></div>`,
    iconSize: [size, size],
    iconAnchor: [anchor, anchor],
  });
}

function buildIncursionIcon(scale: number, tone: "enemy" | "default" = "default"): L.DivIcon {
  const glyph = attackWeaponGlyph("ground");
  const size = Math.round(28 * Math.max(0.9, scale));
  const anchor = Math.round(size / 2);
  const toneClass = tone === "enemy" ? "incursion-marker--enemy" : "incursion-marker--default";
  return L.divIcon({
    className: "incursion-marker-wrapper",
    html: `<div class="incursion-marker ${toneClass}" style="--incursion-marker-size:${size}px;"><span class="incursion-marker__glyph">${glyph}</span></div>`,
    iconSize: [size, size],
    iconAnchor: [anchor, anchor],
  });
}

function squaredDistance(a: [number, number], b: [number, number]): number {
  const lat = a[0] - b[0];
  const lng = a[1] - b[1];
  return lat * lat + lng * lng;
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function pointSeed(point: MapPoint): number {
  const text = `${point.id}:${point.event_type}:${point.location_name ?? ""}`;
  return hashString(text);
}

function haversineMeters(a: [number, number], b: [number, number]): number {
  const earthRadiusMeters = 6_371_000;
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const lat1 = toRadians(a[0]);
  const lon1 = toRadians(a[1]);
  const lat2 = toRadians(b[0]);
  const lon2 = toRadians(b[1]);
  const dLat = lat2 - lat1;
  const dLon = lon2 - lon1;

  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const h = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon;
  return 2 * earthRadiusMeters * Math.asin(Math.min(1, Math.sqrt(h)));
}

function offsetPointByMeters(center: [number, number], distanceMeters: number, angleRadians: number): [number, number] {
  const earthRadiusMeters = 6_371_000;
  const lat1 = (center[0] * Math.PI) / 180;
  const lon1 = (center[1] * Math.PI) / 180;
  const angularDistance = distanceMeters / earthRadiusMeters;

  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angularDistance)
      + Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(angleRadians),
  );
  const lon2 =
    lon1
    + Math.atan2(
      Math.sin(angleRadians) * Math.sin(angularDistance) * Math.cos(lat1),
      Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2),
    );

  return [(lat2 * 180) / Math.PI, (lon2 * 180) / Math.PI];
}

function projectPointOnSegment(
  point: [number, number],
  start: [number, number],
  end: [number, number],
): [number, number] {
  const ax = start[0];
  const ay = start[1];
  const bx = end[0];
  const by = end[1];
  const px = point[0];
  const py = point[1];

  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;
  if (lengthSquared === 0) {
    return start;
  }

  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSquared));
  return [ax + t * dx, ay + t * dy];
}

function buildSouthBorderOrigin(point: MapPoint): [number, number] {
  const target: [number, number] = [point.latitude, point.longitude];
  let closest = SOUTH_GROUND_BORDER_PATH[0];
  let bestDistance = squaredDistance(closest, target);

  for (let index = 0; index < SOUTH_GROUND_BORDER_PATH.length - 1; index += 1) {
    const candidate = projectPointOnSegment(
      target,
      SOUTH_GROUND_BORDER_PATH[index],
      SOUTH_GROUND_BORDER_PATH[index + 1],
    );
    const distance = squaredDistance(candidate, target);
    if (distance < bestDistance) {
      closest = candidate;
      bestDistance = distance;
    }
  }

  for (const candidate of SOUTH_GROUND_BORDER_PATH) {
    const distance = squaredDistance(candidate, target);
    if (distance < bestDistance) {
      closest = candidate;
      bestDistance = distance;
    }
  }

  const isNearBorder = bestDistance < 0.0105;
  if (isNearBorder) {
    const seed = pointSeed(point);
    const segmentIndex = seed % (SOUTH_GROUND_BORDER_PATH.length - 1);
    const start = SOUTH_GROUND_BORDER_PATH[segmentIndex];
    const end = SOUTH_GROUND_BORDER_PATH[segmentIndex + 1];
    const progress = 0.2 + ((seed % 55) / 100);
    return projectPointOnSegment(
      [
        start[0] + (end[0] - start[0]) * progress,
        start[1] + (end[1] - start[1]) * progress,
      ],
      start,
      end,
    );
  }

  return closest;
}

function buildProjectilePath(point: MapPoint): [number, number][] {
  const origin = buildSouthBorderOrigin(point);
  const target: [number, number] = [point.latitude, point.longitude];
  return [origin, target];
}

function coordinateGroupKey(point: MapPoint): string {
  const locationKey = point.location_name?.trim().toLowerCase();
  if (locationKey) {
    return `${locationKey}:${point.latitude.toFixed(4)}:${point.longitude.toFixed(4)}`;
  }
  return `${point.latitude.toFixed(4)}:${point.longitude.toFixed(4)}`;
}

function buildVillageSpread(points: MapPoint[]): Map<string, [number, number]> {
  const grouped = new Map<string, MapPoint[]>();

  for (const point of points) {
    const key = coordinateGroupKey(point);
    const existing = grouped.get(key);
    if (existing) {
      existing.push(point);
    } else {
      grouped.set(key, [point]);
    }
  }

  const spread = new Map<string, [number, number]>();

  for (const group of grouped.values()) {
    if (group.length === 1) {
      const [point] = group;
      spread.set(point.id, [point.latitude, point.longitude]);
      continue;
    }

    const ordered = [...group].sort((left, right) => pointSeed(left) - pointSeed(right));
    const total = ordered.length;

    ordered.forEach((point, index) => {
      const angle = (Math.PI * 2 * index) / total + (pointSeed(point) % 360) * (Math.PI / 1800);
      const ring = Math.floor(index / 5);
      const latRadius = 0.0022 + ring * 0.0011;
      const lngRadius = 0.0028 + ring * 0.00135;
      const latitude = point.latitude + Math.sin(angle) * latRadius;
      const longitude = point.longitude + Math.cos(angle) * lngRadius;
      spread.set(point.id, [latitude, longitude]);
    });
  }

  return spread;
}

function buildDroneClusters(points: MapPoint[], distanceThresholdMeters: number): DroneClusterResult {
  const groupedPointIds = new Set<string>();
  const clusters: DroneCluster[] = [];
  const byMessage = new Map<string, MapPoint[]>();

  for (const point of points) {
    const messageId = (point.raw_message_id ?? "").trim();
    if (!messageId) {
      continue;
    }
    const bucket = byMessage.get(messageId);
    if (bucket) {
      bucket.push(point);
    } else {
      byMessage.set(messageId, [point]);
    }
  }

  for (const [rawMessageId, messagePoints] of byMessage.entries()) {
    if (messagePoints.length < 2) {
      continue;
    }

    const sortedPoints = [...messagePoints].sort((left, right) => pointSeed(left) - pointSeed(right));
    const localClusters: MapPoint[][] = [];

    for (const point of sortedPoints) {
      const pointCoordinate: [number, number] = [point.latitude, point.longitude];
      let assignedCluster: MapPoint[] | null = null;

      for (const candidateCluster of localClusters) {
        const centerLat =
          candidateCluster.reduce((sum, existingPoint) => sum + existingPoint.latitude, 0) / candidateCluster.length;
        const centerLng =
          candidateCluster.reduce((sum, existingPoint) => sum + existingPoint.longitude, 0) / candidateCluster.length;
        const clusterCenter: [number, number] = [centerLat, centerLng];
        const closeToClusterCenter = haversineMeters(pointCoordinate, clusterCenter) <= distanceThresholdMeters;
        if (closeToClusterCenter) {
          assignedCluster = candidateCluster;
          break;
        }
      }

      if (assignedCluster) {
        assignedCluster.push(point);
      } else {
        localClusters.push([point]);
      }
    }

    localClusters.forEach((clusterPoints, clusterIndex) => {
      if (clusterPoints.length < 2) {
        return;
      }

      const pointIds = clusterPoints.map((point) => point.id);
      pointIds.forEach((pointId) => groupedPointIds.add(pointId));

      const villageNames = Array.from(
        new Set(
          clusterPoints
            .map((point) => point.location_name?.trim())
            .filter((name): name is string => Boolean(name)),
        ),
      );

      const centerLat = clusterPoints.reduce((sum, point) => sum + point.latitude, 0) / clusterPoints.length;
      const centerLng = clusterPoints.reduce((sum, point) => sum + point.longitude, 0) / clusterPoints.length;
      const center: [number, number] = [centerLat, centerLng];
      const maxDistanceFromCenter = clusterPoints.reduce((currentMax, point) => {
        const distance = haversineMeters(center, [point.latitude, point.longitude]);
        return Math.max(currentMax, distance);
      }, 0);
      const areaRadiusMeters = Math.max(
        DRONE_CLUSTER_MIN_AREA_RADIUS_METERS,
        maxDistanceFromCenter + DRONE_CLUSTER_AREA_PADDING_METERS,
      );
      const orbitRadiusMeters = areaRadiusMeters + DRONE_CLUSTER_ORBIT_PADDING_METERS;
      const clusterHash = hashString(pointIds.join(":")).toString(16);

      clusters.push({
        id: `${rawMessageId}-${clusterIndex}-${clusterHash}`,
        rawMessageId,
        center,
        villageNames,
        pointIds,
        sourceText: clusterPoints[0]?.source_text ?? null,
        areaRadiusMeters,
        orbitRadiusMeters,
      });
    });
  }

  return { clusters, groupedPointIds };
}

function attackSideForDisplay(point: MapPoint): AttackSide | null {
  if (point.attack_side === "enemy_attack") {
    return "enemy_attack";
  }
  if (point.attack_side === "resistance_attack" && !isMixedCrossBorderResistancePoint(point)) {
    return "resistance_attack";
  }
  if (isMixedCrossBorderResistancePoint(point)) {
    return null;
  }
  if (isLikelyIsraelTarget(point)) {
    return "resistance_attack";
  }
  if (isResistanceOperation(point)) {
    return "resistance_attack";
  }
  if (point.attack_side == null && isDirectAttackText(point)) {
    return "enemy_attack";
  }
  return point.attack_side;
}

function isAttackPoint(point: MapPoint): boolean {
  if (point.attack_side === "enemy_attack" || point.attack_side === "resistance_attack") {
    return true;
  }
  return resolveAttackTone(point) !== null;
}

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

function zoomScale(zoom: number): number {
  return Math.max(0.72, Math.min(1.4, 0.72 + (zoom - 7) * 0.12));
}

function PointNewsLabel({
  mode,
  location,
  typeLabel,
  attackLabel,
  eventTime,
  sourceText,
}: {
  mode: "redalerts" | "firemonitor";
  location: string;
  typeLabel?: string | null;
  attackLabel?: string | null;
  eventTime?: string | null;
  sourceText?: string | null;
}) {
  if (mode === "firemonitor") {
    return (
      <div className="max-w-[18rem] text-center">
        <p className="whitespace-pre-line text-xs leading-5 text-slate-600">{sourceText || location}</p>
      </div>
    );
  }

  return (
    <div className="max-w-[18rem] space-y-1 text-center">
      <p className="font-semibold">{location}</p>
      {typeLabel ? <p className="text-xs">{typeLabel}</p> : null}
      {attackLabel ? <p className="text-xs">{attackLabel}</p> : null}
      {eventTime ? <p className="text-xs text-slate-500">{formatDateTime(eventTime)}</p> : null}
      {sourceText ? <p className="whitespace-pre-line text-xs leading-5 text-slate-600">{sourceText}</p> : null}
    </div>
  );
}

function MapViewportController({
  bounds,
}: {
  bounds: [[number, number], [number, number]];
}) {
  const map = useMap();

  useEffect(() => {
    map.fitBounds(bounds, { padding: [12, 12] });
    map.setMaxBounds(bounds);
  }, [bounds, map]);

  return null;
}

function MapZoomTracker({ onZoomChange }: { onZoomChange: (zoom: number) => void }) {
  const map = useMapEvents({
    zoomend: () => onZoomChange(map.getZoom()),
  });

  useEffect(() => {
    onZoomChange(map.getZoom());
  }, [map, onZoomChange]);

  return null;
}

function MapClickReset({ onMapClick }: { onMapClick: () => void }) {
  useMapEvents({
    click: () => onMapClick(),
  });

  return null;
}

export default function DashboardMap({
  points,
  regionalEvents = [],
  lang = "en",
  mode = "firemonitor",
  historicalMode = false,
  hasActiveFighterAlert = false,
  hasActiveHelicopterAlert = false,
  hasCoastFighterThreat = false,
  hasBeirutFighterThreat = false,
  hasBeirutBoundFighterThreat = false,
  hasSouthFighterThreat = false,
}: DashboardMapProps) {
  const viewportBounds = mode === "redalerts" ? REDALERTS_BOUNDS : FIREMONITOR_BOUNDS;
  const viewportCenter = mode === "redalerts" ? REDALERTS_CENTER : FIREMONITOR_CENTER;
  const defaultZoom = mode === "redalerts" ? REDALERTS_DEFAULT_ZOOM : FIREMONITOR_DEFAULT_ZOOM;
  const allowAttackVisuals = mode !== "redalerts";
  const showFighterThreatVisuals = mode !== "firemonitor";
  const t =
    lang === "ar"
      ? {
          fightersThreat: "تهديد المقاتلات",
          helicopterThreat: "تهديد المروحيات",
          coast: "الساحل",
          towardBeirut: "باتجاه بيروت",
          aboveBeirut: "فوق بيروت",
          aboveSouth: "جنوب لبنان",
          fighterMovement: "حركة مقاتلات",
          unknown: "موقع غير معروف",
          coastActive: "هناك حركة مقاتلات نشطة على الساحل الآن.",
          beirutBoundActive: "هناك حركة مقاتلات باتجاه بيروت الآن.",
          beirutActive: "هناك حركة مقاتلات فوق بيروت الآن.",
          southActive: "هناك تهديد مقاتلات قادم من الجنوب باتجاه بيروت الآن.",
          noneActive: "لا توجد مواقع دقيقة نشطة على الخريطة الآن.",
          plottedNow: "المعروض الآن",
        }
      : {
          fightersThreat: "Fighters Threat",
          helicopterThreat: "Helicopter Threat",
          coast: "Coast",
          towardBeirut: "Toward Beirut",
          aboveBeirut: "Beirut",
          aboveSouth: "South Lebanon",
          fighterMovement: "Fighter movement",
          unknown: "Unknown location",
          coastActive: "Coastal fighter movement is active right now.",
          beirutBoundActive: "Fighter movement toward Beirut is active right now.",
          beirutActive: "Fighter movement above Beirut is active right now.",
          southActive: "A fighter threat is moving from the south toward Beirut right now.",
          noneActive: "No exact locations are active on the map right now.",
          plottedNow: "Plotted now",
        };
  const hasRegionalSouthFighter = regionalEvents.some(
    (event) =>
      event.event_type === "fighter_jet_movement" &&
      (event.region_slug === "south-lebanon" || event.region_name === "South Lebanon" || event.region_name === "جنوب لبنان"),
  );
  const showSouthFighterThreat = hasSouthFighterThreat || hasRegionalSouthFighter;
  const droneClusterInput = useMemo(() => {
    if (mode !== "redalerts") {
      return [];
    }
    return points.filter(
      (point) =>
        point.event_type === "drone_movement"
        && !(allowAttackVisuals && isAttackPoint(point)),
    );
  }, [allowAttackVisuals, mode, points]);
  const { clusters: droneClusters, groupedPointIds: groupedDronePointIds } = useMemo(
    () => buildDroneClusters(droneClusterInput, DRONE_CLUSTER_DISTANCE_METERS),
    [droneClusterInput],
  );

  const [beirutBoundProgress, setBeirutBoundProgress] = useState(0);
  const [fighterSweepProgress, setFighterSweepProgress] = useState(0);
  const [projectileProgress, setProjectileProgress] = useState(0);
  const [droneOrbitProgress, setDroneOrbitProgress] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [mapZoom, setMapZoom] = useState(defaultZoom);
  const [selectedLabelId, setSelectedLabelId] = useState<string | null>(null);
  const toggleSelectedLabel = (labelId: string) => {
    setSelectedLabelId((current) => (current === labelId ? null : labelId));
  };
  const handleLayerClick = (labelId: string) => (event: L.LeafletMouseEvent) => {
    event.originalEvent?.stopPropagation();
    toggleSelectedLabel(labelId);
  };
  const markerScale = zoomScale(mapZoom);
  const spreadPositions = useMemo(() => buildVillageSpread(points), [points]);

  useEffect(() => {
    setMapZoom(defaultZoom);
  }, [defaultZoom]);

  useEffect(() => {
        const hasProjectilePath =
      allowAttackVisuals &&
      points.some((point) => {
        const tone = resolveAttackTone(point);
        const attackSide = attackSideForDisplay(point);
        return tone === "resistance" && attackSide === "resistance_attack" && isStrictlyOutsideLebanonPoint(point);
      });

    if (!hasBeirutBoundFighterThreat && !showSouthFighterThreat && !points.some((point) => point.event_type === "fighter_jet_movement") && !hasProjectilePath) {
      setBeirutBoundProgress(0);
      setFighterSweepProgress(0);
      setProjectileProgress(0);
      return;
    }

    if (historicalMode) {
      setBeirutBoundProgress(0);
      setFighterSweepProgress(0);
      if (!hasProjectilePath) {
        setProjectileProgress(0);
        return;
      }
    }

    const interval = window.setInterval(() => {
      if (!historicalMode) {
        setBeirutBoundProgress((current) => {
          const next = current + 0.04;
          return next >= 1 ? 0 : next;
        });
        setFighterSweepProgress((current) => {
          const next = current + 0.05;
          return next >= 1 ? 0 : next;
        });
      }
      setProjectileProgress((current) => {
        const next = current + (historicalMode ? 0.035 : 0.06);
        return next >= 1 ? 0 : next;
      });
    }, historicalMode ? 210 : 180);

    return () => window.clearInterval(interval);
  }, [allowAttackVisuals, hasBeirutBoundFighterThreat, historicalMode, points, showSouthFighterThreat]);

  useEffect(() => {
    if (droneClusters.length === 0) {
      setDroneOrbitProgress(0);
      return;
    }

    const interval = window.setInterval(() => {
      setDroneOrbitProgress((current) => {
        const next = current + (historicalMode ? 0.01 : 0.018);
        return next >= 1 ? 0 : next;
      });
    }, 130);

    return () => window.clearInterval(interval);
  }, [droneClusters.length, historicalMode]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const beirutBoundCenter = interpolatePath(BEIRUT_FIGHTER_PATH, beirutBoundProgress);
  const southFighterCenter = interpolatePath(SOUTH_FIGHTER_PATH, fighterSweepProgress);
  const attackPoints = allowAttackVisuals
    ? points.filter((point) => {
        if (!resolveAttackTone(point)) {
          return false;
        }
        if (historicalMode) {
          return true;
        }
        const elapsed = now - new Date(point.event_time).getTime();
        return elapsed >= 0 && elapsed <= ATTACK_VISUAL_WINDOW_MS;
      })
    : [];
  const spotlightedPointIds = new Set(attackPoints.map((point) => point.id));

  return (
    <div className="official-panel relative h-full min-h-[380px] overflow-hidden rounded-[1.8rem] sm:min-h-[460px] lg:min-h-[640px]">
      {showFighterThreatVisuals && (hasActiveFighterAlert || hasActiveHelicopterAlert) ? (
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
        center={viewportCenter}
        zoom={defaultZoom}
        className="h-full w-full"
        preferCanvas
        zoomAnimation
        fadeAnimation
        markerZoomAnimation
        zoomAnimationThreshold={8}
        zoomSnap={0.25}
        zoomDelta={0.5}
        wheelDebounceTime={40}
        wheelPxPerZoomLevel={70}
        attributionControl={false}
        maxBounds={viewportBounds}
        maxBoundsViscosity={1}
        maxZoom={MAP_MAX_ZOOM}
        minZoom={mode === "redalerts" ? 8 : 7}
        scrollWheelZoom
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          updateWhenIdle={false}
          updateWhenZooming
          keepBuffer={10}
        />
        <Pane name="drone-pane" style={{ zIndex: 610 }} />
        <Pane name="incursion-pane" style={{ zIndex: 615 }} />
        <Pane name="helicopter-pane" style={{ zIndex: 620 }} />
        <Pane name="fighter-pane" style={{ zIndex: 680 }} />
        <Pane name="attack-pane" style={{ zIndex: 760 }} />
        <Pane name="popup-pane" style={{ zIndex: 980 }} />
        <MapViewportController bounds={viewportBounds} />
        <MapZoomTracker onZoomChange={setMapZoom} />
        <MapClickReset onMapClick={() => setSelectedLabelId(null)} />

        {showFighterThreatVisuals && hasCoastFighterThreat ? (
          <>
            <Polyline
              pane="fighter-pane"
              positions={COAST_FIGHTER_PATH}
              pathOptions={{
                color: "#ff4d5f",
                weight: 5,
                opacity: 0.9,
                lineCap: "round",
                lineJoin: "round",
                dashArray: "12 10",
              }}
            />
            {COAST_FIGHTER_MARKERS.map((center, index) => (
              <CircleMarker
                key={`coast-fighter-${index}`}
                center={center}
                pane="fighter-pane"
                eventHandlers={{
                  click: handleLayerClick(`coast-fighter-${index}`),
                }}
                radius={7 * markerScale}
                pathOptions={{
                  color: "#ff99a2",
                  fillColor: "#ff4d5f",
                  fillOpacity: 0.95,
                  weight: 3,
                }}
              >
                {selectedLabelId === `coast-fighter-${index}` ? (
                <Tooltip direction="top" offset={[0, -18]} permanent>
                  <div className="space-y-1">
                    <p className="font-semibold">{t.coast}</p>
                    <p className="text-xs">{t.fighterMovement}</p>
                  </div>
                </Tooltip>
                ) : null}
              </CircleMarker>
            ))}
          </>
        ) : null}

        {showFighterThreatVisuals && hasBeirutBoundFighterThreat ? (
          <CircleMarker
            center={beirutBoundCenter}
            pane="fighter-pane"
            eventHandlers={{
              click: handleLayerClick("beirut-bound-fighter"),
            }}
            radius={9 * markerScale}
            pathOptions={{
              color: "#ff99a2",
              fillColor: "#ff4d5f",
              fillOpacity: 0.95,
              weight: 3,
            }}
          >
            {selectedLabelId === "beirut-bound-fighter" ? (
            <Tooltip direction="top" offset={[0, -18]} permanent>
              <div className="space-y-1">
                <p className="font-semibold">{t.towardBeirut}</p>
                <p className="text-xs">{t.fighterMovement}</p>
              </div>
            </Tooltip>
            ) : null}
          </CircleMarker>
        ) : null}

        {showFighterThreatVisuals && hasBeirutFighterThreat ? (
          <>
            <Polyline
              pane="fighter-pane"
              positions={BEIRUT_FIGHTER_PATH}
              pathOptions={{
                color: "#ff4d5f",
                weight: 5,
                opacity: 0.9,
                lineCap: "round",
                lineJoin: "round",
                dashArray: "10 8",
              }}
            />
            <CircleMarker
            center={BEIRUT_FIGHTER_PATH[1]}
            pane="fighter-pane"
            eventHandlers={{
              click: handleLayerClick("beirut-fighter"),
            }}
            radius={7 * markerScale}
            pathOptions={{
              color: "#ff99a2",
              fillColor: "#ff4d5f",
                fillOpacity: 0.95,
                weight: 3,
              }}
            >
              {selectedLabelId === "beirut-fighter" ? (
              <Tooltip direction="top" offset={[0, -18]} permanent>
                <div className="space-y-1">
                  <p className="font-semibold">{t.aboveBeirut}</p>
                  <p className="text-xs">{t.fighterMovement}</p>
                </div>
              </Tooltip>
              ) : null}
            </CircleMarker>
          </>
        ) : null}

        {showFighterThreatVisuals && showSouthFighterThreat ? (
          <CircleMarker
            center={southFighterCenter}
            pane="fighter-pane"
            eventHandlers={{
              click: handleLayerClick("south-fighter"),
            }}
            radius={9 * markerScale}
            pathOptions={{
              color: "#ff99a2",
              fillColor: "#ff4d5f",
              fillOpacity: 0.95,
              weight: 3,
            }}
          >
            {selectedLabelId === "south-fighter" ? (
            <Tooltip direction="top" offset={[0, -18]} permanent>
              <div className="space-y-1">
                <p className="font-semibold">{t.aboveSouth}</p>
                <p className="text-xs">{t.fighterMovement}</p>
              </div>
            </Tooltip>
            ) : null}
          </CircleMarker>
        ) : null}

        {attackPoints.map((point) => {
          const attackTone = resolveAttackTone(point);
          if (!attackTone) {
            return null;
          }
          const weaponKind = inferAttackWeapon(point);
          const attackSide = attackSideForDisplay(point);
          const attackPosition = spreadPositions.get(point.id) ?? [point.latitude, point.longitude];
          const shouldShowProjectile =
            attackSide === "resistance_attack" && isStrictlyOutsideLebanonPoint(point);
          const projectilePath = shouldShowProjectile
            ? [buildSouthBorderOrigin(point), attackPosition]
            : null;
          const projectileCenter = projectilePath
            ? interpolatePath(projectilePath, projectileProgress)
            : null;
          return (
            <Fragment key={`attack-group-${point.id}`}>
              {projectilePath ? (
                <Polyline
                  key={`attack-path-${point.id}`}
                  pane="attack-pane"
                  positions={projectilePath}
                  pathOptions={{
                    color: attackTone === "resistance" ? "#ffe44d" : "#4f8dff",
                    weight: 4,
                    opacity: 0.82,
                    lineCap: "round",
                    lineJoin: "round",
                    dashArray: weaponKind === "drone" ? "8 10" : "12 8",
                  }}
                />
              ) : null}
              {projectileCenter ? (
                <Marker
                  key={`attack-projectile-${point.id}`}
                  position={projectileCenter}
                  icon={buildProjectileIcon(attackTone, weaponKind, markerScale)}
                  pane="attack-pane"
                  eventHandlers={{
                    click: handleLayerClick(`attack-projectile-${point.id}`),
                  }}
                >
                  {selectedLabelId === `attack-projectile-${point.id}` ? (
                  <Tooltip direction="top" offset={[0, -24]} permanent>
                    <PointNewsLabel
                      mode={mode}
                      location={displayEventLocation(point, lang) || t.unknown}
                      typeLabel={attackWeaponLabel(weaponKind, lang)}
                      attackLabel={attackSide ? attackSideLabel(attackSide, lang) : null}
                      eventTime={point.event_time}
                      sourceText={point.source_text}
                    />
                  </Tooltip>
                  ) : null}
                </Marker>
              ) : null}
              <Marker
                key={`attack-${point.id}`}
                position={attackPosition}
                icon={buildAttackMarkerIcon(attackTone, weaponKind, markerScale)}
                pane="attack-pane"
                eventHandlers={{
                  click: handleLayerClick(`attack-${point.id}`),
                }}
              >
                {selectedLabelId === `attack-${point.id}` ? (
                <Tooltip direction="top" offset={[0, -28]} permanent>
                  <PointNewsLabel
                    mode={mode}
                    location={displayEventLocation(point, lang) || t.unknown}
                    typeLabel={attackWeaponLabel(weaponKind, lang)}
                    attackLabel={attackSide ? attackSideLabel(attackSide, lang) : null}
                    eventTime={point.event_time}
                    sourceText={point.source_text}
                  />
                </Tooltip>
                ) : null}
              </Marker>
            </Fragment>
          );
        })}

        {droneClusters.map((cluster, clusterIndex) => {
          const labelId = `drone-cluster-${cluster.id}`;
          const phase = (hashString(cluster.id) + clusterIndex * 37) % 360;
          const orbitAngle = ((droneOrbitProgress + phase / 360) % 1) * Math.PI * 2;
          const orbitMarkerPosition = offsetPointByMeters(cluster.center, cluster.orbitRadiusMeters, orbitAngle);
          const clusterVillages =
            cluster.villageNames.length > 0
              ? cluster.villageNames.join(lang === "ar" ? "، " : ", ")
              : t.unknown;

          return (
            <Fragment key={labelId}>
              <Circle
                center={cluster.center}
                pane="drone-pane"
                radius={cluster.areaRadiusMeters}
                pathOptions={{
                  color: "#75b5ff",
                  fillColor: "#2d7cff",
                  fillOpacity: 0.16,
                  weight: 2,
                }}
                eventHandlers={{
                  click: handleLayerClick(labelId),
                }}
                bubblingMouseEvents={false}
              />
              <Circle
                center={cluster.center}
                pane="drone-pane"
                radius={cluster.orbitRadiusMeters}
                pathOptions={{
                  color: "#2d7cff",
                  fillOpacity: 0,
                  weight: 2,
                  opacity: 0.9,
                  dashArray: "8 10",
                }}
                eventHandlers={{
                  click: handleLayerClick(labelId),
                }}
                bubblingMouseEvents={false}
              />
              <CircleMarker
                center={orbitMarkerPosition}
                pane="drone-pane"
                radius={8 * markerScale}
                pathOptions={{
                  color: "#9bc7ff",
                  fillColor: "#2d7cff",
                  fillOpacity: 0.95,
                  weight: 3,
                }}
                eventHandlers={{
                  click: handleLayerClick(labelId),
                }}
                bubblingMouseEvents={false}
              >
                {selectedLabelId === labelId ? (
                <Tooltip direction="top" offset={[0, -18]} permanent>
                  <PointNewsLabel
                    mode={mode}
                    location={clusterVillages}
                    typeLabel={lang === "ar" ? "حركة مسيّرات" : "Drone movement"}
                  />
                </Tooltip>
                ) : null}
              </CircleMarker>
            </Fragment>
          );
        })}

        {points.map((point) => {
          if (groupedDronePointIds.has(point.id)) {
            return null;
          }
          if (allowAttackVisuals && isAttackPoint(point)) {
            return null;
          }
          if (mode === "firemonitor" && !(point.event_type === "ground_incursion" && isActualIncursion(point))) {
            return null;
          }
          const basePosition = spreadPositions.get(point.id) ?? [point.latitude, point.longitude];
          const renderIncursionIcon = mode === "firemonitor" && point.event_type === "ground_incursion" && isActualIncursion(point);
          const incursionTone: "enemy" | "default" = point.attack_side === "enemy_attack" ? "enemy" : "default";
          const pointCenter: [number, number] =
            point.event_type === "fighter_jet_movement"
              ? interpolatePath(
                  [
                    [basePosition[0] - 0.01, basePosition[1] - 0.01],
                    [basePosition[0], basePosition[1] + 0.012],
                    [basePosition[0] + 0.01, basePosition[1] - 0.004],
                  ],
                  fighterSweepProgress,
                )
              : basePosition;

          if (renderIncursionIcon) {
            return (
              <Marker
                key={point.id}
                position={pointCenter}
                pane={spotlightedPointIds.has(point.id) ? "drone-pane" : "incursion-pane"}
                icon={buildIncursionIcon(markerScale, incursionTone)}
                eventHandlers={{
                  click: handleLayerClick(`point-${point.id}`),
                }}
              >
                {selectedLabelId === `point-${point.id}` ? (
                <Tooltip direction="top" offset={[0, -14]} opacity={0.98} permanent>
                  <PointNewsLabel
                    mode={mode}
                    location={displayEventLocation(point, lang) || t.unknown}
                    typeLabel={displayEventTypeLabel(point, lang)}
                    attackLabel={point.attack_side ? attackSideLabel(point.attack_side, lang) : null}
                    eventTime={point.event_time}
                    sourceText={point.source_text}
                  />
                </Tooltip>
                ) : null}
              </Marker>
            );
          }

          return (
            <CircleMarker
              key={point.id}
              center={pointCenter}
              eventHandlers={{
                click: handleLayerClick(`point-${point.id}`),
              }}
              pane={
                spotlightedPointIds.has(point.id)
                  ? "drone-pane"
                : point.event_type === "ground_incursion" && isActualIncursion(point)
                    ? "incursion-pane"
                    : "drone-pane"
              }
              radius={markerStyles[point.event_type].radius * markerScale}
              pathOptions={{
                color: spotlightedPointIds.has(point.id) ? "rgba(145, 161, 194, 0.45)" : markerStyles[point.event_type].ring,
                fillColor: spotlightedPointIds.has(point.id) ? "rgba(255,255,255,0.78)" : markerStyles[point.event_type].fill,
                fillOpacity: spotlightedPointIds.has(point.id) ? 0.45 : 0.92,
                weight: spotlightedPointIds.has(point.id) ? 2 : 3,
              }}
              bubblingMouseEvents={false}
            >
              {selectedLabelId === `point-${point.id}` ? (
              <Tooltip direction="top" offset={[0, -18]} permanent>
                <PointNewsLabel
                  mode={mode}
                  location={displayEventLocation(point, lang) || t.unknown}
                  typeLabel={
                    mode === "redalerts" && point.event_type === "drone_movement"
                      ? (lang === "ar" ? "حركة مسيّرات" : "Drone movement")
                      : displayEventTypeLabel(point, lang)
                  }
                  attackLabel={point.attack_side ? attackSideLabel(point.attack_side, lang) : null}
                  eventTime={point.event_time}
                  sourceText={
                    mode === "redalerts" && point.event_type === "drone_movement"
                      ? null
                      : point.source_text
                  }
                />
              </Tooltip>
              ) : null}
            </CircleMarker>
          );
        })}
      </MapContainer>

      {points.length === 0 ? (
        <div className="pointer-events-none absolute inset-x-3 bottom-3 rounded-2xl border border-[#d4deed] bg-white/98 p-3 text-sm text-[#607393] shadow-[0_10px_28px_rgba(16,40,84,0.08)] sm:inset-x-4 sm:bottom-4 sm:p-4">
          {hasCoastFighterThreat
            ? t.coastActive
            : hasBeirutBoundFighterThreat
              ? t.beirutBoundActive
              : hasBeirutFighterThreat
                ? t.beirutActive
                : showSouthFighterThreat
                  ? t.southActive
                : t.noneActive}
        </div>
      ) : null}
    </div>
  );
}
