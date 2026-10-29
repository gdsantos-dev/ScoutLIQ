import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  CalendarClock,
  Check,
  Clock3,
  Mail,
  MessageCircle,
  Phone,
  Search,
} from "lucide-react";
import { api } from "../api";
import { buildActionQueue } from "../actionQueue";
import type { ActionQueueBucket, ActionQueueItem, ActionQueueReason } from "../actionQueue";
import OutreachComposer, { OutreachTemplateManager } from "../components/OutreachComposer";
import { Empty, PageHead } from "../components/UI";
import { tr } from "../i18n";
import { normalizeSearch } from "../search";
import { parseStoredTemplates } from "../outreach";
import type { OutreachTemplate } from "../outreach";
import type { Lead, LeadActivityCreateResponse, LeadActivityKind } from "../types";
import { activeLocale, dateLabel, inputDate, money, stageLabel } from "../types";

const buckets: { id: ActionQueueBucket; label: string }[] = [
  { id: "today", label: "Hoje" },
  { id: "overdue", label: "Atrasadas" },
  { id: "upcoming", label: "Próximas" },
];

function digits(value: string) {
  return value.replace(/\D/g, "");
}

function leadEmail(lead: Lead) {
  const fields = lead.enrichment?.fields || {};
  return fields.email?.value || fields.contact_email?.value || "";
}

function dueLabel(item: ActionQueueItem) {
  if (item.bucket === "overdue" && item.dueOn)
    return `${tr("Vencida")} ${dateLabel(item.dueOn)}`;
  if (item.bucket === "today") return tr("Hoje");
  if (item.dueOn) return dateLabel(item.dueOn);
  return tr("Sem data");
}

function reasonLabel(reason: ActionQueueReason) {
  if (reason.kind === "overdue")
    return `${tr("Atrasada há")} ${reason.days} ${tr(reason.days === 1 ? "dia" : "dias")}`;
  if (reason.kind === "today") return tr("Vence hoje");
  if (reason.kind === "upcoming")
    return `${tr("Prevista em")} ${reason.days} ${tr(reason.days === 1 ? "dia" : "dias")}`;
  if (reason.kind === "undated") return tr("Próxima ação sem data");
  if (reason.kind === "first_contact")
    return `${tr("Sem primeiro contato há")} ${reason.days} ${tr(reason.days === 1 ? "dia" : "dias")}`;
  if (reason.kind === "stale")
    return `${tr("Sem contato há")} ${reason.days} ${tr(reason.days === 1 ? "dia" : "dias")}`;
  if (reason.kind === "stage") return `${tr("Etapa")}: ${stageLabel(reason.stage)}`;
  return `Score ${reason.value}`;
}

