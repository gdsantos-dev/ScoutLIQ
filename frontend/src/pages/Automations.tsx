import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Pause,
  Play,
  Plus,
  Save,
  Trash2,
  Workflow,
  X,
} from "lucide-react";
import { api } from "../api";
import OperationalRoutines from "../components/OperationalRoutines";
import ProspectingPlan from "../components/ProspectingPlan";
import { Confirm, Empty, ErrorText, Field, PageHead } from "../components/UI";
import { SmartSelect } from "../components/Primitives";
import { tr } from "../i18n";
import type {
  AutomationAction,
  AutomationActionType,
  AutomationCondition,
  AutomationConditionField,
  AutomationOperator,
  AutomationRule,
  AutomationStop,
  AutomationTrigger,
  Lead,
  Stage,
} from "../types";

const triggerOptions: { value: AutomationTrigger; label: string }[] = [
  { value: "score_changed", label: "Score alterado" },
  { value: "pipeline_added", label: "Entrou no Pipeline" },
  { value: "stage_changed", label: "Etapa alterada" },
  { value: "watch_change", label: "Mudança na Watchlist" },
  { value: "enriched", label: "Enriquecimento concluído" },
  { value: "manual", label: "Execução manual" },
];

const fieldOptions: { value: AutomationConditionField; label: string }[] = [
  { value: "score", label: "Opportunity Score" },
  { value: "confidence", label: "Confidence Score" },
  { value: "timing", label: "Timing comercial" },
  { value: "service_score", label: "Fit por serviço" },
  { value: "stage", label: "Etapa" },
  { value: "in_pipeline", label: "No Pipeline" },
  { value: "watchlisted", label: "Na Watchlist" },
  { value: "has_phone", label: "Tem telefone" },
  { value: "has_whatsapp", label: "Tem WhatsApp" },
  { value: "has_instagram", label: "Tem Instagram" },
  { value: "website_status", label: "Situação do site" },
  { value: "combined_signal", label: "Sinal combinado" },
];

const operatorOptions: { value: AutomationOperator; label: string }[] = [
  { value: "eq", label: "é" },
  { value: "neq", label: "não é" },
  { value: "gte", label: "maior ou igual" },
  { value: "lte", label: "menor ou igual" },
  { value: "gt", label: "maior que" },
  { value: "lt", label: "menor que" },
  { value: "truthy", label: "sim" },
  { value: "falsy", label: "não" },
  { value: "contains", label: "contém" },
];

const combinedSignalOptions = [
  {
    value: "local_demand_digital_gap",
    label: "Demanda local forte + gap digital",
  },
  {
    value: "growth_without_digital_upgrade",
    label: "Crescimento sem evolução digital",
  },
  { value: "digital_decline_with_demand", label: "Piora digital com demanda" },
  {
    value: "structured_business_digital_gap",
    label: "Operação estruturada + lacuna digital",
  },
  {
    value: "qualified_reachable_fit",
    label: "Fit forte + contato + confiança",
  },
];

const actionOptions: { value: AutomationActionType; label: string }[] = [
  { value: "add_pipeline", label: "Adicionar ao Pipeline" },
  { value: "set_next_action", label: "Criar próxima ação" },
  { value: "add_watchlist", label: "Adicionar à Watchlist" },
  { value: "add_note", label: "Registrar anotação" },
];

const stageOptions: { value: Stage; label: string }[] = [
  { value: "discovered", label: "Encontrado" },
  { value: "contacted", label: "Contatado" },
  { value: "replied", label: "Respondeu" },
  { value: "negotiating", label: "Negociando" },
  { value: "won", label: "Fechado" },
  { value: "lost", label: "Perdido" },
];

const defaultCondition = (): AutomationCondition => ({
  field: "score",
  operator: "gte",
  value: 70,
  service_key: "",
});
const defaultAction = (): AutomationAction => ({
  type: "set_next_action",
  text: "Revisar oportunidade",
  due_days: 0,
});
const defaultStop = (): AutomationStop => ({
  stages: ["won", "lost"],
  max_runs_per_lead: 3,
  stop_if_next_action_exists: false,
});

