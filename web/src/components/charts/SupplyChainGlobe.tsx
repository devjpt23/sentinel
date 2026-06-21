"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useCallback, useMemo } from "react";
import { COUNTRY_COORDS, type Entity, type Relationship } from "@/types/supply-chain";

// ─── Color helpers (match existing utility patterns) ──────────────

function getPinColor(score?: number): string {
  if (score === undefined) return "#6b7f8e";
  if (score >= 70) return "#84cc16"; // emerald-500
  if (score >= 40) return "#eab308"; // yellow-500
  return "#ef4444"; // red-500
}

function getArcColor(type: Relationship["type"]): string {
  switch (type) {
    case "supplier":
      return "#84cc16";
    case "customer":
      return "#3b82f6";
    case "competitor":
      return "#ef4444";
    case "partner":
      return "#a855f7";
    default:
      return "#6b7f8e";
  }
}

function getArcDashLength(strength: Relationship["strength"]): number {
  switch (strength) {
    case "strong":
      return 1.0;
    case "medium":
      return 0.6;
    case "weak":
      return 0.3;
  }
}

// ─── Resolve location from geo data ──────────────────────────────

function resolveCoords(location: string | undefined): [number, number] | null {
  if (!location) return null;
  const upper = location.trim().toUpperCase();
  if (COUNTRY_COORDS[upper]) return COUNTRY_COORDS[upper];
  for (const [key, val] of Object.entries(COUNTRY_COORDS)) {
    if (upper.includes(key) || key.includes(upper)) return val;
  }
  return null;
}

// ─── Derived data for globe.gl ───────────────────────────────────

interface PinPoint {
  lat: number;
  lng: number;
  name: string;
  type: Relationship["type"];
  score?: number;
  color: string;
  radius: number;
}

interface ArcPoint {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  source: string;
  target: string;
  type: Relationship["type"];
  strength: Relationship["strength"];
  color: string;
  dashLength: number;
}

function buildPins(relationships: Relationship[]): PinPoint[] {
  const seen = new Map<string, PinPoint>();

  for (const rel of relationships) {
    if (!rel.geo) continue;

    const domicileCoords = resolveCoords(rel.geo.domicile ?? undefined);
    if (domicileCoords) {
      const key = `${rel.source}:${rel.geo.domicile}`;
      if (!seen.has(key)) {
        seen.set(key, {
          lat: domicileCoords[0],
          lng: domicileCoords[1],
          name: rel.source,
          type: rel.type,
          score: rel.investability_score,
          color: getPinColor(rel.investability_score),
          radius: 0.8,
        });
      }
    }

    (rel.geo.manufacturing ?? []).forEach((loc) => {
      const coords = resolveCoords(loc);
      if (coords) {
        const key = `${rel.target}:${loc}`;
        if (!seen.has(key)) {
          seen.set(key, {
            lat: coords[0],
            lng: coords[1],
            name: rel.target,
            type: rel.type,
            color: getPinColor(rel.investability_score),
            radius: 0.6,
          });
        }
      }
    });
  }

  return Array.from(seen.values());
}

function buildArcs(relationships: Relationship[]): ArcPoint[] {
  const arcs: ArcPoint[] = [];

  for (const rel of relationships) {
    if (!rel.geo) continue;
    const start = resolveCoords(rel.geo.domicile ?? undefined);
    if (!start) continue;

    (rel.geo.manufacturing ?? []).forEach((loc) => {
      const end = resolveCoords(loc);
      if (end) {
        arcs.push({
          startLat: start[0],
          startLng: start[1],
          endLat: end[0],
          endLng: end[1],
          source: rel.source,
          target: rel.target,
          type: rel.type,
          strength: rel.strength,
          color: getArcColor(rel.type),
          dashLength: getArcDashLength(rel.strength),
        });
      }
    });
  }

  return arcs;
}

// ─── Globe wrapper (dynamically imported) ────────────────────────

interface OrbitControls {
  autoRotate: boolean;
  autoRotateSpeed: number;
}

