import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  Plus,
  Target,
  Trash2,
} from "lucide-react";
import { api } from "../api";
import { tr } from "../i18n";
import type {
  Campaign,
  Lead,
  OutcomeInsights,
  RadarSavedSearch,
} from "../types";
import { money, stageLabel } from "../types";
import { Empty, ErrorText, Field, PageHead } from "../components/UI";
import { SmartSelect } from "../components/Primitives";

const statusOptions = [
  { value: "active", label: "Ativa" },
  { value: "paused", label: "Pausada" },
  { value: "finished", label: "Encerrada" },
];

export default function Campaigns({
  leads,
  onSelect,
}: {
  leads: Lead[];
  onSelect: (lead: Lead) => void;
}) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [savedSearches, setSavedSearches] = useState<RadarSavedSearch[]>([]);
  const [insights, setInsights] = useState<OutcomeInsights | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    new URLSearchParams(location.hash.split("?")[1] || "").get("campaign"),
  );
  const [members, setMembers] = useState<Lead[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sourceSearch, setSourceSearch] = useState("");
  const [addLeadId, setAddLeadId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const selected =
    campaigns.find((item) => item.id === selectedId) ?? campaigns[0] ?? null;
  const memberIds = useMemo(
    () => new Set(members.map((lead) => lead.id)),
    [members],
  );
  const availableLeads = useMemo(
    () => leads.filter((lead) => !memberIds.has(lead.id) && !lead.demo),
    [leads, memberIds],
  );

  async function load() {
    setError("");
    try {
      const [campaignData, searchData, insightData] = await Promise.all([
        api<Campaign[]>("/campaigns"),
        api<RadarSavedSearch[]>("/radar/saved-searches"),
        api<OutcomeInsights>("/insights/outcomes"),
      ]);
      setCampaigns(campaignData);
      setSavedSearches(searchData);
      setInsights(insightData);
      setSelectedId((current) =>
        current && campaignData.some((item) => item.id === current)
          ? current
          : (campaignData[0]?.id ?? null),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    const selectFromHash = () => {
      const id = new URLSearchParams(location.hash.split("?")[1] || "").get(
        "campaign",
      );
      if (id) {
        setSelectedId(id);
        void load();
      }
    };
    window.addEventListener("hashchange", selectFromHash);
    return () => window.removeEventListener("hashchange", selectFromHash);
  }, []);

  useEffect(() => {
    if (!selected?.id) {
      setMembers([]);
      return;
    }
    let alive = true;
    api<Lead[]>(`/campaigns/${selected.id}/leads`)
      .then((data) => {
        if (alive) setMembers(data);
      })
      .catch((err) => {
        if (alive) setError((err as Error).message);
      });
    return () => {
      alive = false;
    };
  }, [selected?.id, selected?.updated_at]);

  async function createCampaign() {
    if (!name.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const created = await api<Campaign>("/campaigns", "POST", {
        name: name.trim(),
        description: description.trim(),
        status: "active",
        source_saved_search_id: sourceSearch || null,
      });
      await load();
      setSelectedId(created.id);
      setName("");
      setDescription("");
      setSourceSearch("");
      setShowCreate(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function updateStatus(value: string) {
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<Campaign>(`/campaigns/${selected.id}`, "PUT", {
        name: selected.name,
        description: selected.description,
        status: value,
        source_saved_search_id: selected.source_saved_search_id,
        version: selected.version,
      });
      setCampaigns((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addMember() {
    if (!selected || !addLeadId || busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<Campaign>(
        `/campaigns/${selected.id}/leads`,
        "POST",
        { lead_ids: [addLeadId], source: "manual" },
      );
      setCampaigns((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setMembers(await api<Lead[]>(`/campaigns/${selected.id}/leads`));
      setAddLeadId("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeMember(leadId: string) {
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    try {
      await api(`/campaigns/${selected.id}/leads/${leadId}`, "DELETE");
      setMembers((current) => current.filter((lead) => lead.id !== leadId));
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const totalMembers = campaigns.reduce(
    (sum, item) => sum + item.metrics.members,
    0,
  );
  const attributedSales = campaigns.reduce(
    (sum, item) => sum + item.metrics.attributed_sales,
    0,
  );

  return (
    <>
      <PageHead title={tr("Campanhas")} eyebrow={tr("AQUISIÇÃO")}>
        <button
          className="button primary"
          type="button"
          onClick={() => setShowCreate((value) => !value)}
        >
          <Plus size={16} />
          {tr("Nova campanha")}
        </button>
      </PageHead>
      <div className="campaign-summary-line">
        <span>
          <Target size={15} />{" "}
          {campaigns.filter((item) => item.status === "active").length}{" "}
          {tr("ativas")}
        </span>
        <span>
          {totalMembers} {tr("empresas em campanhas")}
        </span>
        <span>
          {attributedSales} {tr("vendas atribuídas")}
        </span>
      </div>
      <ErrorText error={error} />

      {showCreate && (
        <section className="panel campaign-create-panel">
          <div className="campaign-create-copy">
            <span className="eyebrow">{tr("NOVA CAMPANHA")}</span>
            <h2>
              {tr("Agrupe uma estratégia e acompanhe o que virou receita")}
            </h2>
          </div>
          <div className="campaign-create-grid">
            <Field label={tr("Nome")}>
              <input
                value={name}
                maxLength={120}
                onChange={(e) => setName(e.target.value)}
                placeholder={tr("Ex.: Clínicas sem site · Recife")}
              />
            </Field>
            <Field label={tr("Origem opcional")}>
              <SmartSelect
                value={sourceSearch}
                onChange={setSourceSearch}
                options={[
                  { value: "", label: tr("Sem busca vinculada") },
                  ...savedSearches.map((item) => ({
                    value: item.id,
                    label: item.name,
                  })),
                ]}
              />
            </Field>
            <Field label={tr("Descrição")} className="span-2">
              <input
                value={description}
                maxLength={2000}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={tr("Hipótese, nicho ou abordagem desta campanha")}
              />
            </Field>
          </div>
          <div className="form-actions">
            <button
              className="button"
              type="button"
              onClick={() => setShowCreate(false)}
            >
              {tr("Cancelar")}
            </button>
            <button
              className="button primary"
              type="button"
              disabled={busy || !name.trim()}
              onClick={() => void createCampaign()}
            >
              {tr("Criar campanha")}
            </button>
          </div>
        </section>
      )}

      {campaigns.length === 0 ? (
        <Empty
          title={tr("Nenhuma campanha criada")}
          description={tr(
            "Campanhas ligam uma busca ou grupo de empresas ao resultado comercial real, sem misturar atribuição com Opportunity Score.",
          )}
        />
      ) : (
        <div className="campaign-workspace">
          <aside className="campaign-list" aria-label={tr("Campanhas")}>
            {campaigns.map((item) => (
              <button
                type="button"
                className={`campaign-list-row ${selected?.id === item.id ? "active" : ""}`}
                key={item.id}
                onClick={() => setSelectedId(item.id)}
              >
                <span>
                  <strong>{item.name}</strong>
                  <small>
                    {tr(
                      statusOptions.find(
                        (option) => option.value === item.status,
                      )?.label ?? item.status,
                    )}
                  </small>
                </span>
                <b>{item.metrics.members}</b>
              </button>
            ))}
          </aside>

          {selected && (
            <section className="panel campaign-detail">
              <div className="campaign-detail-head">
                <div>
                  <span className="eyebrow">{tr("CAMPANHA")}</span>
                  <h2>{selected.name}</h2>
                  {selected.description && <p>{selected.description}</p>}
                </div>
                <SmartSelect
                  ariaLabel={tr("Status da campanha")}
                  value={selected.status}
                  onChange={(value) => void updateStatus(value)}
                  options={statusOptions.map((item) => ({
                    value: item.value,
                    label: tr(item.label),
                  }))}
                />
              </div>
              <div className="campaign-metrics">
                <span>
                  <em>{tr("Empresas")}</em>
                  <b>{selected.metrics.members}</b>
                </span>
                <span>
                  <em>{tr("Contatadas")}</em>
                  <b>{selected.metrics.contacted}</b>
                </span>
                <span>
                  <em>{tr("Responderam")}</em>
                  <b>{selected.metrics.responded}</b>
                </span>
                <span>
                  <em>{tr("Negociando")}</em>
                  <b>{selected.metrics.negotiating}</b>
                </span>
                <span>
                  <em>{tr("Fechadas")}</em>
                  <b>{selected.metrics.won}</b>
                </span>
              </div>
              <div className="campaign-revenue-line">
                <strong>{tr("Receita atribuída")}</strong>
                <span>
                  {Object.entries(selected.metrics.revenue_by_currency).length
                    ? Object.entries(selected.metrics.revenue_by_currency)
                        .map(([currency, value]) =>
                          money(value, currency as "BRL" | "USD"),
                        )
                        .join(" · ")
                    : "—"}
                </span>
                <small>
                  {tr(
                    "Só vendas explicitamente atribuídas à campanha entram aqui.",
                  )}
                </small>
              </div>
              <div className="campaign-member-toolbar">
                <SmartSelect
                  ariaLabel={tr("Adicionar empresa")}
                  value={addLeadId}
                  onChange={setAddLeadId}
                  options={[
                    { value: "", label: tr("Adicionar empresa…") },
                    ...availableLeads
                      .slice(0, 300)
                      .map((lead) => ({
                        value: lead.id,
                        label: `${lead.name} · ${lead.city}`,
                      })),
                  ]}
                />
                <button
                  className="button"
                  type="button"
                  disabled={!addLeadId || busy}
                  onClick={() => void addMember()}
                >
                  <Plus size={15} />
                  {tr("Adicionar")}
                </button>
              </div>
              <div className="campaign-member-list">
                {members.length ? (
                  members.map((lead) => (
                    <div className="campaign-member-row" key={lead.id}>
                      <button type="button" onClick={() => onSelect(lead)}>
                        <span>
                          <strong>{lead.name}</strong>
                          <small>
                            {lead.category} · {lead.city}
                          </small>
                        </span>
                        <em>{stageLabel(lead.stage)}</em>
                      </button>
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={tr("Remover da campanha")}
                        disabled={busy}
                        onClick={() => void removeMember(lead.id)}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))
                ) : (
                  <p className="muted">
                    {tr("Nenhuma empresa nesta campanha.")}
                  </p>
                )}
              </div>
            </section>
          )}
        </div>
      )}

      <section className="outcome-learning-section">
        <div className="outcome-learning-head">
          <div>
            <span className="eyebrow">{tr("GANHOS × PERDAS")}</span>
            <h2>{tr("Padrões do seu histórico fechado")}</h2>
          </div>
          {insights?.status === "ready" && (
            <span>
              {insights.closed_count} {tr("negociações fechadas")}
            </span>
          )}
        </div>
        {!insights || insights.status === "insufficient" ? (
          <div className="panel outcome-insufficient">
            <strong>{tr("Ainda não há histórico suficiente")}</strong>
            <p>
              {tr(
                "O Scout começa a comparar padrões quando existir uma base mínima de seis negociações fechadas, com pelo menos dois ganhos e duas perdas.",
              )}
            </p>
            <small>
              {insights
                ? `${insights.closed_count}/${insights.minimum_required}`
                : ""}
            </small>
          </div>
        ) : (
          <>
            <div className="outcome-baseline">
              <span>{tr("Taxa histórica observada")}</span>
              <strong>{insights.overall_win_rate}%</strong>
              <small>
                {insights.won_count} {tr("ganhos")} · {insights.lost_count}{" "}
                {tr("perdas")} · {insights.snapshot_coverage}%{" "}
                {tr("com snapshot no momento do desfecho")}
              </small>
            </div>
            <div className="outcome-insight-list">
              {insights.insights.map((item) => (
                <article
                  className="outcome-insight-row"
                  data-direction={item.direction}
                  key={item.key}
                >
                  <span className="outcome-direction">
                    {item.direction === "higher" ? (
                      <ArrowUpRight size={17} />
                    ) : (
                      <ArrowDownRight size={17} />
                    )}
                  </span>
                  <div>
                    <small>{tr(item.dimension)}</small>
                    <strong>{tr(item.value)}</strong>
                    <p>
                      {item.won} {tr("ganhos")} · {item.lost} {tr("perdas")} ·{" "}
                      {Math.abs(item.delta_pp)} p.p. {tr("vs. histórico")}
                    </p>
                  </div>
                  <div className="outcome-insight-stat">
                    <b>{item.win_rate}%</b>
                    <span>
                      {item.delta_pp > 0 ? "+" : ""}
                      {item.delta_pp} p.p.
                    </span>
                    <small>n={item.sample}</small>
                  </div>
                </article>
              ))}
            </div>
            <p className="field-hint">{tr(insights.note || "")}</p>
          </>
        )}
      </section>
    </>
  );
}
