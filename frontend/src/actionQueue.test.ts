import { expect, it } from "vitest";
import { buildActionQueue } from "./actionQueue";
import type { Lead } from "./types";

function lead(overrides: Partial<Lead> = {}): Lead {
  return {
    id: "lead-1",
    name: "Acme",
    category: "Restaurante",
    city: "Recife",
    country: "BR",
    address: "",
    latitude: 0,
    longitude: 0,
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
    in_pipeline: true,
    demo: false,
    version: 1,
    score: { value: 70 } as Lead["score"],
    source: "manual",
    next_action: "",
    next_action_on: null,
    pipeline_added_at: 1_000_000,
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
    created_at: 1_000_000,
    ...overrides,
  };
}

const now = Math.floor(Date.parse("2026-09-28T15:00:00Z") / 1000);

it("prioritizes overdue explicit actions before today and upcoming", () => {
  const items = buildActionQueue(
    [
      lead({ id: "future", next_action: "Enviar proposta", next_action_on: "2026-09-30" }),
      lead({ id: "today", next_action: "Ligar", next_action_on: "2026-09-28" }),
      lead({ id: "late", next_action: "Retornar", next_action_on: "2026-09-26" }),
    ],
    "2026-09-28",
    now,
  );
  expect(items.map((item) => item.lead.id)).toEqual(["late", "today", "future"]);
});

it("creates a first-contact task from an aging pipeline lead without backend state", () => {
  const items = buildActionQueue(
    [lead({ pipeline_added_at: now - 3 * 86_400, created_at: now - 3 * 86_400 })],
    "2026-09-28",
    now,
  );
  expect(items[0]?.source).toBe("first_contact");
  expect(items[0]?.action).toBe("Fazer primeiro contato");
});

it("does not surface won or lost leads", () => {
  const items = buildActionQueue(
    [lead({ stage: "won" }), lead({ id: "lost", stage: "lost" })],
    "2026-09-28",
    now,
  );
  expect(items).toEqual([]);
});
