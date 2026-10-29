import type { Currency, Lead, Sale, Stage, User } from "./types";

export const BRIDGE_SCHEMA = "orliq.bridge" as const;
export const BRIDGE_SCHEMA_VERSION = 1 as const;
export const SCOUTLIQ_BRIDGE_VERSION = "1.38.7-dev";

export type BridgeProfile = "workspace" | "dashliq_finance";
export type BridgeScope = "commercial" | "delivery" | "finance";

export type BridgeOptions = {
  profile: BridgeProfile;
  scopes: BridgeScope[];
  includeContacts: boolean;
};

type MoneyBucket = Partial<Record<Currency, number>>;

function compact<T extends Record<string, unknown>>(value: T) {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== "" && item !== null && item !== undefined),
  ) as Partial<T>;
}

function bestService(lead: Lead) {
  return [...(lead.score.service_scores || [])].sort((a, b) => b.value - a.value)[0] ?? null;
}

function primaryDiagnosis(lead: Lead) {
  return [...(lead.score.diagnosis || [])].sort((a, b) => {
    const weight = { high: 3, medium: 2, low: 1 } as const;
    return weight[b.severity] - weight[a.severity];
  })[0] ?? null;
}

function contactPayload(lead: Lead, includeContacts: boolean) {
  if (!includeContacts) return undefined;
  const enrichment = lead.enrichment?.fields || {};
  const email = enrichment.email?.value || "";
  return compact({
    name: lead.contact,
    phone: lead.phone,
    whatsapp: lead.whatsapp,
    instagram: lead.instagram,
    email,
  });
}

function serializeLead(lead: Lead, includeContacts: boolean) {
  const service = bestService(lead);
  const diagnosis = primaryDiagnosis(lead);
  return {
    id: lead.id,
    name: lead.name,
    category: lead.category,
    city: lead.city,
    country: lead.country,
    stage: lead.stage,
    in_pipeline: lead.in_pipeline,
    source: lead.source,
    website: lead.website || null,
    website_status: lead.website_status,
    opportunity_score: lead.score.value,
    confidence: lead.score.confidence?.value ?? null,
    timing: lead.score.timing?.value ?? null,
    potential_cents: lead.potential_cents,
    potential_currency: lead.potential_currency,
    next_action: lead.next_action || null,
    next_action_on: lead.next_action_on,
    last_contact_at: lead.last_contact_at,
    best_service: service
      ? { key: service.key, label: service.label, score: service.value }
      : null,
    primary_diagnosis: diagnosis
      ? {
          key: diagnosis.key,
          area: diagnosis.area,
          severity: diagnosis.severity,
          title: diagnosis.title,
          detail: diagnosis.detail,
        }
      : null,
    contact: contactPayload(lead, includeContacts) ?? null,
  };
}

function serializeSale(sale: Sale, includeContacts: boolean) {
  return {
    id: sale.id,
    lead_id: sale.lead_id,
    company: sale.company,
    service: sale.service,
    project_status: sale.project_status,
    sold_on: sale.sold_on,
    due_on: sale.due_on,
    currency: sale.currency,
    amount_cents: sale.amount_cents,
    received_cents: sale.received_cents,
    outstanding_cents: Math.max(0, sale.amount_cents - sale.received_cents),
    recurring_cents: sale.recurring_cents,
    campaign_id: sale.campaign_id,
    campaign_name: sale.campaign_name || null,
    contact: includeContacts
      ? compact({ name: sale.contact, phone: sale.phone })
      : null,
    payments: sale.payments.map((payment) => ({
      id: payment.id,
      export_id: payment.export_id,
      amount_cents: payment.amount_cents,
      currency: payment.currency,
      paid_on: payment.paid_on,
    })),
  };
}

function addMoney(bucket: MoneyBucket, currency: Currency, cents: number) {
  bucket[currency] = (bucket[currency] || 0) + cents;
}

