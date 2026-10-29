import { describe, expect, it } from "vitest";
import { getOpportunityBrief, getOpportunityPriority } from "./opportunity";
import type { Lead } from "./types";

it("keeps insufficient evidence distinct from a low quality business", () => {
  const priority = getOpportunityPriority({
    value: 49,
    status: "insufficient",
  } as Lead["score"]);
  expect(priority.label).toBe("Qualificação provisória");
  expect(priority.explanation).toContain("não indica uma empresa ruim");
});

const baseLead: Lead = {
  id: "lead-1",
  name: "Clínica Exemplo",
  category: "Clínica",
  city: "Recife",
  country: "BR",
  address: "",
  latitude: -8.05,
  longitude: -34.9,
  rating: null,
  reviews: null,
  website: "",
  website_status: "unknown",
  instagram: "",
  instagram_active: false,
  phone: "",
  whatsapp: "",
  contact: "",
  potential_cents: 0,
  potential_currency: "BRL",
  notes: "",
  stage: "discovered",
  in_pipeline: false,
  demo: false,
  version: 1,
  score: {
    value: 0,
    version: "2.4",
    reasons: [],
    dimensions: {},
    niche: {
      key: "generic",
      label: "Negócio local",
      confidence: 35,
      matched_term: "",
      matched_by: "fallback",
      expectations: [],
    },
    diagnosis: [],
    confidence: { value: 0, level: "low", components: {}, missing: [] },
    service_scores: [],
    competitive: null,
    commercial_structure: {
      value: 0,
      level: "low",
      confidence: 0,
      components: {},
      signals: [],
    },
    timing: { value: 0, level: "low", signals: [], latest_event_at: null },
  },
  source: "test",
  next_action: "",
  next_action_on: null,
  pipeline_added_at: null,
  last_contact_at: null,
  website_intelligence: {},
  website_analyzed_at: null,
  competitive_context: null,
  competitive_analyzed_at: null,
  commercial_signal_analyzed_at: null,
  watchlisted: false,
  watch_started_at: null,
  watch_last_checked_at: null,
  watch_last_event_at: null,
  enrichment: {},
  enrichment_analyzed_at: null,
  created_at: 0,
};

describe("opportunity priority", () => {
  it("uses deterministic score bands", () => {
    expect(getOpportunityPriority(70).level).toBe("high");
    expect(getOpportunityPriority(69).level).toBe("medium");
    expect(getOpportunityPriority(40).level).toBe("medium");
    expect(getOpportunityPriority(39).level).toBe("low");
  });

  it("explains a strong local company without a confirmed website", () => {
    const lead: Lead = {
      ...baseLead,
      rating: 4.8,
      reviews: 286,
      phone: "+5581999999999",
      website_status: "none",
      score: {
        value: 75,
        version: "2.4",
        niche: {
          key: "healthcare",
          label: "Saúde e clínicas",
          confidence: 92,
          matched_term: "clinica",
          matched_by: "category",
          expectations: [],
        },
        diagnosis: [],
        confidence: { value: 90, level: "high", components: {}, missing: [] },
        service_scores: [
          {
            key: "site_institucional",
            label: "Site institucional",
            value: 90,
            need: 72,
            commercial_context: 18,
            signals: ["Sem site próprio confirmado"],
          },
        ],
        competitive: null,
        commercial_structure: {
          value: 50,
          level: "medium",
          confidence: 80,
          components: {},
          signals: [],
        },
        timing: {
          value: 35,
          level: "medium",
          signals: [],
          latest_event_at: null,
        },
        dimensions: {
          digital_need: { value: 50, max: 50 },
          public_demand: { value: 18, max: 20 },
          reachability: { value: 6, max: 20 },
          digital_activity: { value: 0, max: 10 },
        },
        reasons: [
          {
            dimension: "digital_need",
            key: "no_website",
            label: "Sem site confirmado",
            points: 50,
          },
          {
            dimension: "public_demand",
            key: "reviews",
            label: "286 avaliações",
            points: 10,
          },
          {
            dimension: "public_demand",
            key: "rating",
            label: "Nota 4.8",
            points: 6,
          },
          {
            dimension: "reachability",
            key: "phone",
            label: "Telefone disponível",
            points: 6,
          },
        ],
      },
    };

    const brief = getOpportunityBrief(lead);
    expect(brief.priority).toBe("high");
    expect(brief.headline).toBe("Presença local sem site confirmado");
    expect(brief.signals.map((item) => item.key)).toContain("website_none");
    expect(brief.signals.map((item) => item.key)).toContain(
      "local_presence_strong",
    );
    expect(brief.signals.map((item) => item.key)).toContain("phone");
  });

  it("keeps sparse leads at low priority without inventing evidence", () => {
    const brief = getOpportunityBrief(baseLead);
    expect(brief.priority).toBe("low");
    expect(brief.headline).toBe("Site ainda precisa ser verificado");
    expect(brief.signals).toHaveLength(1);
    expect(brief.signals[0].key).toBe("website_unknown");
  });
});
