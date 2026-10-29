import { tr } from "../i18n";
import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Globe,
  MapPin,
  Pencil,
  Phone,
  Plus,
  Star,
  Trash2,
  X,
  Check,
  MessageCircle,
  Search,
  ShieldCheck,
  AlertCircle,
  CalendarClock,
  LoaderCircle,
  History,
  Bell,
  BellOff,
  Database,
} from "lucide-react";
import type { Environment } from "../navigation";
import type {
  Lead,
  Sale,
  LeadActivity,
  LeadActivityCreateResponse,
  LeadAudit,
  LeadEnrichmentResponse,
  LeadReanalysisResponse,
  LeadResearch,
  LeadResearchResponse,
  Stage,
} from "../types";
import { activeLocale, inputDate, money, stageLabel, stages } from "../types";
import { api } from "../api";
import { ExternalLink } from "./UI";
import { DateField, SmartSelect } from "./Primitives";
import { getOpportunityBrief } from "../opportunity";
import OpportunityWorkflow from "./OpportunityWorkflow";
import { useDialogLifecycle } from "./dialogLifecycle";
import CommercialReview from "./CommercialReview";

export default function ContextPanel({
  environment,
  sales,
  onManage,
  lead,
  onClose,
  onEdit,
  onDelete,
  onSale,
  onMove,
  busy,
  onLeadUpdated,
  timezone,
}: {
  environment: Environment;
  sales: Sale[];
  onManage: () => void;
  lead: Lead;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onSale: () => void;
  onMove: (stage: Stage) => void;
  busy: boolean;
  onLeadUpdated: (lead: Lead) => void;
  timezone: string;
}) {
  const panel = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState("summary");
  const [workflowOpened, setWorkflowOpened] = useState(false);
  const [workflowDirty, setWorkflowDirty] = useState(false);
  function closePanel() {
    if (
      workflowDirty &&
      !window.confirm(
        "Há alterações não salvas na mensagem. Descartar e fechar?",
      )
    )
      return;
    onClose();
  }
  useEffect(() => {
    if (tab === "workflow") setWorkflowOpened(true);
  }, [tab]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (workflowDirty) event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [workflowDirty]);
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const [research, setResearch] = useState<LeadResearch | null>(null);
  const [researchLoading, setResearchLoading] = useState(true);
  const [researchBusy, setResearchBusy] = useState(false);
  const [deepBusy, setDeepBusy] = useState(false);
  const [reanalysisBusy, setReanalysisBusy] = useState(false);
  const [reanalysisMessage, setReanalysisMessage] = useState("");
  const [researchError, setResearchError] = useState("");
  const [nextAction, setNextAction] = useState(lead.next_action || "");
  const [nextActionOn, setNextActionOn] = useState(lead.next_action_on || "");
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [activityKind, setActivityKind] = useState("whatsapp");
  const [activityBody, setActivityBody] = useState("");
  const [activityBusy, setActivityBusy] = useState(false);
  const [activityError, setActivityError] = useState("");
  const [watchBusy, setWatchBusy] = useState(false);
  const [watchError, setWatchError] = useState("");
  const [enrichmentBusy, setEnrichmentBusy] = useState(false);
  const [enrichmentMessage, setEnrichmentMessage] = useState("");

  useEffect(() => {
    setNextAction(lead.next_action || "");
    setNextActionOn(lead.next_action_on || "");
    setActionError("");
  }, [lead.id, lead.next_action, lead.next_action_on]);

  useEffect(() => {
    if (tab !== "relationship") {
      setActivities([]);
      return;
    }
    let alive = true;
    setActivitiesLoading(true);
    setActivityError("");
    api<LeadActivity[]>(`/leads/${lead.id}/activities`)
      .then((items) => {
        if (alive) setActivities(items);
      })
      .catch((error) => {
        if (alive) setActivityError((error as Error).message);
      })
      .finally(() => {
        if (alive) setActivitiesLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [lead.id, lead.in_pipeline, lead.watchlisted, lead.version, tab]);

  useEffect(() => {
    let alive = true;
    if (tab !== "research") return;
    setResearchLoading(true);
    setResearchError("");
    api<{ research: LeadResearch | null }>(`/leads/${lead.id}/research`)
      .then((result) => {
        if (alive) setResearch(result.research);
      })
      .catch((error) => {
        if (alive) {
          setResearch(null);
          setResearchError((error as Error).message);
        }
      })
      .finally(() => {
        if (alive) setResearchLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [lead.id, tab]);

  async function runResearch() {
    if (researchBusy || lead.demo) return;
    setResearchBusy(true);
    setResearchError("");
    try {
      const result = await api<LeadResearchResponse>(
        `/leads/${lead.id}/research`,
        "POST",
        undefined,
        45000,
      );
      setResearch(result.research);
      onLeadUpdated(result.lead);
    } catch (error) {
      setResearchError((error as Error).message);
    } finally {
      setResearchBusy(false);
    }
  }

  async function runDeepAudit() {
    if (deepBusy || lead.demo) return;
    setDeepBusy(true);
    setResearchError("");
    try {
      const result = await api<LeadResearchResponse>(
        `/leads/${lead.id}/research/deep`,
        "POST",
        undefined,
        65000,
      );
      setResearch(result.research);
      onLeadUpdated(result.lead);
    } catch (error) {
      setResearchError((error as Error).message);
    } finally {
      setDeepBusy(false);
    }
  }

  async function runIntelligentReanalysis() {
    if (reanalysisBusy || lead.demo) return;
    setReanalysisBusy(true);
    setResearchError("");
    setReanalysisMessage("");
    try {
      const result = await api<LeadReanalysisResponse>(
        `/leads/${lead.id}/reanalysis`,
        "POST",
        undefined,
        80000,
      );
      setResearch(result.research);
      onLeadUpdated(result.lead);
      if (result.after_confidence > result.before_confidence) {
        setReanalysisMessage(
          `${tr("Confiança atualizada")}: ${result.before_confidence} → ${result.after_confidence}`,
        );
      } else if (result.actions.length) {
        setReanalysisMessage(
          tr("Reanálise concluída com as evidências disponíveis."),
        );
      } else {
        setReanalysisMessage(tr("Os dados recentes já estão atualizados."));
      }
    } catch (error) {
      setResearchError((error as Error).message);
    } finally {
      setReanalysisBusy(false);
    }
  }

  async function runEnrichment() {
    if (enrichmentBusy || lead.demo) return;
    setEnrichmentBusy(true);
    setResearchError("");
    setEnrichmentMessage("");
    try {
      const result = await api<LeadEnrichmentResponse>(
        `/leads/${lead.id}/enrich`,
        "POST",
        undefined,
        70000,
      );
      if (result.research) setResearch(result.research);
      onLeadUpdated(result.lead);
      const coverage = result.enrichment.coverage ?? 0;
      const missing = result.enrichment.missing?.length ?? 0;
      setEnrichmentMessage(
        missing
          ? `${tr("Cobertura dos contatos")}: ${coverage}% · ${missing} ${tr("campos ainda ausentes")}`
          : `${tr("Cobertura dos contatos")}: ${coverage}%`,
      );
    } catch (error) {
      setResearchError((error as Error).message);
    } finally {
      setEnrichmentBusy(false);
    }
  }

  async function toggleWatchlist() {
    if (watchBusy) return;
    setWatchBusy(true);
    setWatchError("");
    try {
      const updated = await api<Lead>(`/leads/${lead.id}/watchlist`, "PATCH", {
        enabled: !lead.watchlisted,
        version: lead.version,
      });
      onLeadUpdated(updated);
    } catch (error) {
      setWatchError((error as Error).message);
    } finally {
      setWatchBusy(false);
    }
  }

  async function addCommercialActivity() {
    if (activityBusy || ["won", "lost"].includes(lead.stage)) return;
    setActivityBusy(true);
    setActivityError("");
    try {
      const result = await api<LeadActivityCreateResponse>(
        `/leads/${lead.id}/activities`,
        "POST",
        {
          kind: activityKind,
          body: activityBody.trim(),
        },
      );
      setActivities((current) => [
        result.activity,
        ...current.filter((item) => item.id !== result.activity.id),
      ]);
      setActivityBody("");
      onLeadUpdated(result.lead);
    } catch (error) {
      setActivityError((error as Error).message);
    } finally {
      setActivityBusy(false);
    }
  }

  function activityTitle(item: LeadActivity) {
    const meta = item.metadata || {};
    if (item.kind === "pipeline_added")
      return tr("Oportunidade salva no Pipeline");
    if (item.kind === "stage_changed") {
      const from =
        typeof meta.from === "string" ? (meta.from as Stage) : "discovered";
      const to =
        typeof meta.to === "string" ? (meta.to as Stage) : "discovered";
      return `${stageLabel(from)} → ${stageLabel(to)}`;
    }
    if (item.kind === "next_action") return tr("Próxima ação definida");
    if (item.kind === "next_action_cleared") return tr("Próxima ação removida");
    if (item.kind === "sale_won") return tr("Venda registrada");
    if (item.kind === "sale_reopened")
      return tr("Venda removida · oportunidade reaberta");
    if (item.kind === "watch_change")
      return tr("Mudança detectada pela Watchlist");
    const labels: Record<string, string> = {
      whatsapp: "WhatsApp",
      call: tr("Ligação"),
      email: "E-mail",
      meeting: tr("Reunião"),
      proposal: tr("Proposta"),
      reply: tr("Resposta"),
      note: tr("Anotação"),
    };
    return labels[item.kind] || item.kind;
  }

  function activityDetail(item: LeadActivity) {
    if (item.body) return item.body;
    if (
      item.kind === "next_action" &&
      typeof item.metadata?.due_on === "string"
    ) {
      return `${tr("Prazo")}: ${item.metadata.due_on}`;
    }
    if (
      item.kind === "sale_won" &&
      typeof item.metadata?.amount_cents === "number"
    ) {
      const currency = item.metadata.currency === "USD" ? "USD" : "BRL";
      return money(item.metadata.amount_cents, currency);
    }
    return "";
  }

  async function updateNextAction(action: string, dueOn: string) {
    if (actionBusy) return;
    setActionBusy(true);
    setActionError("");
    try {
      const normalized = action.trim();
      const updated = await api<Lead>(
        `/leads/${lead.id}/next-action`,
        "PATCH",
        {
          next_action: normalized,
          next_action_on: normalized && dueOn ? dueOn : null,
          version: lead.version,
        },
      );
      setNextAction(updated.next_action || "");
      setNextActionOn(updated.next_action_on || "");
      onLeadUpdated(updated);
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setActionBusy(false);
    }
  }

  const evidenceLabels: Record<string, string> = {
    name_match: tr("Nome comercial corresponde"),
    name_partial: tr("Nome parcialmente correspondente"),
    domain_match: tr("Domínio compatível com a marca"),
    city_match: tr("Cidade corresponde"),
    phone_match: tr("Telefone corresponde"),
    address_match: tr("Endereço corresponde"),
    instagram_match: tr("Instagram vinculado"),
    search_result: tr("Resultado encontrado na web"),
  };
  const checkLabels: Record<string, string> = {
    context_services: tr("Links de serviços ou cardápio"),
    context_contact: tr("Contato público ou formulário"),
    context_booking: tr("Sinal de agendamento"),
    https: "HTTPS",
    viewport: tr("Viewport responsivo"),
    title: tr("Título da página"),
    description: tr("Descrição da página"),
    schema: tr("Dados estruturados"),
    contact: tr("Contato no site"),
    speed: tr("Resposta do site"),
  };
  const auditCategoryLabels: Record<string, string> = {
    technical: tr("Técnico"),
    discoverability: tr("Descoberta"),
    conversion: tr("Conversão"),
    accessibility: tr("Acessibilidade"),
  };
  const auditFindingLabels: Record<string, string> = {
    no_https: tr("Site sem HTTPS"),
    no_viewport: tr("Viewport responsivo ausente"),
    slow_response: tr("Resposta lenta"),
    heavy_html: tr("HTML muito pesado"),
    mixed_content: tr("Conteúdo inseguro em página HTTPS"),
    no_canonical: tr("URL canônica não encontrada"),
    no_favicon: tr("Favicon não encontrado"),
    free_host_domain: tr("Site usa subdomínio de plataforma"),
    weak_title: tr("Título da página ausente ou inadequado"),
    no_description: tr("Meta description fraca ou ausente"),
    no_schema: tr("Dados estruturados não encontrados"),
    no_h1: tr("H1 principal não encontrado"),
    multiple_h1: tr("Mais de um H1 encontrado"),
    no_lang: tr("Idioma da página não declarado"),
    no_phone: tr("Telefone não encontrado no site"),
    no_whatsapp: tr("WhatsApp não encontrado no site"),
    no_email: tr("E-mail não encontrado no site"),
    no_form: tr("Formulário de contato não encontrado"),
    few_ctas: tr("Poucas ações comerciais claras"),
    no_cta: tr("Nenhuma ação comercial clara detectada"),
    no_contact_page: tr("Página de contato não encontrada"),
    no_social: tr("Redes sociais não vinculadas no site"),
    image_alt_partial: tr("Textos alternativos incompletos"),
    image_alt_low: tr("Poucas imagens têm texto alternativo"),
    button_labels_partial: tr("Alguns botões podem não ter rótulo claro"),
    button_labels_low: tr("Botões sem rótulo claro detectados"),
  };
  const scoreDimensionLabels: Record<string, string> = {
    digital_need: tr("Necessidade digital"),
    public_demand: tr("Demanda pública"),
    reachability: tr("Facilidade de contato"),
    digital_activity: tr("Atividade digital"),
  };
  const confidenceComponentLabels: Record<string, string> = {
    identity: tr("Identificação"),
    public_evidence: tr("Evidência pública"),
    digital_presence: tr("Presença digital"),
    website_verification: tr("Verificação do site"),
    contactability: tr("Contatos verificados"),
    niche_context: tr("Contexto do nicho"),
  };
  const commercialStructureSignalLabels: Record<string, string> = {
    reviews: tr("Volume de avaliações"),
    rating: tr("Nota pública"),
    local_demand: tr("Demanda acima de boa parte dos concorrentes locais"),
    multiple_locations: tr("Múltiplas unidades detectadas"),
    own_domain: tr("Domínio próprio"),
    analytics: tr("Ferramentas de analytics detectadas"),
    digital_capabilities: tr("Capacidade digital operacional detectada"),
    instagram_active: tr("Instagram ativo confirmado"),
    instagram: tr("Instagram encontrado"),
    social_links: tr("Site conectado às redes sociais"),
    owned_presence: tr("Presença digital própria"),
    measurement: tr("Medição digital detectada"),
    whatsapp: tr("WhatsApp disponível"),
    phone: tr("Telefone disponível"),
    email: tr("E-mail encontrado"),
    forms: tr("Formulário de contato"),
  };
  const confidence = lead.score.confidence || {
    value: 0,
    level: "low",
    components: {},
    missing: [],
  };
  const serviceScores = lead.score.service_scores || [];
  const intelligence = lead.website_intelligence || {};
  const competitive =
    lead.score.competitive || lead.competitive_context || null;
  const commercialStructure = lead.score.commercial_structure || {
    value: 0,
    level: "low",
    confidence: 0,
    components: {},
    signals: [],
  };
  const timing = lead.score.timing || {
    value: 0,
    level: "low",
    signals: [],
    latest_event_at: null,
  };
  const combinedSignals = lead.score.combined_signals || [];
  const commercialLevelLabel = (level: "high" | "medium" | "low") =>
    tr(level === "high" ? "Alta" : level === "medium" ? "Média" : "Baixa");
  const audit =
    research?.audit &&
    typeof (research.audit as LeadAudit).quality_score === "number"
      ? (research.audit as LeadAudit)
      : null;
  const opportunity = getOpportunityBrief(lead, audit);

  function selectContextTab(next: string) {
    setTab(next);
    if (next !== "summary") setMobileExpanded(true);
  }

  useDialogLifecycle(panel);
  return (
    <dialog
      ref={panel}
      tabIndex={-1}
      className={`context-panel context-${environment} ${tab === "workflow" ? "context-operation" : ""} ${mobileExpanded ? "context-mobile-expanded" : ""}`}
      aria-labelledby="lead-title"
      onCancel={(event) => {
        event.preventDefault();
        closePanel();
      }}
      onClick={(event) => {
        if (event.target === panel.current) {
          const box = panel.current.getBoundingClientRect();
          if (
            event.clientX < box.left ||
            event.clientX > box.right ||
            event.clientY < box.top ||
            event.clientY > box.bottom
          )
            closePanel();
        }
      }}
    >
      <button
        type="button"
        className="context-sheet-handle"
        aria-expanded={mobileExpanded}
        aria-label={tr(
          mobileExpanded ? "Recolher detalhes" : "Expandir detalhes",
        )}
        onClick={() => setMobileExpanded((value) => !value)}
      >
        <i />
      </button>
      <header className="context-panel-header">
        <span className="eyebrow">
          {tr(
            lead.stage === "won"
              ? "Cliente"
              : environment === "manage"
                ? "Negociação"
                : "Oportunidade",
          )}
        </span>
        <div>
          <button
            className="icon-button"
            aria-label={tr("Editar empresa")}
            onClick={onEdit}
          >
            <Pencil size={18} />
          </button>
          <button
            className="icon-button"
            aria-label={tr("Fechar detalhes")}
            onClick={closePanel}
          >
            <X size={21} />
          </button>
        </div>
      </header>
      <div className="context-identity">
        <div className="company-monogram">
          {lead.name.slice(0, 2).toUpperCase()}
        </div>
        <div>
          <h2 id="lead-title">{lead.name}</h2>
          <p>
            {lead.category} · {lead.city}
          </p>
        </div>
      </div>
      <nav
        className="context-tabs"
        aria-label={tr("Detalhes da empresa")}
        role="tablist"
      >
        {[
          ["summary", "Resumo"],
          ["workflow", "Operação"],
          ["analysis", "Análise"],
          ["research", "Pesquisa"],
          ["relationship", "Relacionamento"],
        ].map(([key, label], index, tabs) => (
          <button
            key={key}
            id={`context-tab-${key}`}
            role="tab"
            tabIndex={tab === key ? 0 : -1}
            aria-selected={tab === key}
            aria-controls="context-body"
            onClick={() => selectContextTab(key)}
            onKeyDown={(event) => {
              if (
                ["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)
              ) {
                event.preventDefault();
                const next =
                  event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? tabs.length - 1
                      : (index +
                          (event.key === "ArrowRight" ? 1 : -1) +
                          tabs.length) %
                        tabs.length;
                selectContextTab(tabs[next][0]);
                panel.current
                  ?.querySelector<HTMLButtonElement>(
                    `#context-tab-${tabs[next][0]}`,
                  )
                  ?.focus();
              }
            }}
          >
            {tr(label)}
          </button>
        ))}
      </nav>
      <div
        className="context-body"
        id="context-body"
        role="tabpanel"
        aria-labelledby={`context-tab-${tab}`}
        tabIndex={0}
        key={lead.id}
      >
        {workflowOpened && (
          <div hidden={tab !== "workflow"}>
            <OpportunityWorkflow
              key={lead.id}
              lead={lead}
              onDirty={setWorkflowDirty}
              onLeadUpdated={onLeadUpdated}
              onInvestigate={() => selectContextTab("research")}
              onHistory={() => {
                setActivityKind("note");
                selectContextTab("relationship");
              }}
            />
          </div>
        )}
        {tab === "summary" && (
          <>
            {lead.demo && (
              <p className="demo-disclosure">
                {tr("Estabelecimento fictício")}
              </p>
            )}
            {environment === "operate" ? (
              <>
                <div className="context-priority">
                  <div>
                    <span>{tr(opportunity.priorityLabel)}</span>
                    <strong>
                      {lead.score.value}
                      <small>/100</small>
                    </strong>
                  </div>
                  <div>
                    <span>{tr("Timing comercial")}</span>
                    <b>{commercialLevelLabel(timing.level)}</b>
                  </div>
                </div>
                <h3 className="context-opportunity-title">
                  {tr(opportunity.headline)}
                </h3>
                <ul className="context-signals">
                  {opportunity.signals.slice(0, 3).map((signal) => (
                    <li key={signal.key}>
                      <Check size={16} />
                      <span>
                        {tr(signal.label)}
                        {signal.detail && <small>{signal.detail}</small>}
                      </span>
                    </li>
                  ))}
                </ul>
                {serviceScores[0] && (
                  <div className="context-service">
                    <span>{tr("Principal serviço")}</span>
                    <b>{tr(serviceScores[0].label)}</b>
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="context-stage">
                  <span>{tr("Etapa comercial")}</span>
                  <strong>{stageLabel(lead.stage)}</strong>
                </div>
                {lead.next_action && (
                  <button
                    className="next-action-focus"
                    onClick={() => selectContextTab("relationship")}
                  >
                    <CalendarClock size={19} />
                    <span>
                      <b>{lead.next_action}</b>
                      <small>{lead.next_action_on || tr("Sem data")}</small>
                    </span>
                    <ArrowUpRight size={17} />
                  </button>
                )}
                {sales.length ? (
                  <div className="context-sales">
                    {sales.map((sale) => (
                      <div key={sale.id}>
                        <span>{sale.service}</span>
                        <strong>
                          {money(sale.amount_cents, sale.currency)}
                        </strong>
                        <small>
                          {tr("A receber")}:{" "}
                          {money(
                            sale.amount_cents - sale.received_cents,
                            sale.currency,
                          )}
                        </small>
                      </div>
                    ))}
                  </div>
                ) : (
                  lead.potential_cents > 0 && (
                    <div className="context-service">
                      <span>{tr("Valor potencial")}</span>
                      <b>
                        {money(lead.potential_cents, lead.potential_currency)}
                      </b>
                    </div>
                  )
                )}
              </>
            )}
            {environment === "operate" && (
              <div className="context-next-work">
                {lead.contact_blocked && (
                  <p role="status">{tr("Contato suspenso")}</p>
                )}
                <button
                  className="button primary"
                  onClick={() => selectContextTab("workflow")}
                >
                  {tr("Abrir ficha operacional")}
                </button>
                {lead.next_action && <p>{lead.next_action}</p>}
              </div>
            )}
            <div className="context-contact">
              <p>
                <MapPin size={16} />
                <span>{lead.address || `${lead.city}, ${lead.country}`}</span>
              </p>
              {lead.phone && (
                <p>
                  <Phone size={16} />
                  <span>{lead.phone}</span>
                </p>
              )}
              <div>
                {lead.whatsapp && !lead.demo && (
                  <ExternalLink href={`https://wa.me/${lead.whatsapp}`}>
                    WhatsApp
                  </ExternalLink>
                )}
                {lead.instagram && (
                  <ExternalLink href={lead.instagram}>Instagram</ExternalLink>
                )}
                {lead.website && (
                  <ExternalLink href={lead.website}>{tr("Site")}</ExternalLink>
                )}
              </div>
            </div>
            <button
              className="context-disclosure"
              onClick={() =>
                selectContextTab(
                  environment === "operate" ? "analysis" : "relationship",
                )
              }
            >
              <span>
                {tr(
                  environment === "operate"
                    ? "Entender esta oportunidade"
                    : "Histórico e próximas ações",
                )}
              </span>
              <ArrowUpRight size={18} />
            </button>
            <button
              className="text-link watch-context"
              disabled={watchBusy || lead.demo}
              onClick={() => void toggleWatchlist()}
            >
              {lead.watchlisted ? <BellOff size={17} /> : <Bell size={17} />}{" "}
              {tr(
                lead.watchlisted ? "Parar de acompanhar" : "Acompanhar empresa",
              )}
            </button>
            {watchError && (
              <p className="research-error" role="alert">
                {watchError}
              </p>
            )}
          </>
        )}
        {tab === "analysis" && (
          <div className="analysis-workspace">
            <CommercialReview lead={lead} onUpdated={onLeadUpdated} />
            <section className="opportunity-evidence">
              <h3>{tr("Ver evidências do índice")}</h3>
              <p className="field-hint">
                {tr(opportunity.priorityExplanation)}
              </p>
              <p className="field-hint">
                {tr(
                  "Prioridade comercial, não probabilidade de venda. Dimensões desconhecidas ficam sem avaliação.",
                )}
              </p>
              <p className="field-hint">
                {tr("Faixas: alta 70+, média 40–69, baixa abaixo de 40.")}
              </p>
              {lead.score.commercial_dimensions && (
                <section aria-label="Qualificação comercial">
                  <p>
                    Estado: {lead.score.status} · Cobertura:{" "}
                    {lead.score.coverage}%
                  </p>
                  <dl>
                    {Object.entries(lead.score.commercial_dimensions).map(
                      ([key, d]) => (
                        <div key={key}>
                          <dt>
                            {{
                              target_fit: "Adequação",
                              need: "Necessidade",
                              impact: "Impacto potencial",
                              viability: "Viabilidade",
                              activity: "Atividade",
                            }[key] || key}
                          </dt>
                          <dd>
                            {d.value === null
                              ? "Não avaliado"
                              : `${d.value}/100`}{" "}
                            · {d.reason}
                          </dd>
                        </div>
                      ),
                    )}
                  </dl>
                  {lead.score.previous?.version && (
                    <p>
                      Antes da migração: {lead.score.previous.value}/100 ·
                      fórmula {lead.score.previous.version}
                    </p>
                  )}
                </section>
              )}
              <details>
                <summary>Diagnósticos técnicos auxiliares</summary>
                <div className="score-dimensions">
                  {Object.entries(lead.score.dimensions || {}).map(
                    ([key, item]) => (
                      <div className="score-dimension" key={key}>
                        <div>
                          <span>{scoreDimensionLabels[key] || key}</span>
                          <b>
                            {item.value}/{item.max}
                          </b>
                        </div>
                        <i aria-hidden="true">
                          <span
                            style={{
                              width: `${Math.min(100, Math.round((item.value / Math.max(1, item.max)) * 100))}%`,
                            }}
                          />
                        </i>
                      </div>
                    ),
                  )}
                </div>
              </details>
              <div className="confidence-score" data-level={confidence.level}>
                <div>
                  <span>{tr("Confiança dos dados")}</span>
                  <b>
                    {confidence.value}/100 ·{" "}
                    {tr(
                      confidence.level === "high"
                        ? "Alta"
                        : confidence.level === "medium"
                          ? "Média"
                          : "Baixa",
                    )}
                  </b>
                </div>
                <i aria-hidden="true">
                  <span
                    style={{ width: `${Math.min(100, confidence.value)}%` }}
                  />
                </i>
                <details>
                  <summary>{tr("Ver cobertura dos dados")}</summary>
                  <div className="confidence-components">
                    {Object.entries(confidence.components || {}).map(
                      ([key, item]) => (
                        <span key={key}>
                          <em>{confidenceComponentLabels[key] || key}</em>
                          <b>
                            {item.value}/{item.max}
                          </b>
                        </span>
                      ),
                    )}
                  </div>
                  {!!confidence.missing?.length && (
                    <p className="field-hint">
                      {tr("Ainda falta verificar")}:{" "}
                      {confidence.missing.map((item) => tr(item)).join(" · ")}
                    </p>
                  )}
                  <p className="field-hint">
                    {tr(
                      "Confiança mede cobertura das evidências, não chance de fechar a venda.",
                    )}
                  </p>
                </details>
                {(confidence.value < 80 || !!confidence.missing?.length) &&
                  !lead.demo && (
                    <button
                      className="secondary-button confidence-reanalysis-button"
                      type="button"
                      onClick={runIntelligentReanalysis}
                      disabled={reanalysisBusy}
                    >
                      {reanalysisBusy ? (
                        <LoaderCircle size={14} className="spin" />
                      ) : (
                        <Search size={14} />
                      )}
                      {tr("Aprofundar análise")}
                    </button>
                  )}
                {reanalysisMessage && (
                  <p className="field-hint confidence-reanalysis-message">
                    {reanalysisMessage}
                  </p>
                )}
              </div>
              {lead.score.reasons.length ? (
                lead.score.reasons.map((r) => (
                  <div className="reason" key={r.key}>
                    <span>
                      <Check size={14} />
                      {tr(r.label)}
                    </span>
                    <b>+{r.points}</b>
                  </div>
                ))
              ) : (
                <p className="muted">
                  {tr("Preencha os sinais verificados para calcular o índice.")}
                </p>
              )}
              <p className="field-hint">
                {tr("Regras do índice")} v{lead.score.version} ·{" "}
                {tr("máximo de 100 pontos")}.
              </p>
            </section>
            <section className="commercial-readout-section">
              <div className="commercial-readout-row">
                <div>
                  <span className="eyebrow">
                    {tr("ESTRUTURA COMERCIAL APARENTE")}
                  </span>
                  <strong>
                    {commercialStructure.value}/100 ·{" "}
                    {commercialLevelLabel(commercialStructure.level)}
                  </strong>
                  <small>
                    {tr(
                      "Sinais visíveis de operação e maturidade, não faturamento ou capacidade financeira.",
                    )}
                  </small>
                </div>
                <div className="commercial-readout-signals">
                  {commercialStructure.signals.slice(0, 3).map((item) => (
                    <span key={item.key}>
                      {commercialStructureSignalLabels[item.key] ||
                        tr(item.label)}
                    </span>
                  ))}
                </div>
              </div>
              <div
                className="commercial-readout-row timing-readout"
                data-level={timing.level}
              >
                <div>
                  <span className="eyebrow">{tr("TIMING COMERCIAL")}</span>
                  <strong>
                    {timing.value}/100 · {commercialLevelLabel(timing.level)}
                  </strong>
                  <small>
                    {tr(
                      "Mede se existe motivo observável para priorizar a abordagem agora, não chance de fechamento.",
                    )}
                  </small>
                </div>
                <div className="commercial-readout-signals">
                  {timing.signals.length ? (
                    timing.signals.slice(0, 3).map((item) => (
                      <span
                        key={`${item.key}-${item.at}`}
                        data-effect={item.effect}
                      >
                        {tr(item.label)}
                      </span>
                    ))
                  ) : (
                    <span>
                      {tr(
                        "Nenhum sinal recente forte o suficiente para alterar o timing.",
                      )}
                    </span>
                  )}
                </div>
              </div>
            </section>
            {!!combinedSignals.length && (
              <section className="combined-signals-section">
                <div className="drawer-section-head">
                  <div>
                    <span className="eyebrow">{tr("SINAIS COMBINADOS")}</span>
                    <strong>
                      {tr(
                        "Contexto que aparece quando sinais independentes contam a mesma história",
                      )}
                    </strong>
                  </div>
                </div>
                <div className="combined-signals-list">
                  {combinedSignals.map((item) => (
                    <article
                      className="combined-signal"
                      data-strength={item.strength}
                      key={item.key}
                    >
                      <div>
                        <strong>{tr(item.label)}</strong>
                        <p>{tr(item.recommended_action)}</p>
                      </div>
                      <div className="combined-signal-evidence">
                        {item.evidence.map((value) => (
                          <span key={value}>{tr(value)}</span>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
                <p className="field-hint">
                  {tr(
                    "Sinais combinados explicam padrões; não adicionam pontos escondidos ao Opportunity Score.",
                  )}
                </p>
              </section>
            )}
            {competitive &&
              (competitive.status === "ready" ||
                competitive.peers_count > 0) && (
                <section
                  className="competitive-context-section"
                  data-status={competitive.status}
                >
                  <div className="drawer-section-head competitive-context-head">
                    <div>
                      <span className="eyebrow">
                        {tr("CONTEXTO COMPETITIVO LOCAL")}
                      </span>
                      <strong>
                        {competitive.status === "ready"
                          ? `${competitive.peers_count} ${tr("concorrentes comparáveis")}`
                          : tr("Amostra local ainda pequena")}
                      </strong>
                    </div>
                    <small>{competitive.radius_km} km</small>
                  </div>
                  {competitive.status === "ready" ? (
                    <>
                      <div className="competitive-metrics">
                        <span>
                          <em>{tr("Com site próprio")}</em>
                          <b>{competitive.peer_site_rate}%</b>
                        </span>
                        <span>
                          <em>{tr("Com site forte")}</em>
                          <b>{competitive.strong_site_rate}%</b>
                        </span>
                        <span>
                          <em>{tr("Mediana de avaliações")}</em>
                          <b>{competitive.median_reviews ?? "—"}</b>
                        </span>
                        <span>
                          <em>{tr("Posição em avaliações")}</em>
                          <b>
                            {competitive.review_percentile !== null
                              ? `${competitive.review_percentile}%`
                              : "—"}
                          </b>
                        </span>
                      </div>
                      {competitive.site_gap && (
                        <div
                          className="competitive-gap"
                          data-gap={competitive.site_gap}
                        >
                          <AlertCircle size={15} />
                          <span>
                            <strong>
                              {tr(
                                competitive.site_gap === "missing"
                                  ? "Presença digital abaixo do mercado local"
                                  : "Site abaixo do padrão digital local",
                              )}
                            </strong>
                            <small>
                              {tr(
                                "O contexto competitivo só reforça o score quando há amostra suficiente.",
                              )}
                            </small>
                          </span>
                        </div>
                      )}
                      {competitive.demand_above_median && (
                        <p className="field-hint">
                          {tr(
                            "A demanda pública está acima da mediana dos concorrentes próximos.",
                          )}
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="field-hint">
                      {tr(
                        "O Scout precisa de pelo menos quatro empresas comparáveis e três presenças digitais conhecidas para usar este contexto no score.",
                      )}
                    </p>
                  )}
                </section>
              )}
            {!!serviceScores.length && (
              <section className="service-fit-section">
                <div className="drawer-section-head service-fit-head">
                  <div>
                    <span className="eyebrow">{tr("FIT POR SERVIÇO")}</span>
                    <strong>
                      {tr("Onde a oportunidade faz mais sentido")}
                    </strong>
                  </div>
                  <small>{tr("não é chance de fechamento")}</small>
                </div>
                <div className="service-fit-list">
                  {serviceScores.slice(0, 4).map((item) => (
                    <div className="service-fit-row" key={item.key}>
                      <div>
                        <span>{tr(item.label)}</span>
                        <b>
                          {item.value}
                          <small>/100</small>
                        </b>
                      </div>
                      <i aria-hidden="true">
                        <span
                          style={{ width: `${Math.min(100, item.value)}%` }}
                        />
                      </i>
                      {!!item.signals.length && (
                        <p>
                          {item.signals
                            .slice(0, 2)
                            .map((signal) => tr(signal))
                            .join(" · ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
                <p className="field-hint service-fit-note">
                  {tr(
                    "O fit combina necessidade verificada do serviço com demanda pública e facilidade de contato.",
                  )}
                </p>
              </section>
            )}
            <section className="score-context-section">
              <div className="drawer-section-head score-context-head">
                <div>
                  <span className="eyebrow">{tr("CONTEXTO DO NICHO")}</span>
                  <strong>
                    {tr(lead.score.niche?.label || "Negócio local")}
                  </strong>
                </div>
                <small>
                  {lead.score.niche?.matched_by === "fallback"
                    ? tr("Contexto genérico")
                    : `${lead.score.niche?.confidence || 0}% ${tr("de confiança")}`}
                </small>
              </div>
              {!!lead.score.niche?.expectations?.length && (
                <div className="niche-expectations">
                  {lead.score.niche.expectations.map((item) => (
                    <span
                      key={item.key}
                      data-state={item.state}
                      data-importance={item.importance}
                    >
                      <i aria-hidden="true" />
                      {tr(item.label)}
                      <small>
                        {item.state === "present"
                          ? tr("detectado")
                          : item.state === "missing"
                            ? tr("não detectado")
                            : tr("não verificado")}
                      </small>
                    </span>
                  ))}
                </div>
              )}
              {!!lead.score.diagnosis?.length && (
                <div className="structured-diagnosis">
                  <div className="structured-diagnosis-title">
                    <span>{tr("DIAGNÓSTICO")}</span>
                    <small>
                      {lead.score.diagnosis.length} {tr("sinais verificados")}
                    </small>
                  </div>
                  {lead.score.diagnosis.slice(0, 6).map((item) => (
                    <div
                      className="diagnosis-row"
                      data-severity={item.severity}
                      key={item.key}
                    >
                      <i aria-hidden="true" />
                      <div>
                        <strong>{tr(item.title)}</strong>
                        <p>{tr(item.detail)}</p>
                      </div>
                      <span>
                        {tr(
                          item.severity === "high"
                            ? "Alta"
                            : item.severity === "medium"
                              ? "Média"
                              : "Baixa",
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
        {tab === "research" && (
          <>
            <div className="research-tools">
              <button
                className="button"
                disabled={enrichmentBusy || lead.demo}
                onClick={() => void runEnrichment()}
              >
                {enrichmentBusy ? (
                  <LoaderCircle size={17} className="spin" />
                ) : (
                  <Database size={17} />
                )}{" "}
                {tr("Enriquecer dados")}
              </button>
              <button
                className="button"
                disabled={reanalysisBusy || lead.demo}
                onClick={() => void runIntelligentReanalysis()}
              >
                <Search size={17} />
                {tr("Aprofundar análise")}
              </button>
            </div>
            {enrichmentMessage && <p role="status">{enrichmentMessage}</p>}
            {!!lead.enrichment?.observed_contacts?.length && (
              <details>
                <summary>{tr("Contatos observados no site")}</summary>
                <ul>
                  {lead.enrichment.observed_contacts.map((contact, i) => (
                    <li key={`${contact.field}-${i}`}>
                      {contact.value} ·{" "}
                      <a
                        href={contact.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {tr("Fonte")}
                      </a>
                    </li>
                  ))}
                </ul>
                <p>
                  {tr(
                    "Links públicos observados; não representam autorização de contato.",
                  )}
                </p>
              </details>
            )}
            {reanalysisMessage && <p role="status">{reanalysisMessage}</p>}
            <section className="research-panel" aria-live="polite">
              <div className="research-head">
                <div>
                  <span className="eyebrow">{tr("PESQUISA WEB")}</span>
                  <strong>{tr("Presença digital")}</strong>
                </div>
                {research?.status === "confirmed" && (
                  <span className="research-confidence">
                    {research.confidence}%
                  </span>
                )}
              </div>

              {researchLoading ? (
                <div className="research-state muted">
                  <LoaderCircle size={14} className="spin" />
                  {tr("Carregando análise")}
                </div>
              ) : research ? (
                <div className="research-result">
                  <div className={`research-status ${research.status}`}>
                    {research.status === "confirmed" ? (
                      <ShieldCheck size={15} />
                    ) : (
                      <AlertCircle size={15} />
                    )}
                    <span>
                      {research.status === "confirmed"
                        ? tr("Site confirmado")
                        : research.status === "not_found"
                          ? tr("Site não encontrado na pesquisa")
                          : tr("Site ainda não confirmado")}
                    </span>
                  </div>
                  {research.website_url && (
                    <a
                      className="research-domain"
                      href={research.website_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {research.page?.domain ||
                        new URL(research.website_url).hostname}
                      <ArrowUpRight size={14} />
                    </a>
                  )}
                  {!!research.evidence.length && (
                    <div className="research-signals">
                      {research.evidence.slice(0, 5).map((item, index) => (
                        <span key={`${item.key}-${index}`}>
                          <Check size={12} />
                          {evidenceLabels[item.key] || item.key}
                        </span>
                      ))}
                    </div>
                  )}
                  {!!research.checks.length && (
                    <div className="research-checks">
                      {research.checks
                        .filter(
                          (item) =>
                            !item.source_url ||
                            item.source_url === research.website_url,
                        )
                        .map((item) => (
                          <span key={item.key} data-state={item.state}>
                            <i />
                            {checkLabels[item.key] || item.key}
                          </span>
                        ))}
                    </div>
                  )}
                  <div className="research-meta">
                    <span>
                      {research.search_configured
                        ? tr("Busca web + validação direta")
                        : tr("Validação direta de domínios")}
                    </span>
                    <span>
                      {new Date(research.checked_at * 1000).toLocaleString(
                        activeLocale(),
                        {
                          dateStyle: "short",
                          timeStyle: "short",
                        },
                      )}
                    </span>
                  </div>
                  {!!research.sources.length && (
                    <details className="research-sources">
                      <summary>{tr("Fontes consultadas")}</summary>
                      {research.sources.slice(0, 4).map((source, index) => (
                        <a
                          key={`${source.url}-${index}`}
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <span>
                            {source.title || new URL(source.url).hostname}
                          </span>
                          <ArrowUpRight size={12} />
                        </a>
                      ))}
                    </details>
                  )}
                </div>
              ) : (
                <p className="research-empty">
                  {tr(
                    "Cruza domínio, identidade e sinais públicos da empresa.",
                  )}
                </p>
              )}

              {research?.status === "confirmed" && audit && (
                <div className="deep-audit">
                  <div className="deep-audit-head">
                    <div>
                      <span className="eyebrow">
                        {tr("AUDITORIA PROFUNDA")}
                      </span>
                      <strong>{tr("Saúde técnica e comercial do site")}</strong>
                    </div>
                    <span className="deep-audit-score">
                      {audit.quality_score}
                      <small>/100</small>
                    </span>
                  </div>
                  <div className="deep-audit-categories">
                    {Object.entries(audit.categories).map(([key, item]) => (
                      <div key={key}>
                        <span>{auditCategoryLabels[key] || key}</span>
                        <b>
                          {item.score}/{item.max}
                        </b>
                      </div>
                    ))}
                  </div>
                  {intelligence.technologies?.length ||
                  intelligence.analytics?.length ||
                  intelligence.booking ||
                  intelligence.ecommerce ||
                  intelligence.catalog_or_menu ||
                  intelligence.live_chat ||
                  intelligence.free_host_domain ? (
                    <div className="site-intelligence">
                      <span className="eyebrow">
                        {tr("IDENTIFICAÇÃO DO SITE")}
                      </span>
                      <div className="site-intelligence-grid">
                        {intelligence.own_domain ? (
                          <span>{tr("Domínio próprio")}</span>
                        ) : null}
                        {intelligence.free_host_domain ? (
                          <span>{tr("Subdomínio de plataforma")}</span>
                        ) : null}
                        {intelligence.booking ? (
                          <span>{tr("Agendamento detectado")}</span>
                        ) : null}
                        {intelligence.ecommerce ? (
                          <span>{tr("E-commerce detectado")}</span>
                        ) : null}
                        {intelligence.catalog_or_menu ? (
                          <span>{tr("Catálogo ou cardápio detectado")}</span>
                        ) : null}
                        {intelligence.live_chat ? (
                          <span>{tr("Chat no site detectado")}</span>
                        ) : null}
                        {intelligence.analytics?.map((item) => (
                          <span key={`analytics-${item}`}>{item}</span>
                        ))}
                        {intelligence.technologies?.map((item) => (
                          <span key={`tech-${item}`}>{item}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {!!audit.findings.length && (
                    <div className="deep-audit-findings">
                      {audit.findings.slice(0, 6).map((item) => (
                        <div key={item.key} data-severity={item.severity}>
                          <i />
                          <span>
                            {auditFindingLabels[item.key] || item.label}
                            {item.detail ? <small>{item.detail}</small> : null}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {!!audit.angles?.length && (
                    <div className="deep-audit-angles">
                      <span className="eyebrow">
                        {tr("ÂNGULOS COMERCIAIS")}
                      </span>
                      {audit.angles.slice(0, 3).map((angle) => (
                        <div key={angle.key}>
                          <span>{tr(angle.label)}</span>
                          <small>
                            {angle.evidence.length} {tr("sinais objetivos")}
                          </small>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="deep-audit-meta">
                    <span>
                      {audit.pages_checked} {tr("páginas verificadas")}
                    </span>
                    {research.audited_at ? (
                      <span>
                        {new Date(research.audited_at * 1000).toLocaleString(
                          activeLocale(),
                          { dateStyle: "short", timeStyle: "short" },
                        )}
                      </span>
                    ) : null}
                  </div>
                </div>
              )}

              {researchError && (
                <p className="research-error">{researchError}</p>
              )}
              {!lead.demo && (
                <div className="research-actions">
                  <button
                    className="button research-button"
                    onClick={() => void runResearch()}
                    disabled={researchBusy || deepBusy}
                  >
                    {researchBusy ? (
                      <LoaderCircle size={15} className="spin" />
                    ) : (
                      <Search size={15} />
                    )}
                    {researchBusy
                      ? tr("Pesquisando empresa")
                      : research
                        ? tr("Pesquisar novamente")
                        : tr("Analisar oportunidade")}
                  </button>
                  {research?.status === "confirmed" && (
                    <button
                      className="button research-button deep"
                      onClick={() => void runDeepAudit()}
                      disabled={deepBusy || researchBusy}
                    >
                      {deepBusy ? (
                        <LoaderCircle size={15} className="spin" />
                      ) : (
                        <ShieldCheck size={15} />
                      )}
                      {deepBusy
                        ? tr("Auditando site")
                        : audit
                          ? tr("Atualizar auditoria")
                          : tr("Auditoria profunda")}
                    </button>
                  )}
                </div>
              )}
            </section>
            <section className="drawer-company-section">
              <div className="drawer-section-head">
                <span className="eyebrow">{tr("EMPRESA")}</span>
              </div>
              <div className="drawer-facts">
                {lead.rating !== null && (
                  <div>
                    <Star size={16} />
                    <span>
                      <small>{tr("Avaliação")}</small>
                      <strong>
                        {lead.rating.toFixed(1)}{" "}
                        <em>
                          · {lead.reviews ?? "—"} {tr("avaliações")}
                        </em>
                      </strong>
                    </span>
                  </div>
                )}
                <div>
                  <MapPin size={16} />
                  <span>
                    <small>{tr("Endereço")}</small>
                    <strong>
                      {lead.address || `${lead.city}, ${lead.country}`}
                    </strong>
                  </span>
                </div>
                <div>
                  <Globe size={16} />
                  <span>
                    <small>{tr("Site")}</small>
                    {lead.website ? (
                      <ExternalLink href={lead.website}>
                        {tr("Ver site")}
                      </ExternalLink>
                    ) : (
                      <strong>
                        {lead.website_status === "none"
                          ? tr("Sem site confirmado")
                          : tr("Site ainda não verificado")}
                      </strong>
                    )}
                  </span>
                </div>
                {lead.phone && (
                  <div>
                    <Phone size={16} />
                    <span>
                      <small>{tr("Telefone")}</small>
                      <strong>{lead.phone}</strong>
                    </span>
                  </div>
                )}
                {lead.contact && (
                  <div>
                    <MessageCircle size={16} />
                    <span>
                      <small>{tr("Contato")}</small>
                      <strong>{lead.contact}</strong>
                    </span>
                  </div>
                )}
                {lead.instagram && (
                  <div>
                    <MessageCircle size={16} />
                    <span>
                      <small>Instagram</small>
                      <ExternalLink href={lead.instagram}>
                        Instagram
                      </ExternalLink>
                    </span>
                  </div>
                )}
              </div>
            </section>
          </>
        )}
        {tab === "relationship" && (
          <>
            {(lead.potential_cents > 0 || lead.in_pipeline || lead.notes) && (
              <section className="drawer-commercial-section">
                <div className="drawer-section-head">
                  <span className="eyebrow">{tr("COMERCIAL")}</span>
                </div>
                {lead.potential_cents > 0 && (
                  <div className="potential">
                    <span>{tr("Valor potencial")}</span>
                    <b>
                      {money(lead.potential_cents, lead.potential_currency)}
                    </b>
                  </div>
                )}
                {lead.in_pipeline && (
                  <div className="field drawer-stage-field">
                    <span>{tr("Etapa comercial")}</span>
                    <SmartSelect
                      value={lead.stage}
                      disabled={busy || lead.stage === "won"}
                      onChange={(next) =>
                        next === "won" ? onSale() : onMove(next as Stage)
                      }
                      options={stages.map((stage) => ({
                        value: stage.id,
                        label: tr(stage.label),
                      }))}
                    />
                  </div>
                )}
                {lead.in_pipeline && !["won", "lost"].includes(lead.stage) && (
                  <div className="next-action-editor">
                    <div className="next-action-editor-head">
                      <span>
                        <CalendarClock size={15} aria-hidden="true" />
                        {tr("Próxima ação")}
                      </span>
                      {lead.next_action && (
                        <button
                          className="text-link"
                          type="button"
                          disabled={actionBusy}
                          onClick={() => void updateNextAction("", "")}
                        >
                          {tr("Limpar")}
                        </button>
                      )}
                    </div>
                    <div className="next-action-fields">
                      <input
                        type="text"
                        maxLength={180}
                        value={nextAction}
                        onChange={(event) => setNextAction(event.target.value)}
                        placeholder={tr("Ex.: Ligar e enviar proposta")}
                        aria-label={tr("Próxima ação")}
                      />
                      <DateField
                        name="next_action_on"
                        min={inputDate(timezone)}
                        value={nextActionOn}
                        onChange={setNextActionOn}
                        ariaLabel={tr("Data da próxima ação")}
                      />
                      <button
                        className="button next-action-save"
                        type="button"
                        disabled={actionBusy || !nextAction.trim()}
                        onClick={() =>
                          void updateNextAction(nextAction, nextActionOn)
                        }
                      >
                        {actionBusy ? (
                          <LoaderCircle size={14} className="spin" />
                        ) : (
                          <Check size={14} />
                        )}
                        {tr("Salvar ação")}
                      </button>
                    </div>
                    {actionError && (
                      <p className="research-error">{actionError}</p>
                    )}
                  </div>
                )}
                {lead.notes && (
                  <div className="drawer-notes">
                    <h3>{tr("Anotações")}</h3>
                    <p>{lead.notes}</p>
                  </div>
                )}
              </section>
            )}
            {
              <section className="commercial-history-section">
                <div className="drawer-section-head commercial-history-head">
                  <span className="eyebrow">{tr("HISTÓRICO COMERCIAL")}</span>
                  <span className="muted">
                    {activities.length
                      ? `${activities.length} ${tr("registros")}`
                      : ""}
                  </span>
                </div>
                {!lead.demo && !["won", "lost"].includes(lead.stage) && (
                  <div className="commercial-log-form">
                    <SmartSelect
                      ariaLabel={tr("Tipo de contato")}
                      value={activityKind}
                      onChange={setActivityKind}
                      options={[
                        { value: "whatsapp", label: "WhatsApp" },
                        { value: "call", label: tr("Ligação") },
                        { value: "email", label: "E-mail" },
                        { value: "meeting", label: tr("Reunião") },
                        { value: "proposal", label: tr("Proposta") },
                        { value: "reply", label: tr("Resposta") },
                        { value: "note", label: tr("Anotação") },
                      ]}
                    />
                    <input
                      type="text"
                      maxLength={1200}
                      value={activityBody}
                      onChange={(event) => setActivityBody(event.target.value)}
                      placeholder={tr(
                        "Ex.: Cliente pediu proposta para amanhã",
                      )}
                      aria-label={tr("Detalhes do contato")}
                    />
                    <button
                      className="button commercial-log-save"
                      type="button"
                      disabled={
                        activityBusy ||
                        (activityKind === "note" && !activityBody.trim())
                      }
                      onClick={() => void addCommercialActivity()}
                    >
                      {activityBusy ? (
                        <LoaderCircle size={14} className="spin" />
                      ) : (
                        <Plus size={14} />
                      )}
                      {tr("Registrar")}
                    </button>
                  </div>
                )}
                {activityError && (
                  <p className="research-error">{activityError}</p>
                )}
                {activitiesLoading ? (
                  <div className="commercial-history-loading muted">
                    <LoaderCircle size={14} className="spin" />{" "}
                    {tr("Carregando histórico")}
                  </div>
                ) : activities.length ? (
                  <div className="commercial-timeline">
                    {activities.map((item) => (
                      <div className="commercial-timeline-item" key={item.id}>
                        <span className="commercial-timeline-mark">
                          <History size={13} />
                        </span>
                        <div>
                          <strong>{activityTitle(item)}</strong>
                          {activityDetail(item) && (
                            <p>{activityDetail(item)}</p>
                          )}
                          <small>
                            {new Date(item.created_at * 1000).toLocaleString(
                              activeLocale(),
                              { dateStyle: "short", timeStyle: "short" },
                            )}
                          </small>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="muted commercial-history-empty">
                    {tr("Nenhum contato registrado ainda.")}
                  </p>
                )}
              </section>
            }
            {!lead.in_pipeline && !lead.watchlisted && (
              <p className="muted">
                {tr(
                  "Salve a oportunidade para iniciar o relacionamento comercial.",
                )}
              </p>
            )}
            {lead.stage !== "won" && (
              <button className="button ghost" onClick={onDelete}>
                <Trash2 size={16} />
                {tr("Excluir registro")}
              </button>
            )}
          </>
        )}
      </div>
      {tab !== "workflow" && (
        <footer className="context-footer">
          {!lead.in_pipeline ? (
            <button
              className="button primary"
              disabled={busy}
              onClick={() => onMove("discovered")}
            >
              <Plus size={17} />
              {tr("Salvar oportunidade")}
            </button>
          ) : environment === "manage" && lead.stage !== "won" ? (
            <button className="button primary" onClick={onSale}>
              <Check size={17} />
              {tr("Registrar venda")}
            </button>
          ) : (
            <button className="button primary" onClick={onManage}>
              {tr(lead.stage === "won" ? "Abrir cliente" : "Abrir negociação")}
              <ArrowUpRight size={17} />
            </button>
          )}
          <span>
            {lead.demo
              ? tr("Exemplo")
              : lead.in_pipeline
                ? stageLabel(lead.stage)
                : tr("Só no Radar")}
          </span>
        </footer>
      )}
    </dialog>
  );
}