function summarize(leads: Lead[], sales: Sale[]) {
  const pipelineByStage = {} as Partial<Record<Stage, number>>;
  const receivableByCurrency: MoneyBucket = {};
  const recurringByCurrency: MoneyBucket = {};
  const receivedByCurrency: MoneyBucket = {};

  for (const lead of leads) {
    pipelineByStage[lead.stage] = (pipelineByStage[lead.stage] || 0) + 1;
  }
  for (const sale of sales) {
    addMoney(
      receivableByCurrency,
      sale.currency,
      Math.max(0, sale.amount_cents - sale.received_cents),
    );
    addMoney(recurringByCurrency, sale.currency, sale.recurring_cents);
    addMoney(receivedByCurrency, sale.currency, sale.received_cents);
  }

  return {
    leads: leads.length,
    sales: sales.length,
    pipeline_by_stage: pipelineByStage,
    receivable_by_currency: receivableByCurrency,
    recurring_by_currency: recurringByCurrency,
    received_by_currency: receivedByCurrency,
  };
}

export function buildBridgePackage({
  user,
  leads,
  sales,
  options,
  generatedAt = new Date().toISOString(),
}: {
  user: User;
  leads: Lead[];
  sales: Sale[];
  options: BridgeOptions;
  generatedAt?: string;
}) {
  const scope = new Set(options.scopes);
  const commercialLeads = leads.filter(
    (lead) => lead.in_pipeline || lead.stage === "won" || lead.stage === "lost",
  );
  const visibleLeads = scope.has("commercial") ? commercialLeads : [];
  const visibleSales = scope.has("delivery") || scope.has("finance") ? sales : [];

  if (options.profile === "dashliq_finance") {
    const financeSales = sales.map((sale) => serializeSale(sale, options.includeContacts));
    return {
      schema: BRIDGE_SCHEMA,
      schema_version: BRIDGE_SCHEMA_VERSION,
      producer: { product: "ScoutLIQ", version: SCOUTLIQ_BRIDGE_VERSION },
      target: { product: "DashLIQ", profile: "finance" },
      generated_at: generatedAt,
      workspace: {
        id: user.id,
        locale: user.locale,
        timezone: user.timezone,
        default_currency: user.default_currency,
      },
      summary: summarize([], sales),
      data: {
        receivables: financeSales.filter((sale) => sale.outstanding_cents > 0),
        sales: financeSales,
      },
    };
  }

  return {
    schema: BRIDGE_SCHEMA,
    schema_version: BRIDGE_SCHEMA_VERSION,
    producer: { product: "ScoutLIQ", version: SCOUTLIQ_BRIDGE_VERSION },
    target: { product: "ORLIQ Ecosystem", profile: "workspace" },
    generated_at: generatedAt,
    workspace: {
      id: user.id,
      name: user.name,
      locale: user.locale,
      timezone: user.timezone,
      default_currency: user.default_currency,
    },
    selection: {
      scopes: options.scopes,
      contacts_included: options.includeContacts,
    },
    summary: summarize(visibleLeads, visibleSales),
    data: {
      leads: visibleLeads.map((lead) => serializeLead(lead, options.includeContacts)),
      sales: visibleSales.map((sale) => serializeSale(sale, options.includeContacts)),
    },
  };
}

export function buildLeadHandoff(lead: Lead, user: User, includeContacts = true) {
  return {
    schema: BRIDGE_SCHEMA,
    schema_version: BRIDGE_SCHEMA_VERSION,
    producer: { product: "ScoutLIQ", version: SCOUTLIQ_BRIDGE_VERSION },
    target: { product: "ORLIQ Ecosystem", profile: "lead_handoff" },
    generated_at: new Date().toISOString(),
    workspace: { id: user.id, timezone: user.timezone, default_currency: user.default_currency },
    data: { lead: serializeLead(lead, includeContacts) },
  };
}

export function bridgeFilename(profile: BridgeProfile, date = new Date()) {
  const day = date.toISOString().slice(0, 10);
  return `scoutliq-${profile === "dashliq_finance" ? "dashliq-finance" : "orliq-bridge"}-${day}.orliq.json`;
}
