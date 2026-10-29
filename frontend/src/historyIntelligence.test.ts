import { describe, expect, it } from "vitest";
import type { Lead, LeadActivity } from "./types";
import { buildClosedHistoryRecord, buildHistoryIntelligence } from "./historyIntelligence";

function lead(overrides: Partial<Lead> = {}): Lead {
  return {
    id: "lead-1",
    name: "Empresa",
    category: "Serviços",
    city: "Recife",
    country: "BR",
    address: "",
    latitude: 0,
    longitude: 0,
    rating: 4.5,
    reviews: 30,
    website: "",
    website_status: "none",
    instagram: "",
    instagram_active: false,
    phone: "",
    whatsapp: "",
    contact: "",
    potential_cents: 0,
    potential_currency: "BRL",
    notes: "",
    stage: "won",
    in_pipeline: true,
    demo: false,
    version: 1,
    score: {} as Lead["score"],
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

function activity(kind: LeadActivity["kind"], at: number, metadata = {}): LeadActivity {
  return { id: `${kind}-${at}`, lead_id: "lead-1", kind, body: "", metadata, created_at: at };
}

describe("history intelligence", () => {
  it("derives cadence and behavior before a won outcome", () => {
    const record = buildClosedHistoryRecord(lead(), [
      activity("pipeline_added", 1_000_000),
      activity("whatsapp", 1_043_200),
      activity("reply", 1_086_400),
      activity("whatsapp", 1_129_600),
      activity("proposal", 1_172_800),
      activity("sale_won", 1_259_200),
    ]);
    expect(record?.firstContactDays).toBe(0.5);
    expect(record?.cycleDays).toBe(3);
    expect(record?.followUps).toBe(1);
    expect(record?.hasProposal).toBe(true);
    expect(record?.hasReply).toBe(true);
  });

  it("remembers the stage immediately before a loss", () => {
    const record = buildClosedHistoryRecord(
      lead({ stage: "lost" }),
      [
        activity("pipeline_added", 1_000_000),
        activity("stage_changed", 1_086_400, { from: "contacted", to: "replied" }),
        activity("stage_changed", 1_172_800, { from: "replied", to: "lost" }),
      ],
    );
    expect(record?.lossFromStage).toBe("replied");
    expect(record?.cycleDays).toBe(2);
  });

  it("only marks comparative patterns ready with enough wins and losses", () => {
    const leads = [
      lead({ id: "w1" }), lead({ id: "w2" }), lead({ id: "w3" }),
      lead({ id: "l1", stage: "lost" }), lead({ id: "l2", stage: "lost" }), lead({ id: "l3", stage: "lost" }),
    ];
    const activities = Object.fromEntries(
      leads.map((item) => [
        item.id,
        [
          { ...activity("pipeline_added", 1_000_000), lead_id: item.id },
          { ...activity("email", 1_010_000), lead_id: item.id },
          ...(item.stage === "won" ? [{ ...activity("proposal", 1_020_000), lead_id: item.id }] : []),
          item.stage === "won"
            ? { ...activity("sale_won", 1_100_000), lead_id: item.id }
            : { ...activity("stage_changed", 1_100_000, { from: "contacted", to: "lost" }), lead_id: item.id },
        ],
      ]),
    );
    const result = buildHistoryIntelligence(leads, activities);
    expect(result.ready).toBe(true);
    expect(result.patterns.find((item) => item.key === "proposal")?.deltaPp).toBe(100);
    expect(result.lossStages[0]).toMatchObject({ stage: "contacted", count: 3, share: 100 });
  });
});
