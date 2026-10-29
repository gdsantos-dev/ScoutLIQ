import type { Lead } from "./types";

export type OutreachChannel = "whatsapp" | "email";

export type OutreachTemplate = {
  id: string;
  name: string;
  channel: OutreachChannel;
  subject: string;
  body: string;
  builtin?: boolean;
};

export type OutreachContext = {
  empresa: string;
  contato: string;
  saudacao_contato: string;
  cidade: string;
  categoria: string;
  site: string;
  score: string;
  servico: string;
  oportunidade: string;
  proxima_acao: string;
};

export const OUTREACH_STORAGE_KEY = "scoutliq.outreach.templates.v1";

export const OUTREACH_VARIABLES: { key: keyof OutreachContext; label: string }[] = [
  { key: "empresa", label: "Empresa" },
  { key: "contato", label: "Contato" },
  { key: "saudacao_contato", label: "Saudação" },
  { key: "cidade", label: "Cidade" },
  { key: "categoria", label: "Categoria" },
  { key: "site", label: "Site" },
  { key: "score", label: "Opportunity Score" },
  { key: "servico", label: "Serviço com maior fit" },
  { key: "oportunidade", label: "Principal oportunidade" },
  { key: "proxima_acao", label: "Próxima ação" },
];

export const DEFAULT_OUTREACH_TEMPLATES: OutreachTemplate[] = [
  {
    id: "builtin-whatsapp-first-contact",
    name: "Primeiro contato · WhatsApp",
    channel: "whatsapp",
    subject: "",
    body:
      "{{saudacao_contato}}! Encontrei a {{empresa}} em {{cidade}} e notei {{oportunidade}}. Trabalho com soluções digitais para negócios de {{categoria}}. Posso te mostrar de forma objetiva o que eu ajustaria?",
    builtin: true,
  },
  {
    id: "builtin-whatsapp-follow-up",
    name: "Retomar contato · WhatsApp",
    channel: "whatsapp",
    subject: "",
    body:
      "{{saudacao_contato}}! Passando para retomar nosso contato sobre a {{empresa}}. O ponto que mais chamou atenção foi {{oportunidade}}. Se fizer sentido, consigo te explicar a ideia sem compromisso e de forma bem rápida.",
    builtin: true,
  },
  {
    id: "builtin-email-first-contact",
    name: "Primeiro contato · E-mail",
    channel: "email",
    subject: "Uma ideia para a {{empresa}}",
    body:
      "{{saudacao_contato}},\n\nEncontrei a {{empresa}} em {{cidade}} e, analisando a presença digital, notei {{oportunidade}}. Pelo perfil do negócio, {{servico}} aparece como uma frente com bom encaixe.\n\nSe fizer sentido, posso te enviar uma visão objetiva do que eu ajustaria e por quê.\n\nAbraço,",
    builtin: true,
  },
  {
    id: "builtin-email-follow-up",
    name: "Follow-up · E-mail",
    channel: "email",
    subject: "Retomando o contato sobre a {{empresa}}",
    body:
      "{{saudacao_contato}},\n\nQueria retomar o contato sobre a {{empresa}}. O principal ponto que identifiquei continua sendo {{oportunidade}}.\n\nSe isso estiver no radar de vocês, posso organizar a sugestão em poucos tópicos e te mandar por aqui.\n\nAbraço,",
    builtin: true,
  },
];

function enrichmentValue(lead: Lead, ...keys: string[]) {
  const fields = lead.enrichment?.fields || {};
  for (const key of keys) {
    const value = fields[key]?.value?.trim();
    if (value) return value;
  }
  return "";
}

function contactName(lead: Lead) {
  return (
    lead.contact?.trim() ||
    enrichmentValue(lead, "contact_name", "contact", "owner", "owner_name")
  );
}

function bestService(lead: Lead) {
  const services = [...(lead.score.service_scores || [])].sort(
    (a, b) => b.value - a.value,
  );
  return services[0]?.label || "uma melhoria na presença digital";
}

function opportunity(lead: Lead) {
  const diagnosis = [...(lead.score.diagnosis || [])].sort((a, b) => {
    const rank = { high: 0, medium: 1, low: 2 };
    return rank[a.severity] - rank[b.severity];
  })[0];
  if (diagnosis?.title) return diagnosis.title.toLocaleLowerCase();

  const combined = lead.score.combined_signals?.find(
    (signal) => signal.strength === "high",
  ) || lead.score.combined_signals?.[0];
  if (combined?.label) return combined.label.toLocaleLowerCase();

  if (lead.website_status === "none") return "que a empresa não possui um site ativo identificado";
  if (lead.website_status === "poor") return "pontos claros de melhoria no site atual";
  if (!lead.website) return "uma oportunidade de fortalecer a presença digital";
  return "uma oportunidade de melhorar a experiência digital atual";
}

export function buildOutreachContext(lead: Lead): OutreachContext {
  const contact = contactName(lead);
  return {
    empresa: lead.name || "a empresa",
    contato: contact,
    saudacao_contato: contact ? `Olá, ${contact}` : "Olá",
    cidade: lead.city || "sua região",
    categoria: lead.category || "seu segmento",
    site: lead.website || "",
    score: String(lead.score.value ?? ""),
    servico: bestService(lead),
    oportunidade: opportunity(lead),
    proxima_acao: lead.next_action || "",
  };
}

const variablePattern = /{{\s*([a-z_]+)\s*}}/gi;

export function renderOutreachText(text: string, context: OutreachContext) {
  return text
    .replace(variablePattern, (_match, rawKey: string) => {
      const key = rawKey.toLocaleLowerCase() as keyof OutreachContext;
      return key in context ? context[key] : "";
    })
    .replace(/[ \t]+\n/g, "\n")
    .replace(/ {2,}/g, " ")
    .trim();
}

export function renderOutreachTemplate(template: OutreachTemplate, lead: Lead) {
  const context = buildOutreachContext(lead);
  return {
    subject: renderOutreachText(template.subject, context),
    body: renderOutreachText(template.body, context),
  };
}

function validTemplate(value: unknown): value is OutreachTemplate {
  if (!value || typeof value !== "object") return false;
  const template = value as Partial<OutreachTemplate>;
  return Boolean(
    template.id &&
      template.name &&
      (template.channel === "whatsapp" || template.channel === "email") &&
      typeof template.subject === "string" &&
      typeof template.body === "string",
  );
}

export function parseStoredTemplates(raw: string | null): OutreachTemplate[] {
  if (!raw) return DEFAULT_OUTREACH_TEMPLATES.map((template) => ({ ...template }));
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) throw new Error("Invalid template list");
    const templates = parsed.filter(validTemplate);
    return templates.length
      ? templates
      : DEFAULT_OUTREACH_TEMPLATES.map((template) => ({ ...template }));
  } catch {
    return DEFAULT_OUTREACH_TEMPLATES.map((template) => ({ ...template }));
  }
}

export function whatsappUrl(phone: string, body: string) {
  const number = phone.replace(/\D/g, "");
  if (!number) return "";
  return `https://wa.me/${number}?text=${encodeURIComponent(body)}`;
}

export function emailUrl(email: string, subject: string, body: string) {
  if (!email.trim()) return "";
  const query = new URLSearchParams();
  if (subject) query.set("subject", subject);
  if (body) query.set("body", body);
  return `mailto:${email.trim()}${query.size ? `?${query.toString()}` : ""}`;
}
