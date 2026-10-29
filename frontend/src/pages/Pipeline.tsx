import { useMemo, useState } from "react";
import AbsorptionDialog from "../components/AbsorptionDialog";
import CommercialQueue from "../components/CommercialQueue";
import {
  ArrowUpRight,
  CalendarClock,
  GripVertical,
  Plus,
  Search,
} from "lucide-react";
import { tr } from "../i18n";
import { normalizeSearch } from "../search";
import type { Lead, Stage } from "../types";
import { activeLocale, inputDate, money, stages } from "../types";
import { Empty, PageHead } from "../components/UI";
import { SmartSelect } from "../components/Primitives";

export default function Pipeline({
  leads,
  onSelect,
  onMove,
  onAdd,
  onAbsorbed,
  busy,
  timezone,
  storageKey,
}: {
  leads: Lead[];
  onSelect: (lead: Lead) => void;
  onMove: (lead: Lead, stage: Stage) => void;
  onAdd: () => void;
  onAbsorbed: () => Promise<void>;
  busy: boolean;
  timezone: string;
  storageKey: string;
}) {
  const [followupOpen,setFollowupOpen]=useState(false);
  const [query, setQuery] = useState("");
  const [absorptionOpen, setAbsorptionOpen] = useState(false);
  const [stageFilter, setStageFilter] = useState<Stage | "open">("open");
  const [onlyDue, setOnlyDue] = useState(false);
  const [over, setOver] = useState<Stage | null>(null);
  const today = inputDate(timezone);
  const pipeline = leads.filter((lead) => lead.in_pipeline);
  const open = pipeline.filter((lead) => !["won", "lost"].includes(lead.stage));
  const due = (lead: Lead) =>
    Boolean(lead.next_action_on && lead.next_action_on <= today);
  const items = useMemo(
    () =>
      pipeline
        .filter(
          (lead) =>
            (stageFilter === "open"
              ? !["won", "lost"].includes(lead.stage)
              : lead.stage === stageFilter) &&
            (!onlyDue || due(lead)) &&
            normalizeSearch(
              `${lead.name} ${lead.city} ${lead.category} ${lead.next_action}`,
            ).includes(normalizeSearch(query)),
        )
        .sort(
          (a, b) =>
            (a.next_action_on || "9999").localeCompare(
              b.next_action_on || "9999",
            ) || b.score.value - a.score.value,
        ),
    [pipeline, query, stageFilter, onlyDue, today],
  );
  const totals = open.reduce<Record<string, number>>((total, lead) => {
    total[lead.potential_currency] =
      (total[lead.potential_currency] || 0) + lead.potential_cents;
    return total;
  }, {});
  const potential =
    Object.entries(totals)
      .filter(([, value]) => value > 0)
      .map(([currency, value]) => money(value, currency as "BRL" | "USD"))
      .join(" · ") || "—";
  const actionDate = (date: string | null) =>
    !date
      ? tr("Sem data")
      : date === today
        ? tr("Hoje")
        : new Date(date + "T12:00:00").toLocaleDateString(activeLocale(), {
            day: "2-digit",
            month: "short",
          });
  return (
    <div className="negotiations-workspace">
      <PageHead title={tr("Negociações")}>
        <button className="button" aria-pressed={followupOpen} onClick={()=>setFollowupOpen(!followupOpen)}>{followupOpen?'Voltar às negociações':'Acompanhamento comercial'}</button>
        <button className="button" onClick={() => setAbsorptionOpen(true)}>Absorver pesquisa</button>
        <button className="button primary" onClick={onAdd}>
          <Plus size={17} />
          {tr("Nova negociação")}
        </button>
      </PageHead>
      {followupOpen?<CommercialQueue storageKey={storageKey} initialFollowup onOpenLead={onSelect} onLeadUpdated={()=>void onAbsorbed()}/>:<>
      <div className="negotiation-overview">
        <div>
          <strong>{open.length}</strong>
          <span>{tr("em andamento")}</span>
        </div>
        <div>
          <span>{tr("Potencial em aberto")}</span>
          <b>{potential}</b>
        </div>
        <button
          className={onlyDue ? "selected" : ""}
          aria-pressed={onlyDue}
          onClick={() => setOnlyDue((value) => !value)}
        >
          <CalendarClock size={17} />
          {tr("Ações para hoje")}
          <b>{open.filter(due).length}</b>
        </button>
      </div>
      <div
        className="negotiation-stages"
        role="group"
        aria-label={tr("Etapas do pipeline")}
      >
        <button
          aria-pressed={stageFilter === "open"}
          onClick={() => setStageFilter("open")}
        >
          {tr("Em andamento")}
          <span>{open.length}</span>
        </button>
        {stages.map((stage) => (
          <button
            key={stage.id}
            aria-pressed={stageFilter === stage.id}
            className={over === stage.id ? "drop-target" : ""}
            onClick={() => setStageFilter(stage.id)}
            onDragOver={(event) => {
              event.preventDefault();
              if (!busy) setOver(stage.id);
            }}
            onDragLeave={() => setOver(null)}
            onDrop={(event) => {
              event.preventDefault();
              setOver(null);
              const lead = leads.find(
                (item) => item.id === event.dataTransfer.getData("text/plain"),
              );
              if (!busy && lead && lead.stage !== stage.id)
                onMove(lead, stage.id);
            }}
          >
            <span className="stage-shape" aria-hidden="true">
              {stage.symbol}
            </span>
            {tr(stage.label)}
            <span>
              {pipeline.filter((lead) => lead.stage === stage.id).length}
            </span>
          </button>
        ))}
      </div>
      <div className="negotiation-tools">
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label={tr("Buscar negociação")}
            placeholder={tr("Empresa, cidade ou próxima ação…")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <span>
          {items.length} {tr("negociações")}
        </span>
      </div>
      <div className="negotiation-column-head" aria-hidden="true">
        <span>{tr("Empresa")}</span>
        <span>{tr("Próxima ação")}</span>
        <span>{tr("Valor potencial")}</span>
        <span>{tr("Etapa")}</span>
      </div>
      <div className="negotiation-list">
        {items.length ? (
          items.map((lead) => (
            <article
              key={lead.id}
              className="negotiation-row"
              draggable={!busy && lead.stage !== "won"}
              onDragStart={(event) =>
                event.dataTransfer.setData("text/plain", lead.id)
              }
            >
              <button
                className="negotiation-company"
                onClick={() => onSelect(lead)}
              >
                <GripVertical size={16} aria-hidden="true" />
                <span>
                  <strong>{lead.name}</strong>
                  <small>
                    {lead.category} · {lead.city}
                  </small>
                </span>
              </button>
              <button
                className={`negotiation-next ${due(lead) ? "due" : ""}`}
                onClick={() => onSelect(lead)}
              >
                <span>{lead.next_action || tr("Definir próxima ação")}</span>
                {lead.next_action && (
                  <small>{actionDate(lead.next_action_on)}</small>
                )}
              </button>
              <span className="negotiation-value">
                {lead.potential_cents
                  ? money(lead.potential_cents, lead.potential_currency)
                  : tr("Valor a definir")}
              </span>
              <div className="negotiation-stage-control">
                <SmartSelect
                  compact
                  ariaLabel={`${tr("Mover")} ${lead.name}`}
                  value={lead.stage}
                  disabled={busy || lead.stage === "won"}
                  onChange={(value) => onMove(lead, value as Stage)}
                  options={stages.map((stage) => ({
                    value: stage.id,
                    label: tr(stage.label),
                  }))}
                />
                <button
                  className="icon-button"
                  aria-label={`${tr("Abrir")} ${lead.name}`}
                  onClick={() => onSelect(lead)}
                >
                  <ArrowUpRight size={18} />
                </button>
              </div>
            </article>
          ))
        ) : (
          <Empty
            title={tr("Nenhuma negociação nesta seleção")}
            action={
              <button
                className="button"
                onClick={() => {
                  setOnlyDue(false);
                  setQuery("");
                  setStageFilter("open");
                }}
              >
                {tr("Limpar filtros")}
              </button>
            }
          />
        )}
      </div>
      </>}
      {absorptionOpen && <AbsorptionDialog onClose={() => setAbsorptionOpen(false)} onImported={onAbsorbed} />}
    </div>
  );
}