interface GlobeInstance {
  globeImageUrl(url: string): GlobeInstance;
  backgroundColor(color: string): GlobeInstance;
  atmosphereColor(color: string): GlobeInstance;
  atmosphereAltitude(alt: number): GlobeInstance;
  pointsData(data: PinPoint[]): GlobeInstance;
  pointAltitude(d: number | string): GlobeInstance;
  pointColor(d: string): GlobeInstance;
  pointRadius(d: number | string): GlobeInstance;
  pointLabel(fn: (d: PinPoint) => string): GlobeInstance;
  onPointClick(cb: (d: PinPoint) => void): GlobeInstance;
  arcsData(data: ArcPoint[]): GlobeInstance;
  arcColor(d: string): GlobeInstance;
  arcDashLength(d: number | string): GlobeInstance;
  arcDashGap(gap: number): GlobeInstance;
  arcDashAnimateTime(ms: number): GlobeInstance;
  arcStroke(stroke: number): GlobeInstance;
  arcLabel(fn: (d: ArcPoint) => string): GlobeInstance;
  pointOfView(pov: { lat: number; lng: number; altitude: number }, durationMs?: number): GlobeInstance;
  controls(): OrbitControls;
  polygonsData(data: unknown[]): GlobeInstance;
  polygonAltitude(d: number): GlobeInstance;
  polygonCapColor(d: string): GlobeInstance;
  polygonSideColor(d: string): GlobeInstance;
  polygonLabel(fn: (d: unknown) => string): GlobeInstance;
  onPolygonHover(cb: (d: unknown | null) => void): GlobeInstance;
  onPolygonClick(cb: (d: unknown) => void): GlobeInstance;
}

type GlobeFactory = (container: HTMLElement) => GlobeInstance;

interface GlobeRendererProps {
  pins: PinPoint[];
  arcs: ArcPoint[];
  onEntityClick: (entity: Entity) => void;
  globeFactory: GlobeFactory;
}

function GlobeRenderer({ pins, arcs, onEntityClick, globeFactory }: GlobeRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeInstance | null>(null);
  const initializedRef = useRef(false);

  // Initialize globe once
  useEffect(() => {
    if (!containerRef.current || initializedRef.current) return;

    const globe = globeFactory(containerRef.current);
    initializedRef.current = true;

    globe
      .globeImageUrl("//unpkg.com/three-globe/example/img/earth-dark.jpg")
      .backgroundColor("rgba(0,0,0,0)")
      .atmosphereColor("#84cc16")
      .atmosphereAltitude(0.25)
      .arcDashGap(0.005)
      .arcDashAnimateTime(2000)
      .arcStroke(0.5);

    // Auto-rotation via underlying OrbitControls (globe.gl v2.x removed .autoRotateSpeed())
    globe.controls().autoRotate = true;
    globe.controls().autoRotateSpeed = 0.4;

    globeRef.current = globe;

    return () => {
      initializedRef.current = false;
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };
  }, [globeFactory]);

  // Update pins when data changes
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;

    globe
      .pointsData(pins)
      .pointAltitude(0.06)
      .pointColor("color")
      .pointRadius("radius")
      .pointLabel(
        (d: PinPoint) =>
          `<div style="background:rgba(0,0,0,0.8);padding:6px 10px;border-radius:6px;border:1px solid #1e2d3a">
            <div style="color:#f0f4f0;font-weight:600;font-size:13px">${d.name}</div>
            <div style="color:#6b7f8e;font-size:11px;margin-top:2px">Type: ${d.type}</div>
            ${d.score !== undefined ? `<div style="color:${d.color};font-size:11px;margin-top:2px">Score: ${d.score}</div>` : ""}
          </div>`
      )
      .onPointClick((d: PinPoint) => {
        onEntityClick({
          name: d.name,
          type: d.type,
          investability_score: d.score,
        });
      });
  }, [pins, onEntityClick]);

  // Update arcs when data changes
  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;

    globe
      .arcsData(arcs)
      .arcColor("color")
      .arcDashLength("dashLength")
      .arcLabel(
        (d: ArcPoint) =>
          `<div style="background:rgba(0,0,0,0.8);padding:6px 10px;border-radius:6px;border:1px solid #1e2d3a">
            <div style="color:#f0f4f0;font-weight:600;font-size:13px">${d.source} → ${d.target}</div>
            <div style="color:#6b7f8e;font-size:11px;margin-top:2px">${d.type} (${d.strength})</div>
          </div>`
      );
  }, [arcs]);

  return <div ref={containerRef} className="w-full h-full" />;
}

