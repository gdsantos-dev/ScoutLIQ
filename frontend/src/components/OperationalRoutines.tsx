import { tr } from "../i18n";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Modal } from "./UI";

type Config = {
  objective: "prospect" | "refresh";
  interval_hours: number;
  task_limit: number;
  daily_task_limit: number;
  operation_limit: number;
  daily_operation_limit: number;
  page_limit: number;
  candidate_limit: number;
  investigation_limit: number;
  cooldown_days: number;
  duration_minutes: number;
  max_runs: number;
  research_mode: "web" | "deep";
};
type Run = {
  id: string;
  status: string;
  reason: string;
  started_at: number;
  search_id: string | null;
  result: Record<string, number>;
  usage: {
    tasks: number;
    operations: { provider: string; state: string; count: number }[];
  };
};
type Routine = {
  id: string;
  name: string;
  version: number;
  state: string;
  reason: string;
  next_at: number | null;
  last_at: number | null;
  config: Config | null;
  runs: Run[];
};
type Status = {
  worker: { status: string };
  mode: string;
  tasks: { own: number; global_used: number; limit: number };
  operations: {
    own: number;
    global_used: number;
    limit: number;
    providers: { provider: string; used: number; limit: number }[];
  };
};
const defaults: Config = {
  objective: "prospect",
  interval_hours: 24,
  task_limit: 20,
  daily_task_limit: 40,
  operation_limit: 100,
  daily_operation_limit: 150,
  page_limit: 3,
  candidate_limit: 100,
  investigation_limit: 15,
  cooldown_days: 7,
  duration_minutes: 60,
  max_runs: 30,
  research_mode: "web",
};
const states: Record<string, string> = {
  disabled: "Não configurada",
  active: "Ativa",
  paused: "Pausada",
  cancelled: "Cancelada",
  completed: "Concluída",
  partial: "Resultado parcial",
  blocked: "Revisão necessária",
  running: "Em execução",
  skipped: "Não executada",
};
const date = (value: number | null) =>
  value ? new Date(value * 1000).toLocaleString("pt-BR") : "—";
const limits: [keyof Config, string, number, number][] = [
  ["task_limit", "Tarefas por execução", 1, 100],
  ["daily_task_limit", "Tarefas por dia", 1, 200],
  ["operation_limit", "Operações de rede por execução", 1, 500],
  ["daily_operation_limit", "Operações de rede por dia", 1, 1000],
  ["page_limit", "Páginas de descoberta", 1, 12],
  ["candidate_limit", "Candidatas por execução", 25, 600],
  ["investigation_limit", "Investigações por execução", 0, 50],
  ["cooldown_days", "Reinvestigar após (dias)", 1, 90],
  ["duration_minutes", "Prazo da execução (minutos)", 15, 120],
  ["max_runs", "Limite total de execuções", 1, 365],
];

