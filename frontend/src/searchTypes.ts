export type SearchLocation = {
  id: string;
  name: string;
  formatted: string;
  administrative_type: "district" | "city" | "county" | "state" | "country";
  city: string;
  state: string;
  country: string;
  country_code: string;
  source: "geoapify" | "ibge";
  resolved_at: number;
};

export type SearchArea = {
  kind: "bounds" | "polygon";
  bounds: number[];
  polygon: [number, number][];
};

export type CommercialIntent = {
  search_mode?: "general" | "directed" | "filtered" | "ambiguous" | "legacy";
  query: string;
  target: 25 | 50 | 75 | 100;
  location?: SearchLocation | null;
  area?: SearchArea | null;
  legacy?: Omit<import("./types").RadarSavedQuery, "commercial_intent"> | null;
  market: { country: string; region: string; city: string };
  sectors: string[];
  profile: { business_type: string; size: string; independence: string };
  requirements: string[];
  preferences: string[];
  exclusions: string[];
  unresolved: string[];
  requirement_mode: "all" | "any";
};
