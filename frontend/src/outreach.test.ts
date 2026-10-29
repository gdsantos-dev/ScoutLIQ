import { describe, expect, it } from "vitest";
import {
  DEFAULT_OUTREACH_TEMPLATES,
  buildOutreachContext,
  emailUrl,
  parseStoredTemplates,
  renderOutreachTemplate,
  renderOutreachText,
  whatsappUrl,
} from "./outreach";
import type { Lead } from "./types";

function lead(overrides: Partial<Lead> = {}): Lead {
  return {
    id: "lead-1",
    name: "Padaria Aurora",
    category: "Padaria",
    city: "Recife",
    country: "BR",
    address: "",
    latitude: -8,
    longitude: -34,
    rating: 4.6,
    reviews: 90,
    website: "https://aurora.example",
    website_status: "poor",
    instagram: "",
    instagram_active: true,
    phone: "5581999999999",
    whatsapp: "5581888888888",
    contact: "Marina",
    potential_cents: 300000,
    potential_currency: "BRL",
    notes: "",
    stage: "contacted",
    in_pipeline: true,
    demo: false,
    version: 1,
    score: {
      value: 82,
      version: "2",
      reasons: [],
      dimensions: {},
      niche: { key: "bakery", label: "Padaria", confidence: 1, matched_term: "", matched_by: "category", expectations: [] },
      diagnosis: [{ key: "site", area: "website", severity: "high", title: "Checkout confuso", detail: "", evidence: [], service_hints: [] }],
      confidence: { value: 90, level: "high", components: {}, missing: [] },
      service_scores: [{ key: "site", label: "Novo site", value: 88, need: 90, commercial_context: 80, signals: [] }],
      competitive: null,
      commercial_structure: { value: 0, level: "low", confidence: 0, components: {}, signals: [] },
      timing: { value: 0, level: "low", signals: [], latest_event_at: null },
    },
    source: "test",
    next_action: "Enviar proposta",
    next_action_on: "2026-09-30",
    pipeline_added_at: 1,
    last_contact_at: 2,
    website_intelligence: {},
    website_analyzed_at: null,
    competitive_context: null,
    competitive_analyzed_at: null,
    commercial_signal_analyzed_at: null,
    watchlisted: false,
    watch_started_at: null,
    watch_last_checked_at: null,
    watch_last_event_at: null,
    enrichment: { fields: {} },
    enrichment_analyzed_at: null,
    created_at: 1,
    ...overrides,
  };
}

describe("outreach", () => {
  it("builds factual context from the lead", () => {
    const context = buildOutreachContext(lead());
    expect(context.empresa).toBe("Padaria Aurora");
    expect(context.saudacao_contato).toBe("Olá, Marina");
    expect(context.oportunidade).toBe("checkout confuso");
    expect(context.servico).toBe("Novo site");
  });

  it("renders known variables and removes unknown variables", () => {
    const text = renderOutreachText("{{saudacao_contato}} · {{empresa}} · {{inexistente}}", buildOutreachContext(lead()));
    expect(text).toBe("Olá, Marina · Padaria Aurora ·");
  });

  it("renders a default template", () => {
    const rendered = renderOutreachTemplate(DEFAULT_OUTREACH_TEMPLATES[0], lead());
    expect(rendered.body).toContain("Padaria Aurora");
    expect(rendered.body).toContain("checkout confuso");
  });

  it("falls back to defaults when storage is invalid", () => {
    expect(parseStoredTemplates("{not json")).toHaveLength(DEFAULT_OUTREACH_TEMPLATES.length);
  });

  it("builds encoded external contact links", () => {
    expect(whatsappUrl("+55 (81) 99999-0000", "Oi & tudo bem?")).toContain("5581999990000");
    expect(whatsappUrl("", "Oi")).toBe("");
    expect(emailUrl("a@b.com", "Assunto A", "Linha 1")).toContain("mailto:a@b.com?");
    expect(emailUrl("", "x", "y")).toBe("");
  });
});