function ConfigurationHistory({
  details,
}: {
  details: Record<string, unknown>;
}) {
  type Snapshot = {
    limits?: Config;
    intent?: { query?: string };
    provider?: string;
  };
  const before = details.before as Snapshot | undefined,
    after = details.after as Snapshot | undefined;
  const fields: [keyof Config, string][] = [
    ["objective", "Objetivo"],
    ["interval_hours", "Frequência (horas)"],
    ["research_mode", "Profundidade"],
    ...limits.map(([key, label]): [keyof Config, string] => [key, label]),
  ];
  const display = (value: unknown) =>
    (
      ({
        prospect: "Novas oportunidades",
        refresh: "Investigações vencidas",
        web: "Análise inicial",
        deep: "Auditoria profunda",
      }) as Record<string, string>
    )[String(value)] || String(value ?? "—");
  return (
    <div className="routine-history-data">
      <p>{after?.intent?.query}</p>
      <p>Fonte: {after?.provider || "Não configurada"}</p>
      <table>
        <thead>
          <tr>
            <th>Configuração</th>
            <th>Antes</th>
            <th>Depois</th>
          </tr>
        </thead>
        <tbody>
          {fields.map(([key, label]) => (
            <tr key={key}>
              <th scope="row">{label}</th>
              <td>{display(before?.limits?.[key])}</td>
              <td>{display(after?.limits?.[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function OperationalRoutines({
  onOpenSearch,
}: {
  onOpenSearch: (id: string) => void;
}) {
  const [rows, setRows] = useState<Routine[]>([]),
    [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState<Routine | null>(null),
    [draft, setDraft] = useState<Config>(defaults);
  const [history, setHistory] = useState<{
    name: string;
    events: { action: string; at: number; details: Record<string, unknown> }[];
  } | null>(null);
  async function load() {
    const [next, info] = await Promise.all([
      api<Routine[]>("/operations/routines"),
      api<Status>("/operations/status"),
    ]);
    setRows(next);
    setStatus(info);
    setLoaded(true);
  }
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        if (active) await load();
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  async function act(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function save(enabled: boolean) {
    if (!editing) return;
    await api(`/operations/routines/${editing.id}/configuration`, "PUT", {
      version: editing.version,
      enabled,
      config: draft,
    });
    setEditing(null);
    setNotice(
      enabled
        ? "Rotina ativada para a próxima execução programada."
        : "Configuração salva; rotina pausada.",
    );
  }
  async function control(row: Routine, action: string) {
    await api(`/operations/routines/${row.id}/control`, "POST", {
      version: row.version,
      action,
    });
    setNotice(
      action === "run_now"
        ? "Execução agendada. Os limites continuam valendo."
        : "Estado da rotina atualizado.",
    );
  }
  return (
    <section
      className="operational-routines panel"
      aria-label="Rotinas de pesquisa"
    >
      <div className="routine-heading">
        <h2>Rotinas de pesquisa</h2>
        <button
          className="button"
          disabled={busy}
          onClick={() => void act(load)}
        >
          Atualizar rotinas
        </button>
      </div>
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {status && (
        <>
          <p role="status">
            {status.mode !== "worker"
              ? "Execução recorrente indisponível no modo atual."
              : status.worker.status === "ok"
                ? "Executor disponível."
                : "Executor indisponível. As rotinas ficam aguardando o serviço."}
          </p>
          <details>
            <summary>Consumo de hoje (UTC)</summary>
            <p>
              {status.tasks.own} tarefas e {status.operations.own} operações de
              rede desta conta.
            </p>
            <p>
              Limites compartilhados: {status.tasks.global_used}/
              {status.tasks.limit} tarefas · {status.operations.global_used}/
              {status.operations.limit} operações.
            </p>
            <ul>
              {status.operations.providers.map((p) => (
                <li key={p.provider}>
                  {p.provider}: {p.used}/{p.limit} operações
                </li>
              ))}
            </ul>
            <p>
              Custo monetário não informado pelos provedores. Operações não
              equivalem a unidades faturadas.
            </p>
          </details>
        </>
      )}
      {!loaded && !error && <p>Carregando rotinas…</p>}
      {loaded && !rows.length && (
        <p>
          Salve uma busca no <a href="#radar">Radar</a> para configurar a
          frequência e os limites.
        </p>
      )}
      {rows.map((row) => (
        <article className="routine-row" key={row.id} aria-label={row.name}>
          <div>
            <h3>{row.name}</h3>
            <p>
              {states[row.state] || row.state} · Próxima: {date(row.next_at)} ·
              Última: {date(row.last_at)}
            </p>
            {row.reason && <p>{row.reason}</p>}
            {row.runs[0] && (
              <p className="routine-result">
                {tr("Último resultado")}:{" "}
                {tr(states[row.runs[0].status] || row.runs[0].status)}
                {row.runs[0].reason ? ` · ${row.runs[0].reason}` : ""}
              </p>
            )}
          </div>
          <div className="routine-actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => {
                setEditing(row);
                setDraft(row.config || defaults);
                setError("");
              }}
            >
              Configurar rotina
            </button>
            {row.state === "active" && (
              <>
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => void act(() => control(row, "run_now"))}
                >
                  Agendar agora
                </button>
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => void act(() => control(row, "pause"))}
                >
                  Pausar rotina
                </button>
              </>
            )}
            {row.state === "paused" && row.config && (
              <button
                className="button"
                disabled={busy}
                onClick={() => void act(() => control(row, "resume"))}
              >
                Retomar rotina
              </button>
            )}
            {["active", "paused", "blocked"].includes(row.state) && (
              <button
                className="button"
                disabled={busy}
                onClick={() => void act(() => control(row, "cancel"))}
              >
                Cancelar rotina
              </button>
            )}
            {row.config && (
              <button
                className="button"
                disabled={busy}
                onClick={() =>
                  void act(async () =>
                    setHistory({
                      name: row.name,
                      events: await api(
                        `/operations/routines/${row.id}/history`,
                      ),
                    }),
                  )
                }
              >
                Histórico da rotina
              </button>
            )}
          </div>
          {!!row.runs.length && (
            <details>
              <summary>Execuções recentes ({row.runs.length})</summary>
              {row.runs.map((run) => (
                <div key={run.id} className="routine-run">
                  <strong>{states[run.status] || run.status}</strong> ·{" "}
                  {date(run.started_at)}
                  <p>
                    {run.reason ||
                      (run.status === "running"
                        ? "Trabalho em andamento dentro dos limites configurados."
                        : run.status === "paused"
                          ? "Execução pausada pelo operador."
                          : "Execução encerrada; resultados preservados.")}
                  </p>
                  <p>
                    {run.usage.tasks} tarefas ·{" "}
                    {run.usage.operations.reduce((n, p) => n + p.count, 0)}{" "}
                    operações de rede
                    {typeof run.result.qualified === "number"
                      ? ` · ${run.result.qualified} qualificadas · ${run.result.investigated} investigadas`
                      : typeof run.result.done === "number"
                        ? ` · ${run.result.done} investigações concluídas`
                        : ""}
                  </p>
                  {run.search_id && (
                    <button
                      className="button"
                      onClick={() =>
                        run.search_id && onOpenSearch(run.search_id)
                      }
                    >
                      Ver resultados
                    </button>
                  )}
                </div>
              ))}
            </details>
          )}
        </article>
      ))}
      {editing && (
        <Modal
          title={`Configurar rotina: ${editing.name}`}
          onClose={() => setEditing(null)}
          className="routine-config"
          wide
        >
          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void act(() => save(true));
            }}
          >
            <label>
              Objetivo
              <select
                value={draft.objective}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    objective: e.target.value as Config["objective"],
                  })
                }
              >
                <option value="prospect">Descobrir novas oportunidades</option>
                <option value="refresh">
                  Atualizar investigações vencidas
                </option>
              </select>
            </label>
            <label>
              Frequência
              <select
                value={draft.interval_hours}
                onChange={(e) =>
                  setDraft({ ...draft, interval_hours: Number(e.target.value) })
                }
              >
                <option value={24}>Diária (a cada 24 horas)</option>
                <option value={168}>Semanal</option>
                <option value={720}>A cada 30 dias</option>
              </select>
            </label>
            <label>
              Profundidade
              <select
                value={draft.research_mode}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    research_mode: e.target.value as Config["research_mode"],
                  })
                }
              >
                <option value="web">Identificação e análise inicial</option>
                <option value="deep">Auditoria profunda de páginas</option>
              </select>
            </label>
            <div className="routine-limit-fields">
              {limits.map(([key, label, min, max]) => (
                <label key={key}>
                  {label}
                  <input
                    type="number"
                    required
                    min={min}
                    max={max}
                    value={draft[key]}
                    onChange={(e) =>
                      setDraft({ ...draft, [key]: Number(e.target.value) })
                    }
                  />
                </label>
              ))}
            </div>
            <p>
              A ativação autoriza pesquisa e investigação dentro destes limites.
              Não autoriza envio de mensagens.
            </p>
            <div className="routine-actions">
              <button type="submit" className="button primary" disabled={busy}>
                Ativar rotina
              </button>
              <button
                type="button"
                className="button"
                disabled={busy}
                onClick={() => void act(() => save(false))}
              >
                Salvar pausada
              </button>
            </div>
          </form>
        </Modal>
      )}
      {history && (
        <Modal
          title={`Histórico: ${history.name}`}
          onClose={() => setHistory(null)}
        >
          {history.events.map((e, i) => (
            <div key={i}>
              <p>
                {(
                  {
                    configure: "Configuração registrada",
                    scheduled: "Execução agendada",
                    pause: "Rotina pausada",
                    resume: "Rotina retomada",
                    cancel: "Rotina cancelada",
                    run_now: "Execução solicitada",
                  } as Record<string, string>
                )[e.action] || e.action}{" "}
                · {date(e.at)}
              </p>
              {e.action === "configure" && (
                <details>
                  <summary>Critérios e limites registrados</summary>
                  <ConfigurationHistory details={e.details} />
                </details>
              )}
            </div>
          ))}
          {!history.events.length && <p>Nenhuma alteração registrada.</p>}
        </Modal>
      )}
    </section>
  );
}
