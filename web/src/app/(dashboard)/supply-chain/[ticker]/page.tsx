"use client";

import { useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useSupplyChain } from "@/hooks/use-supply-chain";
import type { Relationship, RelationshipEntry } from "@/types/supply-chain";
import {
  getInvestabilityColor,
  getRiskLabel,
} from "@/lib/utils";
import {
  ArrowLeft,
  Globe,
  ListFilter,
  TrendingUp,
  AlertTriangle,
  ArrowUpDown,
  ExternalLink,
} from "lucide-react";

// Dynamically import the globe component (created by another agent)
const SupplyChainGlobe = dynamic(
  () => import("@/components/charts/SupplyChainGlobe"),
  { ssr: false, loading: () => <GlobeSkeleton /> },
);

function GlobeSkeleton() {
  return (
    <div className="flex items-center justify-center h-[500px] bg-[#0d1319] rounded-lg">
      <Skeleton className="h-16 w-16 rounded-full" />
    </div>
  );
}

type SortKey = "company" | "relationship" | "country" | "risk" | "investability" | "exposure";
type SortDir = "asc" | "desc";

export default function SupplyChainPage() {
  const params = useParams();
  const ticker = (params?.ticker as string) ?? "";
  const upperTicker = ticker.toUpperCase();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState("globe");
  const [sortKey, setSortKey] = useState<SortKey>("risk");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const { data, isLoading, error } = useSupplyChain(upperTicker);

  // Normalize API response into Relationship objects with geo mapped from target_geo.
  const flatRelationships = useMemo((): Relationship[] => {
    if (!data?.relationships) return [];
    return (data.relationships as RelationshipEntry[]).map((e) => ({
      ...e,
      geo: e.target_geo,
      financials: e.financials ?? {},
    }));
  }, [data?.relationships]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return <ArrowUpDown className="h-3 w-3 inline ml-1 opacity-40" />;
    return sortDir === "asc" ? (
      <ArrowUpDown className="h-3 w-3 inline ml-1 text-[#84cc16]" />
    ) : (
      <ArrowUpDown className="h-3 w-3 inline ml-1 text-[#84cc16] rotate-180" />
    );
  };

  const sortedRelationships = useMemo(() => {
    const rels = [...flatRelationships];
    rels.sort((a, b) => {
      let aVal: number | string = "";
      let bVal: number | string = "";
      switch (sortKey) {
        case "company":
          aVal = a.source ?? "";
          bVal = b.source ?? "";
          break;
        case "relationship":
          aVal = a.type ?? "";
          bVal = b.type ?? "";
          break;
        case "country":
          aVal = a.geo?.domicile ?? "";
          bVal = b.geo?.domicile ?? "";
          break;
        case "risk":
          aVal = (a.financials?.risk_score as number | undefined) ?? 0;
          bVal = (b.financials?.risk_score as number | undefined) ?? 0;
          break;
        case "investability":
          aVal = (a.investability_score as number | undefined) ?? 0;
          bVal = (b.investability_score as number | undefined) ?? 0;
          break;
        case "exposure":
          aVal = (a.financials?.revenue_exposure_pct as number | undefined) ?? 0;
          bVal = (b.financials?.revenue_exposure_pct as number | undefined) ?? 0;
          break;
      }
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }
      return sortDir === "asc"
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal));
    });
    return rels;
  }, [flatRelationships, sortKey, sortDir]);

  // Derived: unique entities from relationships (deduplicated by target name)
  const sortedEntities = useMemo(() => {
    if (flatRelationships.length === 0) return [];
    const entityMap = new Map<string, { name: string; type: Relationship["type"]; investability_score: number }>();
    for (const rel of flatRelationships) {
      const name = rel.target;
      if (!entityMap.has(name)) {
        entityMap.set(name, {
          name,
          type: rel.type,
          investability_score: rel.investability_score ?? 0,
        });
      }
    }
    const ents = Array.from(entityMap.values());
    ents.sort((a, b) => {
      return sortDir === "asc" ? a.investability_score - b.investability_score : b.investability_score - a.investability_score;
    });
    return ents;
  }, [flatRelationships, sortDir]);

  // Derived: country exposure aggregated from relationship geo risk_scores
  const sortedCountryExposure = useMemo(() => {
    if (flatRelationships.length === 0) return [];
    const countryMap = new Map<string, { country: string; riskEntries: Array<{ name: string; risk_score: number | null; risk_label: string }> }>();
    for (const rel of flatRelationships) {
      const scores = rel.geo?.risk_scores;
      if (!scores) continue;
      for (const rs of scores) {
        const cc = rs.country_code;
        if (!countryMap.has(cc)) {
          countryMap.set(cc, { country: rs.name, riskEntries: [] });
        }
        countryMap.get(cc)!.riskEntries.push(rs);
      }
    }
    const total = flatRelationships.length;
    const exp = Array.from(countryMap.values()).map(({ country, riskEntries }) => {
      const count = riskEntries.length;
      // Derive risk levels from the highest risk_label seen
      const labels = riskEntries.map((r) => (r.risk_label ?? "").toLowerCase());
      const deriveRisk = (): "none" | "low" | "medium" | "high" | "critical" => {
        if (labels.some((l) => l.includes("critical"))) return "critical";
        if (labels.some((l) => l.includes("high"))) return "high";
        if (labels.some((l) => l.includes("low") || l.includes("minimal"))) return "low";
        if (labels.some((l) => l.includes("moderate") || l.includes("medium"))) return "medium";
        return "none";
      };
      return {
        country,
        exposure_pct: (count / total) * 100,
        entity_count: count,
        sanctions_risk: deriveRisk(),
        tariff_risk: deriveRisk(),
        geopolitical_risk: deriveRisk(),
      };
    });
    exp.sort((a, b) => {
      if (sortDir === "asc") return a.exposure_pct - b.exposure_pct;
      return b.exposure_pct - a.exposure_pct;
    });
    return exp;
  }, [flatRelationships, sortDir]);

  // Derived summary stats from relationships
  const summary = useMemo(() => {
    if (flatRelationships.length === 0) {
      return { total_suppliers: 0, total_customers: 0, countries_exposed: 0, avg_risk_score: null, high_risk_countries: 0 };
    }
    const rels = flatRelationships;
    const total_suppliers = rels.filter((r) => r.type === "supplier").length;
    const total_customers = rels.filter((r) => r.type === "customer").length;

    // Unique countries from domicile
    const countries = new Set<string>();
    for (const rel of rels) {
      if (rel.geo?.domicile) countries.add(rel.geo.domicile);
      for (const rs of rel.geo?.risk_scores ?? []) {
        if (rs.country_code) countries.add(rs.country_code);
      }
    }

    // Average risk_score from all risk_scores arrays
    const allScores: number[] = [];
    for (const rel of rels) {
      for (const rs of rel.geo?.risk_scores ?? []) {
        if (rs.risk_score !== null && rs.risk_score !== undefined) {
          allScores.push(rs.risk_score);
        }
      }
    }
    const avg_risk_score = allScores.length > 0 ? allScores.reduce((a, b) => a + b, 0) / allScores.length : null;

    // High-risk countries: count of unique countries with risk_label containing "high" or "critical"
    const highRiskCountries = new Set<string>();
    for (const rel of rels) {
      for (const rs of rel.geo?.risk_scores ?? []) {
        const label = (rs.risk_label ?? "").toLowerCase();
        if (label.includes("high") || label.includes("critical")) {
          if (rs.country_code) highRiskCountries.add(rs.country_code);
        }
      }
    }

    return {
      total_suppliers,
      total_customers,
      countries_exposed: countries.size,
      avg_risk_score,
      high_risk_countries: highRiskCountries.size,
    };
  }, [flatRelationships]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <div>
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64 mt-2" />
          </div>
        </div>
        <div className="flex gap-1 border-b border-[#1e2d3a]">
          {["Globe", "Explorer", "Investability", "Risk"].map((t) => (
            <Skeleton key={t} className="h-8 w-24" />
          ))}
        </div>
        <Skeleton className="h-[500px] w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-2xl font-bold">Supply Chain</h1>
        </div>
        <Card className="border-red-500/30 bg-red-500/10">
          <CardContent className="pt-6">
            <p className="text-sm font-semibold text-red-400 mb-1">Failed to load supply chain data</p>
            <p className="text-xs text-[#6b7f8e]">
              {(error as Error).message || "Check your connection or API key."}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data || flatRelationships.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-2xl font-bold">{upperTicker}</h1>
        </div>
        <Card>
          <CardContent className="pt-12 pb-12 text-center">
            <Globe className="h-12 w-12 text-[#3a5570] mx-auto mb-4" />
            <p className="text-sm font-medium text-[#c8d8e4] mb-1">No supply chain data</p>
            <p className="text-xs text-[#6b7f8e]">
              Supply chain relationships have not been mapped for {upperTicker} yet.
            </p>
            <Link
              href={`/company/${upperTicker}`}
              className="inline-flex items-center gap-1 mt-4 text-xs text-[#84cc16] hover:text-[#65a30d] transition-colors"
            >
              View company profile <ExternalLink className="h-3 w-3" />
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{upperTicker}</h1>
            <Badge variant="outline" className="text-xs">Supply Chain</Badge>
          </div>
          <p className="text-sm text-[#6b7f8e]">
            {data?.company_name ?? upperTicker} &middot; {summary?.total_suppliers ?? 0} suppliers &middot; {summary?.total_customers ?? 0} customers &middot; {summary?.countries_exposed ?? 0} countries
          </p>
        </div>
        <Link
          href={`/company/${upperTicker}`}
          className="text-xs text-[#84cc16] hover:text-[#65a30d] flex items-center gap-1 transition-colors"
        >
          Company profile <ExternalLink className="h-3 w-3" />
        </Link>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <p className="text-xs text-[#6b7f8e]">Total Relationships</p>
          <p className="text-2xl font-bold mt-1">{(summary?.total_suppliers ?? 0) + (summary?.total_customers ?? 0)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-[#6b7f8e]">Countries Exposed</p>
          <p className="text-2xl font-bold mt-1">{summary?.countries_exposed ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-[#6b7f8e]">Avg Risk Score</p>
          <p className="text-2xl font-bold mt-1">
            {summary?.avg_risk_score !== null && summary?.avg_risk_score !== undefined
              ? summary.avg_risk_score.toFixed(0)
              : "N/A"}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-[#6b7f8e]">High-Risk Countries</p>
          <p className="text-2xl font-bold mt-1 text-red-400">{summary?.high_risk_countries ?? 0}</p>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs
        tabs={[
          { id: "globe", label: "Globe" },
          { id: "explorer", label: "Explorer" },
          { id: "investability", label: "Investability" },
          { id: "risk", label: "Risk Table" },
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Tab: Globe */}
      {activeTab === "globe" && (
        <SupplyChainGlobe
          relationships={flatRelationships}
          onEntityClick={(entity) => {
            if (entity.name) router.push(`/company/${entity.name.toUpperCase()}`);
          }}
        />
      )}

      {/* Tab: Explorer */}
      {activeTab === "explorer" && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <ListFilter className="h-4 w-4" />
              Relationship Explorer
            </CardTitle>
            <CardDescription>
              All supply chain relationships sorted by {sortKey} ({sortDir})
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <button onClick={() => handleSort("company")} className="flex items-center">
                      Company <SortIcon col="company" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button onClick={() => handleSort("relationship")} className="flex items-center">
                      Type <SortIcon col="relationship" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button onClick={() => handleSort("country")} className="flex items-center">
                      Country <SortIcon col="country" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button onClick={() => handleSort("exposure")} className="flex items-center">
                      Exposure <SortIcon col="exposure" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button onClick={() => handleSort("risk")} className="flex items-center">
                      Risk <SortIcon col="risk" />
                    </button>
                  </TableHead>
                  <TableHead>Strength</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedRelationships.map((rel, i) => {
                  const riskScore = rel.financials?.risk_score as number | undefined;
                  const exposure = rel.financials?.revenue_exposure_pct as number | undefined;
                  return (
                    <TableRow key={i}>
                      <TableCell className="font-medium text-[#f0f4f0]">
                        <div className="flex items-center gap-2">
                          {rel.target && rel.target !== "N/A" && (
                            <Link
                              href={`/company/${rel.target}`}
                              className="text-[#84cc16] hover:underline font-mono"
                            >
                              {rel.target}
                            </Link>
                          )}
                          <span className="text-[#6b7f8e]">{rel.source}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            rel.type === "supplier"
                              ? "primary"
                              : rel.type === "customer"
                                ? "secondary"
                                : "outline"
                          }
                          className="text-[10px]"
                        >
                          {rel.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-[#c8d8e4] text-sm">
                        {rel.geo?.domicile ?? "—"}
                      </TableCell>
                      <TableCell className="font-mono text-sm text-[#c8d8e4]">
                        {exposure !== null && exposure !== undefined ? `${exposure.toFixed(1)}%` : "—"}
                      </TableCell>
                      <TableCell>
                        {riskScore !== null && riskScore !== undefined ? (
                          <Badge
                            variant={
                              riskScore >= 70
                                ? "success"
                                : riskScore >= 40
                                  ? "warning"
                                  : "danger"
                            }
                          >
                            {riskScore.toFixed(0)}
                          </Badge>
                        ) : (
                          <span className="text-[#6b7f8e] text-sm">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            rel.strength === "strong"
                              ? "success"
                              : rel.strength === "medium"
                                ? "warning"
                                : "secondary"
                          }
                          className="text-[10px]"
                        >
                          {rel.strength}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Tab: Investability */}
      {activeTab === "investability" && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Upstream Investability
            </CardTitle>
            <CardDescription>
              Entities ranked by investability score
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Entity</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Investability Score</TableHead>
                  <TableHead>Risk Label</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedEntities.length > 0 ? (
                  sortedEntities.map((entity, i) => {
                    const score = entity.investability_score ?? 0;
                    const riskLabel = getRiskLabel(score);
                    const colorClass = getInvestabilityColor(score);
                    return (
                      <TableRow key={i}>
                        <TableCell className="font-medium text-[#f0f4f0]">
                          {entity.name}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              entity.type === "supplier"
                                ? "primary"
                                : entity.type === "customer"
                                  ? "secondary"
                                  : "outline"
                            }
                            className="text-[10px]"
                          >
                            {entity.type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className={`font-mono font-semibold ${colorClass}`}>
                            {score.toFixed(0)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              riskLabel === "Strong"
                                ? "success"
                                : riskLabel === "Moderate"
                                  ? "warning"
                                  : "danger"
                            }
                          >
                            {riskLabel}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-[#6b7f8e] py-8">
                      No investability data available for upstream entities.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Tab: Risk Table */}
      {activeTab === "risk" && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-400" />
              Country Exposure & Risk
            </CardTitle>
            <CardDescription>
              Geographic risk breakdown including sanctions and tariff exposure
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Country</TableHead>
                  <TableHead>Exposure</TableHead>
                  <TableHead>Entities</TableHead>
                  <TableHead>Sanctions Risk</TableHead>
                  <TableHead>Tariff Risk</TableHead>
                  <TableHead>Geopolitical Risk</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedCountryExposure.length > 0 ? (
                  sortedCountryExposure.map((c, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium text-[#f0f4f0]">
                        {c.country}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-[#1a2a38] overflow-hidden">
                            <div
                              className="h-full rounded-full bg-[#84cc16]"
                              style={{ width: `${Math.min(c.exposure_pct, 100)}%` }}
                            />
                          </div>
                          <span className="font-mono text-sm text-[#c8d8e4]">
                            {c.exposure_pct.toFixed(1)}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-sm text-[#c8d8e4]">
                        {c.entity_count}
                      </TableCell>
                      <TableCell>
                        <RiskBadge level={c.sanctions_risk} />
                      </TableCell>
                      <TableCell>
                        <RiskBadge level={c.tariff_risk} />
                      </TableCell>
                      <TableCell>
                        <RiskBadge level={c.geopolitical_risk} />
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-[#6b7f8e] py-8">
                      No country exposure data available.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Small helpers ──────────────────────────────────────────────

function RiskBadge({ level }: { level: string }) {
  const variantMap: Record<string, "success" | "warning" | "danger" | "secondary"> = {
    none: "success",
    low: "success",
    medium: "warning",
    high: "danger",
    critical: "danger",
  };
  return (
    <Badge variant={variantMap[level] ?? "secondary"} className="text-[10px] capitalize">
      {level}
    </Badge>
  );
}
