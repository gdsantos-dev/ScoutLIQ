import type { Lead, LeadAudit, Score } from "./types";

export type OpportunityPriority = "high" | "medium" | "low";
export type OpportunitySignalTone = "gap" | "strength" | "contact" | "research";

export type OpportunitySignal = {
  key: string;
  label: string;
  detail?: string;
  tone: OpportunitySignalTone;
};

export type OpportunityBrief = {
  priority: OpportunityPriority;
  priorityLabel: string;
  priorityExplanation: string;
  headline: string;
  summary: string;
  signals: OpportunitySignal[];
};

export function getOpportunityPriority(score: number | Score): {
  level: OpportunityPriority;
  label: string;
  explanation: string;
} {
  const scoreValue = typeof score === "number" ? score : score.value;
  if (
    typeof score !== "number" &&
    ["insufficient", "provisional"].includes(score.status || "")
  )
    return {
      level: "low",
      label: "Qualificação provisória",
      explanation:
        "Faltam evidências comerciais. O valor provisório não indica uma empresa ruim.",
    };
  if (typeof score !== "number" && score.status === "incompatible")
    return {
      level: "low",
      label: "Fora do perfil comercial",
      explanation:
        "Há uma exclusão identificada ou bloqueio de contato. Revise os motivos antes de prosseguir.",
    };
  if (scoreValue >= 70) {
    return {
      level: "high",
      label: "Alta prioridade",
      explanation: "Vários sinais objetivos se somam nesta empresa.",
    };
  }
  if (scoreValue >= 40) {
    return {
      level: "medium",
      label: "Prioridade média",
      explanation:
        "Há oportunidade, mas ainda faltam alguns sinais para colocá-la no topo.",
    };
  }
  return {
    level: "low",
    label: "Baixa prioridade",
    explanation: "Poucos sinais objetivos foram confirmados até agora.",
  };
}

function localPresenceSignal(lead: Lead): OpportunitySignal | null {
  const reviews = lead.reviews ?? 0;
  const rating = lead.rating ?? 0;

  if (reviews >= 100 && rating >= 4.5) {
    return {
      key: "local_presence_strong",
      label: "Presença local forte",
      detail: `${rating.toFixed(1)} · ${reviews}`,
      tone: "strength",
    };
  }
  if (reviews >= 100) {
    return {
      key: "review_volume",
      label: "Volume relevante de avaliações",
      detail: `${reviews}`,
      tone: "strength",
    };
  }
  if (rating >= 4.5) {
    return {
      key: "public_rating",
      label: "Avaliação pública forte",
      detail: rating.toFixed(1),
      tone: "strength",
    };
  }
  return null;
}

export function getOpportunityBrief(
  lead: Lead,
  audit: LeadAudit | null = null,
): OpportunityBrief {
  const priority = getOpportunityPriority(lead.score);
  const signals: OpportunitySignal[] = [];
  const localPresence = localPresenceSignal(lead);

  if (lead.website_status === "none") {
    signals.push({
      key: "website_none",
      label: "Sem site confirmado",
      tone: "gap",
    });
  } else if (lead.website_status === "poor") {
    signals.push({
      key: "website_poor",
      label: "Site com problemas confirmados",
      tone: "gap",
    });
  } else if (!lead.website || lead.website_status === "unknown") {
    signals.push({
      key: "website_unknown",
      label: "Site ainda não verificado",
      tone: "research",
    });
  }

  if (audit) {
    const importantFindings = audit.findings.filter(
      (item) => item.severity === "high" || item.severity === "medium",
    );
    if (importantFindings.length) {
      signals.push({
        key: "audit_findings",
        label: "Falhas importantes encontradas no site",
        detail: `${importantFindings.length}`,
        tone: "gap",
      });
    }
  }

  if (localPresence) signals.push(localPresence);

  if (lead.instagram_active) {
    signals.push({
      key: "instagram_active",
      label: "Instagram ativo confirmado",
      tone: "strength",
    });
  } else if (lead.instagram) {
    signals.push({
      key: "instagram_presence",
      label: "Instagram encontrado",
      tone: "strength",
    });
  }

  if (lead.whatsapp) {
    signals.push({
      key: "whatsapp",
      label: "WhatsApp disponível",
      tone: "contact",
    });
  } else if (lead.phone) {
    signals.push({
      key: "phone",
      label: "Telefone disponível",
      tone: "contact",
    });
  }

  let headline = "Oportunidade ainda pouco qualificada";
  let summary =
    "Os dados atuais ainda são insuficientes para colocar esta empresa entre as primeiras abordagens.";

  if (lead.website_status === "none" && localPresence) {
    headline = "Presença local sem site confirmado";
    summary =
      "A empresa já tem sinais públicos de presença local, mas não possui site confirmado nos dados verificados.";
  } else if (lead.website_status === "none") {
    headline = "Empresa sem site confirmado";
    summary =
      "A ausência de site confirmado cria uma oportunidade clara, mas vale validar presença e contato antes da abordagem.";
  } else if (
    lead.website_status === "poor" ||
    (audit && audit.findings.some((item) => item.severity === "high"))
  ) {
    headline = "Site atual abre espaço para melhoria";
    summary =
      "Há problemas concretos no site atual que podem sustentar uma abordagem comercial específica.";
  } else if (lead.score.value >= 40) {
    headline = "Há sinais concretos para abordagem";
    summary =
      "Os dados disponíveis combinam presença pública, contato ou necessidade digital suficiente para justificar prospecção.";
  } else if (lead.website_status === "unknown") {
    headline = "Site ainda precisa ser verificado";
    summary =
      "Antes de priorizar esta empresa, confirme a presença digital e os canais de contato disponíveis.";
  }

  if (
    ["insufficient", "provisional", "incompatible"].includes(
      lead.score.status || "",
    )
  ) {
    headline = priority.label;
    summary = priority.explanation;
  }
  return {
    priority: priority.level,
    priorityLabel: priority.label,
    priorityExplanation: priority.explanation,
    headline,
    summary,
    signals: signals.slice(0, 5),
  };
}