function conditionSummary(item: AutomationCondition) {
  const field = tr(
    fieldOptions.find((entry) => entry.value === item.field)?.label ??
      item.field,
  );
  const operator = tr(
    operatorOptions.find((entry) => entry.value === item.operator)?.label ??
      item.operator,
  );
  if (item.operator === "truthy" || item.operator === "falsy")
    return `${field} · ${operator}`;
  const extra =
    item.field === "service_score" && item.service_key
      ? ` (${item.service_key})`
      : "";
  return `${field}${extra} · ${operator} ${String(item.value ?? "")}`;
}

function actionSummary(item: AutomationAction) {
  const label = tr(
    actionOptions.find((entry) => entry.value === item.type)?.label ??
      item.type,
  );
  if (item.type === "set_next_action")
    return `${label}: ${item.text}${item.due_days ? ` · +${item.due_days}d` : ""}`;
  if (item.type === "add_note") return `${label}: ${item.text}`;
  return label;
}

export default function Automations({
  leads,
  onOpenSearch,
}: {
  leads: Lead[];
  onOpenSearch: (id: string) => void;
}) {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<AutomationRule | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState<AutomationTrigger>("score_changed");
  const [conditions, setConditions] = useState<AutomationCondition[]>([
    defaultCondition(),
  ]);
  const [actions, setActions] = useState<AutomationAction[]>([defaultAction()]);
  const [stop, setStop] = useState<AutomationStop>(defaultStop());
  const [deleting, setDeleting] = useState<AutomationRule | null>(null);

  const activeCount = useMemo(
    () => rules.filter((rule) => rule.enabled).length,
    [rules],
  );

  async function load() {
    setLoading(true);
    setError("");
    try {
      setRules(await api<AutomationRule[]>("/automations"));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function resetForm() {
    setEditing(null);
    setName("");
    setTrigger("score_changed");
    setConditions([defaultCondition()]);
    setActions([defaultAction()]);
    setStop(defaultStop());
  }

  function openNew() {
    resetForm();
    setShowForm(true);
  }

  function openEdit(rule: AutomationRule) {
    setEditing(rule);
    setName(rule.name);
    setTrigger(rule.trigger);
    setConditions(
      rule.conditions.length
        ? rule.conditions.map((item) => ({ ...item }))
        : [],
    );
    setActions(rule.actions.map((item) => ({ ...item })));
    setStop({ ...rule.stop, stages: [...(rule.stop.stages || [])] });
    setShowForm(true);
  }

  async function saveRule() {
    if (!name.trim() || !actions.length || busy) return;
    setBusy(true);
    setError("");
    try {
      const payload = {
        name: name.trim(),
        enabled: editing?.enabled ?? true,
        trigger,
        conditions,
        actions,
        stop,
        ...(editing ? { version: editing.version } : {}),
      };
      const saved = editing
        ? await api<AutomationRule>(
            `/automations/${editing.id}`,
            "PUT",
            payload,
          )
        : await api<AutomationRule>("/automations", "POST", payload);
      setRules((current) => [
        saved,
        ...current.filter((item) => item.id !== saved.id),
      ]);
      setShowForm(false);
      resetForm();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(rule: AutomationRule) {
    setBusy(true);
    setError("");
    try {
      const updated = await api<AutomationRule>(
        `/automations/${rule.id}/enabled`,
        "PATCH",
        {
          enabled: !rule.enabled,
          version: rule.version,
        },
      );
      setRules((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(rule: AutomationRule) {
    setBusy(true);
    setError("");
    try {
      await api(`/automations/${rule.id}`, "DELETE");
      setRules((current) => current.filter((item) => item.id !== rule.id));
      setDeleting(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function patchCondition(index: number, patch: Partial<AutomationCondition>) {
    setConditions((current) =>
      current.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    );
  }

  function patchAction(index: number, patch: Partial<AutomationAction>) {
    setActions((current) =>
      current.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    );
  }

  return (
    <>
      <PageHead title={tr("Automações")} eyebrow={tr("OPERAÇÃO")}>
        <button className="button primary" type="button" onClick={openNew}>
          <Plus size={16} />
          {tr("Nova automação")}
        </button>
      </PageHead>
      <ProspectingPlan />
      <OperationalRoutines onOpenSearch={onOpenSearch} />

      <div className="automation-summary-line">
        <span>
          <Workflow size={15} /> {activeCount} {tr("ativas")}
        </span>
        <span>
          {rules.length} {tr("regras")}
        </span>
        <span>
          {leads.length} {tr("estabelecimentos disponíveis")}
        </span>
      </div>
      <ErrorText error={error} />

      {showForm && (
        <section className="panel automation-builder">
          <div className="automation-builder-head">
            <div>
              <span className="eyebrow">
                {editing ? tr("EDITAR REGRA") : tr("NOVA REGRA")}
              </span>
              <h2>{editing ? editing.name : tr("Criar automação")}</h2>
            </div>
            <button
              type="button"
              className="icon-button"
              aria-label={tr("Fechar")}
              onClick={() => {
                setShowForm(false);
                resetForm();
              }}
            >
              <X size={18} />
            </button>
          </div>
          <div className="automation-builder-grid">
            <Field label={tr("Nome da automação")}>
              <input
                value={name}
                maxLength={100}
                onChange={(e) => setName(e.target.value)}
                placeholder={tr("Ex.: Prioridade alta → revisar hoje")}
              />
            </Field>
            <Field label={tr("Quando")}>
              <SmartSelect
                value={trigger}
                onChange={(value) => setTrigger(value as AutomationTrigger)}
                options={triggerOptions.map((item) => ({
                  value: item.value,
                  label: tr(item.label),
                }))}
              />
            </Field>
          </div>

          <div className="automation-section">
            <div className="automation-section-head">
              <div>
                <h3>{tr("Condições")}</h3>
                <p>
                  {tr("Todas precisam ser verdadeiras para a regra executar.")}
                </p>
              </div>
              {conditions.length < 4 && (
                <button
                  className="text-link"
                  type="button"
                  onClick={() =>
                    setConditions((current) => [...current, defaultCondition()])
                  }
                >
                  + {tr("Adicionar condição")}
                </button>
              )}
            </div>
            {conditions.length === 0 ? (
              <p className="muted">
                {tr("Sem condições: executa sempre que o gatilho acontecer.")}
              </p>
            ) : (
              <div className="automation-rule-stack">
                {conditions.map((item, index) => (
                  <div
                    className="automation-condition-row"
                    key={`${index}-${item.field}`}
                  >
                    <SmartSelect
                      ariaLabel={tr("Campo da condição")}
                      value={item.field}
                      onChange={(value) =>
                        patchCondition(index, {
                          field: value as AutomationConditionField,
                          service_key:
                            value === "service_score" ? item.service_key : "",
                          ...(value === "combined_signal"
                            ? {
                                operator: "contains",
                                value: combinedSignalOptions[0].value,
                              }
                            : {}),
                        })
                      }
                      options={fieldOptions.map((entry) => ({
                        value: entry.value,
                        label: tr(entry.label),
                      }))}
                    />
                    <SmartSelect
                      ariaLabel={tr("Operador da condição")}
                      value={item.operator}
                      onChange={(value) =>
                        patchCondition(index, {
                          operator: value as AutomationOperator,
                        })
                      }
                      options={operatorOptions.map((entry) => ({
                        value: entry.value,
                        label: tr(entry.label),
                      }))}
                    />
                    {item.operator !== "truthy" &&
                      item.operator !== "falsy" &&
                      (item.field === "stage" ? (
                        <SmartSelect
                          value={String(item.value || "discovered")}
                          onChange={(value) => patchCondition(index, { value })}
                          options={stageOptions.map((entry) => ({
                            value: entry.value,
                            label: tr(entry.label),
                          }))}
                        />
                      ) : item.field === "website_status" ? (
                        <SmartSelect
                          value={String(item.value || "unknown")}
                          onChange={(value) => patchCondition(index, { value })}
                          options={["unknown", "none", "poor", "good"].map(
                            (value) => ({
                              value,
                              label: tr(
                                value === "none"
                                  ? "Sem site"
                                  : value === "poor"
                                    ? "Site com problemas"
                                    : value === "good"
                                      ? "Site adequado"
                                      : "Não verificado",
                              ),
                            }),
                          )}
                        />
                      ) : item.field === "service_score" ? (
                        <div className="automation-service-value">
                          <input
                            aria-label={tr("Serviço")}
                            value={item.service_key}
                            onChange={(e) =>
                              patchCondition(index, {
                                service_key: e.target.value
                                  .replace(/[^a-z0-9_]/g, "")
                                  .slice(0, 50),
                              })
                            }
                            placeholder="site_institucional"
                          />
                          <input
                            aria-label={tr("Valor da condição")}
                            type="number"
                            min={0}
                            max={100}
                            value={Number(item.value ?? 70)}
                            onChange={(e) =>
                              patchCondition(index, {
                                value: Number(e.target.value),
                              })
                            }
                          />
                        </div>
                      ) : item.field === "combined_signal" ? (
                        <SmartSelect
                          value={String(
                            item.value || combinedSignalOptions[0].value,
                          )}
                          onChange={(value) =>
                            patchCondition(index, {
                              value,
                              operator: "contains",
                            })
                          }
                          options={combinedSignalOptions.map((entry) => ({
                            value: entry.value,
                            label: tr(entry.label),
                          }))}
                        />
                      ) : [
                          "in_pipeline",
                          "watchlisted",
                          "has_phone",
                          "has_whatsapp",
                          "has_instagram",
                        ].includes(item.field) ? (
                        <SmartSelect
                          value={String(item.value ?? true)}
                          onChange={(value) =>
                            patchCondition(index, { value: value === "true" })
                          }
                          options={[
                            { value: "true", label: tr("Sim") },
                            { value: "false", label: tr("Não") },
                          ]}
                        />
                      ) : (
                        <input
                          aria-label={tr("Valor da condição")}
                          type="number"
                          min={0}
                          max={100}
                          value={Number(item.value ?? 0)}
                          onChange={(e) =>
                            patchCondition(index, {
                              value: Number(e.target.value),
                            })
                          }
                        />
                      ))}
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={tr("Remover condição")}
                      onClick={() =>
                        setConditions((current) =>
                          current.filter((_, i) => i !== index),
                        )
                      }
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="automation-section">
            <div className="automation-section-head">
              <div>
                <h3>{tr("Ações")}</h3>
                <p>
                  {tr(
                    "Executadas em ordem quando a regra passar pelas condições.",
                  )}
                </p>
              </div>
              {actions.length < 4 && (
                <button
                  className="text-link"
                  type="button"
                  onClick={() =>
                    setActions((current) => [...current, defaultAction()])
                  }
                >
                  + {tr("Adicionar ação")}
                </button>
              )}
            </div>
            <div className="automation-rule-stack">
              {actions.map((item, index) => (
                <div
                  className="automation-action-row"
                  key={`${index}-${item.type}`}
                >
                  <SmartSelect
                    ariaLabel={tr("Tipo de ação")}
                    value={item.type}
                    onChange={(value) =>
                      patchAction(index, {
                        type: value as AutomationActionType,
                      })
                    }
                    options={actionOptions.map((entry) => ({
                      value: entry.value,
                      label: tr(entry.label),
                    }))}
                  />
                  {(item.type === "set_next_action" ||
                    item.type === "add_note") && (
                    <input
                      aria-label={tr("Texto da ação")}
                      value={item.text}
                      maxLength={500}
                      onChange={(e) =>
                        patchAction(index, { text: e.target.value })
                      }
                      placeholder={
                        item.type === "set_next_action"
                          ? tr("Ex.: Ligar para o responsável")
                          : tr("Texto da anotação")
                      }
                    />
                  )}
                  {item.type === "set_next_action" && (
                    <label className="automation-days">
                      <span>{tr("Em dias")}</span>
                      <input
                        type="number"
                        min={0}
                        max={365}
                        value={item.due_days}
                        onChange={(e) =>
                          patchAction(index, {
                            due_days: Number(e.target.value),
                          })
                        }
                      />
                    </label>
                  )}
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={tr("Remover ação")}
                    disabled={actions.length === 1}
                    onClick={() =>
                      setActions((current) =>
                        current.filter((_, i) => i !== index),
                      )
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="automation-section automation-stop-section">
            <div>
              <h3>{tr("Parar quando")}</h3>
              <p>
                {tr(
                  "As condições de parada são verificadas antes de qualquer ação.",
                )}
              </p>
            </div>
            <div className="automation-stop-grid">
              <div className="automation-stop-stages">
                {stageOptions
                  .filter((item) =>
                    ["replied", "negotiating", "won", "lost"].includes(
                      item.value,
                    ),
                  )
                  .map((item) => (
                    <label key={item.value}>
                      <input
                        type="checkbox"
                        checked={stop.stages.includes(item.value)}
                        onChange={(e) =>
                          setStop((current) => ({
                            ...current,
                            stages: e.target.checked
                              ? [...current.stages, item.value]
                              : current.stages.filter(
                                  (stage) => stage !== item.value,
                                ),
                          }))
                        }
                      />
                      {tr(item.label)}
                    </label>
                  ))}
              </div>
              <Field label={tr("Máximo por empresa")}>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={stop.max_runs_per_lead}
                  onChange={(e) =>
                    setStop((current) => ({
                      ...current,
                      max_runs_per_lead: Number(e.target.value),
                    }))
                  }
                />
              </Field>
              <label className="automation-stop-toggle">
                <input
                  type="checkbox"
                  checked={stop.stop_if_next_action_exists}
                  onChange={(e) =>
                    setStop((current) => ({
                      ...current,
                      stop_if_next_action_exists: e.target.checked,
                    }))
                  }
                />
                <span>{tr("Parar se já existir próxima ação")}</span>
              </label>
            </div>
          </div>

          <div className="form-actions automation-form-actions">
            <button
              className="button"
              type="button"
              onClick={() => {
                setShowForm(false);
                resetForm();
              }}
            >
              {tr("Cancelar")}
            </button>
            <button
              className="button primary"
              type="button"
              disabled={busy || !name.trim() || !actions.length}
              onClick={() => void saveRule()}
            >
              <Save size={16} />
              {busy ? tr("Salvando…") : tr("Salvar automação")}
            </button>
          </div>
        </section>
      )}

      {loading ? (
        <div className="panel automation-loading">{tr("Carregando")}</div>
      ) : rules.length === 0 ? (
        <Empty
          title={tr("Nenhuma automação criada")}
          description={tr(
            "Crie regras pequenas e rastreáveis para manter o Pipeline andando sem espalhar lógica pelo produto.",
          )}
          action={
            <button className="button primary" onClick={openNew}>
              <Plus size={16} />
              {tr("Criar primeira automação")}
            </button>
          }
        />
      ) : (
        <section className="automation-list" aria-label={tr("Automações")}>
          {rules.map((rule) => (
            <article
              className={`automation-row ${rule.enabled ? "" : "paused"}`}
              key={rule.id}
            >
              <button
                type="button"
                className="automation-row-main"
                onClick={() => openEdit(rule)}
              >
                <span className="automation-rule-icon">
                  <Workflow size={17} />
                </span>
                <span className="automation-rule-copy">
                  <strong>{rule.name}</strong>
                  <small>
                    {tr(
                      triggerOptions.find((item) => item.value === rule.trigger)
                        ?.label ?? rule.trigger,
                    )}
                    {!rule.enabled && ` · ${tr("Pausada")}`}
                  </small>
                  <span>
                    {rule.conditions.length
                      ? rule.conditions.map(conditionSummary).join(" · ")
                      : tr("Sem condições")}
                  </span>
                  <span>{rule.actions.map(actionSummary).join(" · ")}</span>
                </span>
              </button>
              <div className="automation-row-stop">
                <Activity size={14} />
                <span>
                  {tr("Máx.")} {rule.stop.max_runs_per_lead}/{tr("empresa")}
                </span>
                {!!rule.stop.stages.length && (
                  <span>
                    {tr("Para em")}:{" "}
                    {rule.stop.stages
                      .map((stage) =>
                        tr(
                          stageOptions.find((item) => item.value === stage)
                            ?.label ?? stage,
                        ),
                      )
                      .join(", ")}
                  </span>
                )}
              </div>
              <div className="automation-row-actions">
                <button
                  type="button"
                  className="icon-button"
                  aria-label={rule.enabled ? tr("Pausar") : tr("Ativar")}
                  disabled={busy}
                  onClick={() => void toggle(rule)}
                >
                  {rule.enabled ? <Pause size={16} /> : <Play size={16} />}
                </button>
                <button
                  type="button"
                  className="icon-button"
                  aria-label={tr("Excluir")}
                  disabled={busy}
                  onClick={() => setDeleting(rule)}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      {deleting && (
        <Confirm
          title={tr("Excluir automação?")}
          description={tr(
            "A regra e seu histórico de execuções serão removidos. Isso não desfaz ações já aplicadas aos estabelecimentos.",
          )}
          label={tr("Excluir")}
          onClose={() => setDeleting(null)}
          onConfirm={() => void remove(deleting)}
          busy={busy}
          error={error}
        />
      )}
    </>
  );
}