// ─── Loading state ───────────────────────────────────────────────

function GlobeLoading() {
  return (
    <div className="flex flex-col items-center justify-center h-[500px] w-full bg-[#0a0a0a] rounded-xl border border-zinc-800">
      <div className="relative w-16 h-16 mb-4">
        <div className="absolute inset-0 rounded-full border-2 border-zinc-700" />
        <div className="absolute inset-0 rounded-full border-2 border-t-emerald-500 animate-spin" />
      </div>
      <p className="text-zinc-400 text-sm">Loading globe visualization...</p>
      <p className="text-zinc-600 text-xs mt-1">Requires globe.gl (npm install globe.gl)</p>
    </div>
  );
}

// ─── Dynamic import ──────────────────────────────────────────────

interface DynamicGlobeProps {
  pins: PinPoint[];
  arcs: ArcPoint[];
  onEntityClick: (entity: Entity) => void;
}

const DynamicGlobe = dynamic<DynamicGlobeProps>(
  async () => {
    const mod = await import("globe.gl");
    const factory = mod.default as unknown as GlobeFactory;

    return function DynamicGlobeInner(props: DynamicGlobeProps) {
      return (
        <GlobeRenderer
          pins={props.pins}
          arcs={props.arcs}
          onEntityClick={props.onEntityClick}
          globeFactory={factory}
        />
      );
    };
  },
  {
    ssr: false,
    loading: () => <GlobeLoading />,
  }
);

// ─── Props ───────────────────────────────────────────────────────

interface SupplyChainGlobeProps {
  relationships: Relationship[];
  onEntityClick: (entity: Entity) => void;
  height?: number;
}

// ─── Main component ──────────────────────────────────────────────

export function SupplyChainGlobe({
  relationships,
  onEntityClick,
  height = 500,
}: SupplyChainGlobeProps) {
  const pins = useMemo(() => buildPins(relationships), [relationships]);
  const arcs = useMemo(() => buildArcs(relationships), [relationships]);

  const handlePointClick = useCallback(
    (point: PinPoint) => {
      onEntityClick({
        name: point.name,
        type: point.type,
        investability_score: point.score,
      });
    },
    [onEntityClick]
  );

  if (pins.length === 0 && arcs.length === 0) {
    return (
      <div className="flex items-center justify-center h-[500px] w-full bg-[#0a0a0a] rounded-xl border border-zinc-800">
        <p className="text-zinc-400 text-sm">
          No geographic data available for supply chain relationships.
        </p>
      </div>
    );
  }

  return (
    <div
      className="relative w-full rounded-xl border border-zinc-800 overflow-hidden bg-[#0a0a0a]"
      style={{ height }}
    >
      {/* Legend: relationship types */}
      <div className="absolute top-3 left-3 z-10 flex flex-col gap-1.5 bg-black/60 backdrop-blur-sm rounded-lg px-3 py-2 border border-zinc-800">
        <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">
          Relationship Type
        </span>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-xs text-zinc-300">Supplier</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          <span className="text-xs text-zinc-300">Customer</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-xs text-zinc-300">Competitor</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-purple-500" />
          <span className="text-xs text-zinc-300">Partner</span>
        </div>
      </div>

      {/* Legend: investability score */}
      <div className="absolute top-3 right-3 z-10 flex flex-col gap-1.5 bg-black/60 backdrop-blur-sm rounded-lg px-3 py-2 border border-zinc-800">
        <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wider">
          Investability Score
        </span>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-xs text-zinc-300">&gt; 70</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-yellow-500" />
          <span className="text-xs text-zinc-300">40-70</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-xs text-zinc-300">&lt; 40</span>
        </div>
      </div>

      <DynamicGlobe
        pins={pins}
        arcs={arcs}
        onEntityClick={handlePointClick as (entity: Entity) => void}
      />
    </div>
  );
}

export default SupplyChainGlobe;
