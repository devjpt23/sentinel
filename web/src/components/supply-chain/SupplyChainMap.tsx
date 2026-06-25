"use client";

import { useState, useMemo } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  Sphere,
  Graticule,
} from "react-simple-maps";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Globe } from "lucide-react";

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

export interface CountryExposure {
  country: string;
  exposure_pct: number;
  entity_count: number;
  sanctions_risk: string;
  tariff_risk: string;
  geopolitical_risk: string;
}

interface SupplyChainMapProps {
  data: CountryExposure[];
}

interface TooltipState {
  content: string;
  x: number;
  y: number;
}

// Maps common country name variants to the names used in world-atlas TopoJSON.
// The TopoJSON uses names like "United States of America", "Czechia", "Dem. Rep. Congo", etc.
const NAME_MAP: Record<string, string> = {
  "United States": "United States of America",
  US: "United States of America",
  USA: "United States of America",
  "Czech Republic": "Czechia",
  Swaziland: "eSwatini",
  Eswatini: "eSwatini",
  "Democratic Republic of the Congo": "Dem. Rep. Congo",
  "DR Congo": "Dem. Rep. Congo",
  DRC: "Dem. Rep. Congo",
  "South Sudan": "S. Sudan",
  "Central African Republic": "Central African Rep.",
  "Dominican Republic": "Dominican Rep.",
  "Equatorial Guinea": "Eq. Guinea",
  "Solomon Islands": "Solomon Is.",
  "Falkland Islands": "Falkland Is.",
  "Bosnia and Herzegovina": "Bosnia and Herz.",
  "Western Sahara": "W. Sahara",
  "North Macedonia": "Macedonia",
  UK: "United Kingdom",
  "Great Britain": "United Kingdom",
  Burma: "Myanmar",
  "East Timor": "Timor-Leste",
  "Ivory Coast": "Côte d'Ivoire",
  "Russian Federation": "Russia",
  "Viet Nam": "Vietnam",
  "Iran (Islamic Republic of)": "Iran",
  "Syrian Arab Republic": "Syria",
  DPRK: "North Korea",
  "Republic of Korea": "South Korea",
  "United Republic of Tanzania": "Tanzania",
  "State of Palestine": "Palestine",
  "Türkiye": "Turkey",
  "Lao PDR": "Laos",
  "Brunei Darussalam": "Brunei",
  "Cape Verde": "Cabo Verde",
  "The Bahamas": "Bahamas",
  "The Gambia": "Gambia",
  "People's Republic of China": "China",
  UAE: "United Arab Emirates",
  "Northern Cyprus": "N. Cyprus",
  "French Southern and Antarctic Lands": "Fr. S. Antarctic Lands",
  "São Tomé and Principe": "São Tomé and Principe",
  "Trinidad & Tobago": "Trinidad and Tobago",
};

function computeRiskScore(entry: CountryExposure): number {
  const riskValues: Record<string, number> = {
    none: 0,
    low: 20,
    medium: 50,
    high: 75,
    critical: 100,
  };
  const sanctions = riskValues[entry.sanctions_risk] ?? 0;
  const tariff = riskValues[entry.tariff_risk] ?? 0;
  const geopolitical = riskValues[entry.geopolitical_risk] ?? 0;
  return (sanctions + tariff + geopolitical) / 3;
}

function getRiskColor(score: number): string {
  if (score <= 15) return "#22c55e";
  if (score <= 30) return "#84cc16";
  if (score <= 45) return "#65a30d";
  if (score <= 55) return "#eab308";
  if (score <= 70) return "#f97316";
  return "#ef4444";
}

export function SupplyChainMap({ data }: SupplyChainMapProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const countryRisk = useMemo(() => {
    const map = new Map<string, { score: number; entry: CountryExposure }>();
    for (const entry of data) {
      const mappedName = NAME_MAP[entry.country] || entry.country;
      const score = computeRiskScore(entry);
      map.set(mappedName, { score, entry });
    }
    return map;
  }, [data]);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Globe className="h-4 w-4" />
            Supply Chain Map
          </CardTitle>
          <CardDescription>Country-level risk visualization</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-[400px] text-[#6b7f8e] text-sm">
            No country exposure data available to display on the map.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Globe className="h-4 w-4" />
          Supply Chain Risk Map
        </CardTitle>
        <CardDescription>
          Countries colored by composite risk score (sanctions, tariff, geopolitical)
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <ComposableMap
            projection="geoMercator"
            projectionConfig={{ scale: 120 }}
            style={{ width: "100%", height: "auto" }}
          >
            <Sphere stroke="#1e2d3a" strokeWidth={0.5} fill="#0a0e13" />
            <Graticule stroke="#1e2d3a" strokeWidth={0.3} />
            <Geographies geography={GEO_URL}>
              {({ geographies }) =>
                geographies.map((geo) => {
                  const geoName: string = geo.properties.name;
                  const matched = countryRisk.get(geoName);
                  const fillColor = matched
                    ? getRiskColor(matched.score)
                    : "#151f2b";

                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      fill={fillColor}
                      stroke="#1e2d3a"
                      strokeWidth={0.4}
                      style={{
                        default: { outline: "none" },
                        hover: {
                          outline: "none",
                          fill: matched ? "#f0f4f0" : "#2a3f52",
                        },
                        pressed: { outline: "none" },
                      }}
                      onMouseEnter={(event: React.MouseEvent) => {
                        if (!matched) return;
                        const e = matched.entry;
                        setTooltip({
                          content: [
                            `<strong>${e.country}</strong>`,
                            `Risk Score: ${matched.score.toFixed(0)}/100`,
                            `Exposure: ${e.exposure_pct.toFixed(1)}%`,
                            `Entities: ${e.entity_count}`,
                            `Sanctions: ${e.sanctions_risk}`,
                            `Tariff: ${e.tariff_risk}`,
                            `Geopolitical: ${e.geopolitical_risk}`,
                          ].join("<br/>"),
                          x: event.clientX,
                          y: event.clientY,
                        });
                      }}
                      onMouseMove={(event: React.MouseEvent) => {
                        if (tooltip) {
                          setTooltip((prev) =>
                            prev
                              ? { ...prev, x: event.clientX, y: event.clientY }
                              : null
                          );
                        }
                      }}
                      onMouseLeave={() => {
                        setTooltip(null);
                      }}
                    />
                  );
                })
              }
            </Geographies>
          </ComposableMap>

          {tooltip && (
            <div
              className="fixed z-50 pointer-events-none px-3 py-2 rounded-lg bg-[#0d1319] border border-[#1e2d3a] shadow-xl text-xs text-[#c8d8e4] max-w-[220px] leading-relaxed"
              style={{ left: tooltip.x + 12, top: tooltip.y - 12 }}
              dangerouslySetInnerHTML={{ __html: tooltip.content }}
            />
          )}
        </div>

        {/* Legend */}
        <div className="flex items-center justify-center flex-wrap gap-3 mt-4 text-[10px] text-[#6b7f8e]">
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "#22c55e" }} />
            <span>Low (0-15)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "#84cc16" }} />
            <span>Moderate (16-30)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "#eab308" }} />
            <span>Medium (31-55)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "#f97316" }} />
            <span>High (56-70)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "#ef4444" }} />
            <span>Critical (71+)</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: "#151f2b" }} />
            <span>No data</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