export default function Actions({
  leads,
  timezone,
  onSelect,
  onLeadUpdated,
  onNotice,
  storageKey,
}: {
  leads: Lead[];
  timezone: string;
  onSelect: (lead: Lead) => void;
  onLeadUpdated: (lead: Lead) => void;
  onNotice: (message: string) => void;
  storageKey: string;
}) {
  const today = inputDate(timezone);
  const queue = useMemo(() => buildActionQueue(leads, today), [leads, today]);
  const [bucket, setBucket] = useState<ActionQueueBucket>("today");
  const [query, setQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [dates, setDates] = useState<Record<string, string>>({});
  const [composerId, setComposerId] = useState<string | null>(null);
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [templates, setTemplates] = useState<OutreachTemplate[]>(() =>
    parseStoredTemplates(typeof localStorage === "undefined" ? null : localStorage.getItem(storageKey)),
  );

  useEffect(() => {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(storageKey, JSON.stringify(templates));
  }, [storageKey, templates]);

  const counts = useMemo(
    () =>
      buckets.reduce<Record<ActionQueueBucket, number>>(
        (result, item) => {
          result[item.id] = queue.filter((entry) => entry.bucket === item.id).length;
          return result;
        },
        { today: 0, overdue: 0, upcoming: 0 },
      ),
    [queue],
  );

  const items = useMemo(() => {
    const needle = normalizeSearch(query);
    return queue.filter(
      (item) =>
        item.bucket === bucket &&
        (!needle ||
          normalizeSearch(
            `${item.lead.name} ${item.lead.city} ${item.lead.category} ${item.action} ${item.reasons.map(reasonLabel).join(" ")}`,
          ).includes(needle)),
    );
  }, [bucket, query, queue]);

  async function register(item: ActionQueueItem, kind: LeadActivityKind, body = "") {
    if (busyId) return;
    setBusyId(item.lead.id);
    setError("");
    try {
      const result = await api<LeadActivityCreateResponse>(
        `/leads/${item.lead.id}/activities`,
        "POST",
        { kind, body },
      );
      onLeadUpdated(result.lead);
      onNotice("Contato registrado.");
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  async function reschedule(item: ActionQueueItem) {
    const dueOn = dates[item.lead.id];
    if (!dueOn || busyId) return;
    setBusyId(item.lead.id);
    setError("");
    try {
      const updated = await api<Lead>(
        `/leads/${item.lead.id}/next-action`,
        "PATCH",
        {
          next_action: item.lead.next_action || item.action,
          next_action_on: dueOn,
          version: item.lead.version,
        },
      );
      onLeadUpdated(updated);
      onNotice("Próxima ação remarcada.");
      setDates((current) => ({ ...current, [item.lead.id]: "" }));
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  async function complete(item: ActionQueueItem) {
    if (item.source !== "explicit" || busyId) return;
    setBusyId(item.lead.id);
    setError("");
    try {
      const updated = await api<Lead>(
        `/leads/${item.lead.id}/next-action`,
        "PATCH",
        {
          next_action: "",
          next_action_on: null,
          version: item.lead.version,
        },
      );
      onLeadUpdated(updated);
      onNotice("Pendência concluída.");
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="actions-workspace">
      <PageHead title={tr("Ações")}>
        <button className="button compact" onClick={() => setTemplatesOpen(true)}>
          {tr("Templates")}
        </button>
      </PageHead>

      <section className="action-brief" aria-label={tr("Resumo da fila")}> 
        <div>
          <span>{tr("Agora")}</span>
          <strong>{counts.overdue + counts.today}</strong>
          <small>{tr("ações pedindo atenção")}</small>
        </div>
        <div>
          <span>{tr("Atrasadas")}</span>
          <strong>{counts.overdue}</strong>
          <small>{tr("resolver primeiro")}</small>
        </div>
        <div>
          <span>{tr("Hoje")}</span>
          <strong>{counts.today}</strong>
          <small>{tr("previstas para hoje")}</small>
        </div>
      </section>

      <div className="action-tabs" role="tablist" aria-label={tr("Fila de ações")}>
        {buckets.map((item) => (
          <button
            key={item.id}
            role="tab"
            aria-selected={bucket === item.id}
            onClick={() => setBucket(item.id)}
          >
            {tr(item.label)}
            <span>{counts[item.id]}</span>
          </button>
        ))}
      </div>

      <div className="action-tools">
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label={tr("Buscar na fila")}
            placeholder={tr("Empresa, cidade ou ação…")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <span>{items.length} {tr(items.length === 1 ? "ação" : "ações")}</span>
      </div>

      {error && <div className="action-error" role="alert">{error}</div>}

      <div className="action-list">
        {items.length ? (
          items.map((item) => {
            const lead = item.lead;
            const whatsapp = digits(lead.whatsapp || lead.phone);
            const phone = lead.phone || lead.whatsapp;
            const email = leadEmail(lead);
            const expanded = expandedId === lead.id;
            const busy = busyId === lead.id;
            return (
              <article className="action-row" key={`${lead.id}-${item.source}-${item.dueOn || "generated"}`}>
                <button className="action-main" onClick={() => onSelect(lead)}>
                  <span className={`action-due action-due-${item.bucket}`}>
                    {item.bucket === "overdue" ? <Clock3 size={16} /> : <CalendarClock size={16} />}
                    {dueLabel(item)}
                  </span>
                  <span className="action-company">
                    <strong>{lead.name}</strong>
                    <small>{lead.category} · {lead.city}</small>
                  </span>
                  <span className="action-name">{tr(item.action)}</span>
                  <span className="action-reasons">
                    {item.reasons.map((reason, index) => <small key={`${reason.kind}-${index}`}>{reasonLabel(reason)}</small>)}
                  </span>
                </button>
                <div className="action-value">
                  <span>{stageLabel(lead.stage)}</span>
                  <b>{lead.potential_cents ? money(lead.potential_cents, lead.potential_currency) : "—"}</b>
                </div>
                <div className="action-row-controls">
                  {whatsapp && (
                    <a
                      className="icon-button"
                      href={`https://wa.me/${whatsapp}`}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={`${tr("Abrir WhatsApp")} · ${lead.name}`}
                    >
                      <MessageCircle size={17} />
                    </a>
                  )}
                  {phone && (
                    <a className="icon-button" href={`tel:${phone}`} aria-label={`${tr("Ligar")} · ${lead.name}`}>
                      <Phone size={17} />
                    </a>
                  )}
                  {email && (
                    <a className="icon-button" href={`mailto:${email}`} aria-label={`${tr("Enviar e-mail")} · ${lead.name}`}>
                      <Mail size={17} />
                    </a>
                  )}
                  <button
                    className="button compact"
                    aria-expanded={expanded}
                    onClick={() => setExpandedId(expanded ? null : lead.id)}
                  >
                    {tr(expanded ? "Fechar" : "Agir")}
                  </button>
                  <button className="icon-button" aria-label={`${tr("Abrir contexto")} · ${lead.name}`} onClick={() => onSelect(lead)}>
                    <ArrowUpRight size={17} />
                  </button>
                </div>

                {expanded && (
                  <div className="action-drawer">
                    <div className="action-register">
                      <span>{tr("Registrar contato")}</span>
                      <div>
                        <button disabled={busy} onClick={() => void register(item, "whatsapp")}>{tr("WhatsApp")}</button>
                        <button disabled={busy} onClick={() => void register(item, "call")}>{tr("Ligação")}</button>
                        <button disabled={busy} onClick={() => void register(item, "email")}>{tr("E-mail")}</button>
                        <button disabled={busy} onClick={() => void register(item, "meeting")}>{tr("Reunião")}</button>
                        <button disabled={busy} onClick={() => void register(item, "proposal")}>{tr("Proposta")}</button>
                        <button disabled={busy} onClick={() => void register(item, "reply")}>{tr("Resposta")}</button>
                      </div>
                    </div>
                    <div className="action-reschedule">
                      <label>
                        <span>{tr("Remarcar")}</span>
                        <input
                          type="date"
                          min={today}
                          value={dates[lead.id] || ""}
                          onChange={(event) => setDates((current) => ({ ...current, [lead.id]: event.target.value }))}
                        />
                      </label>
                      <button className="button" disabled={busy || !dates[lead.id]} onClick={() => void reschedule(item)}>
                        {tr("Salvar data")}
                      </button>
                    </div>
                    {item.source === "explicit" && (
                      <button className="button action-complete" disabled={busy} onClick={() => void complete(item)}>
                        <Check size={16} />
                        {tr("Concluir pendência")}
                      </button>
                    )}
                    <button
                      type="button"
                      className="button outreach-toggle"
                      aria-expanded={composerId === lead.id}
                      onClick={() => setComposerId(composerId === lead.id ? null : lead.id)}
                    >
                      <MessageCircle size={16} />
                      {tr(composerId === lead.id ? "Fechar mensagem" : "Preparar mensagem")}
                    </button>
                    {composerId === lead.id && (
                      <OutreachComposer
                        lead={lead}
                        phone={whatsapp || digits(phone)}
                        email={email}
                        templates={templates}
                        onManageTemplates={() => setTemplatesOpen(true)}
                        onRegister={(kind, body) => register(item, kind, body)}
                        busy={busy}
                        onNotice={onNotice}
                      />
                    )}
                    <small className="action-updated">
                      {lead.last_contact_at
                        ? `${tr("Último contato")}: ${new Date(lead.last_contact_at * 1000).toLocaleDateString(activeLocale(), { day: "2-digit", month: "short" })}`
                        : tr("Nenhum contato registrado")}
                    </small>
                  </div>
                )}
              </article>
            );
          })
        ) : (
          <Empty
            title={tr(bucket === "overdue" ? "Nenhuma ação atrasada" : bucket === "today" ? "Nada pendente para hoje" : "Nenhuma ação futura")}
            action={query ? <button className="button" onClick={() => setQuery("")}>{tr("Limpar busca")}</button> : undefined}
          />
        )}
      </div>

      {templatesOpen && (
        <OutreachTemplateManager
          templates={templates}
          onChange={setTemplates}
          onClose={() => setTemplatesOpen(false)}
        />
      )}
    </div>
  );
}
