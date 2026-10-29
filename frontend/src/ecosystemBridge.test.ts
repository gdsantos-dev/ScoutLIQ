import { describe, expect, it } from "vitest";
import { buildBridgePackage, bridgeFilename } from "./ecosystemBridge";
import type { Lead, Sale, User } from "./types";

const user = {
  id: "u1",
  email: "owner@example.com",
  name: "Workspace",
  accent: "crimson",
  motion: "full",
  timezone: "America/Recife",
  locale: "pt-BR",
  default_currency: "BRL",
} satisfies User;

const lead = {
  id: "l1",
  name: "Acme",
  category: "Restaurante",
  city: "Recife",
  country: "BR",
  address: "",
  latitude: 0,
  longitude: 0,
  rating: null,
  reviews: null,
  website: "https://acme.test",
  website_status: "poor",
  instagram: "@acme",
  instagram_active: true,
  phone: "81999999999",
  whatsapp: "81999999999",
  contact: "Ana",
  potential_cents: 300000,
  potential_currency: "BRL",
  notes: "não exportar",
  stage: "negotiating",
  in_pipeline: true,
  demo: false,
  version: 1,
  score: {
    value: 82,
    version: "2",
    reasons: [],
    dimensions: {},
    niche: { key: "restaurant", label: "Restaurante", confidence: 90, matched_term: "", matched_by: "category", expectations: [] },
    diagnosis: [{ key: "site", area: "site", severity: "high", title: "Site fraco", detail: "Problemas técnicos", evidence: [], service_hints: [] }],
    confidence: { value: 88, level: "high", components: {}, missing: [] },
    service_scores: [{ key: "website", label: "Novo site", value: 91, need: 90, commercial_context: 92, signals: [] }],
    competitive: null,
    commercial_structure: { value: 70, level: "high", confidence: 80, components: {}, signals: [] },
    timing: { value: 64, level: "medium", signals: [], latest_event_at: null },
  },
  source: "manual",
  next_action: "Enviar proposta",
  next_action_on: "2026-09-30",
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
  enrichment: { fields: { email: { value: "ana@acme.test", source: "site", confidence: 90, checked_at: 1 } } },
  enrichment_analyzed_at: null,
  created_at: 1,
} satisfies Lead;

const sale = {
  id: "s1",
  lead_id: "l1",
  campaign_id: null,
  campaign_name: "",
  company: "Acme",
  contact: "Ana",
  phone: "81999999999",
  service: "Site",
  amount_cents: 500000,
  currency: "BRL",
  received_cents: 200000,
  recurring_cents: 30000,
  project_status: "progress",
  sold_on: "2026-09-01",
  due_on: "2026-10-01",
  demo: false,
  payments: [{ id: "p1", amount_cents: 200000, paid_on: "2026-09-02", export_id: "exp1", currency: "BRL" }],
} satisfies Sale;

describe("ORLIQ bridge", () => {
  it("gera pacote financeiro para DashLIQ com recebível restante", () => {
    const result = buildBridgePackage({
      user,
      leads: [lead],
      sales: [sale],
      options: { profile: "dashliq_finance", scopes: ["finance"], includeContacts: false },
      generatedAt: "2026-09-28T22:00:00.000Z",
    }) as any;
    expect(result.schema).toBe("orliq.bridge");
    expect(result.target.product).toBe("DashLIQ");
    expect(result.data.receivables[0].outstanding_cents).toBe(300000);
    expect(result.data.sales[0].contact).toBeNull();
  });

  it("não exporta notas internas e respeita opt-out de contatos", () => {
    const result = buildBridgePackage({
      user,
      leads: [lead],
      sales: [sale],
      options: { profile: "workspace", scopes: ["commercial"], includeContacts: false },
      generatedAt: "2026-09-28T22:00:00.000Z",
    }) as any;
    const text = JSON.stringify(result);
    expect(text).not.toContain("não exportar");
    expect(result.data.leads[0].contact).toBeNull();
    expect(result.data.sales).toHaveLength(0);
  });

  it("usa extensão identificável do ecossistema", () => {
    expect(bridgeFilename("workspace", new Date("2026-09-28T12:00:00Z"))).toBe(
      "scoutliq-orliq-bridge-2026-09-28.orliq.json",
    );
  });
});
