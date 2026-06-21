// Supply chain relationship types for the 3D globe visualization

export interface RiskScoreEntry {
  country_code: string;
  name: string;
  risk_score: number | null;
  risk_label: string;
}

export interface RelationshipGeo {
  domicile: string | null;
  manufacturing: string[];
  risk_scores?: RiskScoreEntry[];
}

/** Raw entry from the API — uses target_geo, may lack investability_score/financials */
export interface RelationshipEntry {
  source: string;
  target: string;
  type: "supplier" | "customer" | "competitor" | "partner";
  strength: "strong" | "medium" | "weak";
  description?: string;
  target_geo?: RelationshipGeo;
  financials?: Record<string, unknown>;
  investability_score?: number;
  has_supply_chain?: boolean;
}

/** Normalized relationship used by the UI — geo is mapped from target_geo */
export interface Relationship extends RelationshipEntry {
  geo?: RelationshipGeo;
  financials: Record<string, unknown>;
}

export interface Entity {
  name: string;
  type: Relationship["type"];
  investability_score?: number;
}

// ─── Derived types (computed client-side from relationships) ───

export interface DerivedEntity {
  name: string;
  type: Relationship["type"];
  investability_score: number;
}

export interface DerivedCountryExposure {
  country: string;
  exposure_pct: number;
  entity_count: number;
  sanctions_risk: "none" | "low" | "medium" | "high" | "critical";
  tariff_risk: "none" | "low" | "medium" | "high" | "critical";
  geopolitical_risk: "none" | "low" | "medium" | "high" | "critical";
}

export interface DerivedSupplyChainSummary {
  total_suppliers: number;
  total_customers: number;
  countries_exposed: number;
  high_risk_countries: number;
  avg_risk_score: number | null;
}

/**
 * Actual API response shape from GET /api/data/<ticker>/supply-chain.
 * Relationships is a flat array of entries (the backend also returns
 * a flat array, not grouped by type).
 */
export interface SupplyChainResponse {
  ticker?: string;
  company_name?: string;
  relationships: RelationshipEntry[];
  multi_hop_paths?: Array<Record<string, unknown>>;
}

// Country to lat/lon mapping for pin placement.
// Extended as needed — these are common domicile/manufacturing locations.
export const COUNTRY_COORDS: Record<string, [number, number]> = {
  US: [39.8283, -98.5795],
  CN: [35.8617, 104.1954],
  DE: [51.1657, 10.4515],
  JP: [36.2048, 138.2529],
  KR: [35.9078, 127.7669],
  TW: [23.6978, 120.9605],
  IN: [20.5937, 78.9629],
  GB: [55.3781, -3.436],
  FR: [46.2276, 2.2137],
  CA: [56.1304, -106.3468],
  AU: [25.2744, 133.7751],
  BR: [-14.235, -51.9253],
  MX: [23.6345, -102.5528],
  VN: [14.0583, 108.2772],
  TH: [15.87, 100.9925],
  MY: [4.2105, 101.9758],
  SG: [1.3521, 103.8198],
  ID: [-0.7893, 113.9213],
  IT: [41.8719, 12.5674],
  NL: [52.1326, 5.2913],
  CH: [46.8182, 8.2275],
  SE: [60.1282, 18.6435],
  IL: [31.0461, 34.8516],
  HK: [22.3193, 114.1694],
  PH: [12.8797, 121.774],
};
