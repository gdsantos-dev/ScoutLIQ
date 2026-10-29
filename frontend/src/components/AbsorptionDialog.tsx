import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Modal } from "./UI";
import "./absorption-dialog.css";
type Row = Record<string, unknown> & {
  name?: string;
  city?: string;
  category?: string;
};
type Suggestion = {
  id: string;
  record: Row;
  provider: string;
  reason: string;
  observed_at: number;
};
type Item = {
  lead_id?: string;
  id: string;
  version: number;
  position: number;
  record: Row;
  original: unknown;
  history: unknown[];
  issues: string[];
  suggestions: Suggestion[];
  matches: {
    name: string;
    city: string;
    address: string;
    kind: string;
    reason: string;
  }[];
  status: "ready" | "pending" | "duplicate" | "imported";
  reason: string;
};
type Recovery = {
  id: string;
  status: string;
  error: string;
  processed: number;
  total: number;
  calls: number;
  limit: number;
};
type Batch = {
  id: string;
  version: number;
  payload_hash: string;
  source: string;
  status: string;
  counts: Record<Item["status"], number>;
  items: Item[];
  created_at: number;
  recovery: Recovery | null;
};
type History = Pick<Batch, "id" | "source" | "status" | "created_at">;
type Parsed = {
  headers: { index: number; label: string; field: string }[];
  mapping_required: boolean;
  fields: string[];
  sample: string[][];
};
const fields: Record<string, string> = {
  name: "Empresa",
  category: "Categoria",
  city: "Cidade",
  country: "País",
  state: "Estado",
  district: "Bairro",
  address: "Endereço",
  latitude: "Latitude",
  longitude: "Longitude",
  phone: "Telefone",
  whatsapp: "WhatsApp",
  website: "Site",
  instagram: "Instagram",
  source_url: "URL da fonte",
  source_id: "ID da fonte",
  source_name: "Fonte",
  notes: "Observações",
  contact: "Contato",
  rating: "Nota",
  reviews: "Avaliações",
  claims: "Alegações externas",
};
const primaryFields = [
  "name",
  "category",
  "city",
  "country",
  "state",
  "address",
  "latitude",
  "longitude",
];
const labels = {
  ready: "Pronto",
  pending: "Pendente",
  duplicate: "Duplicado",
  imported: "Absorvido",
};
const states: Record<string, string> = {
  pending: "Na fila do worker",
  running: "Em recuperação",
  paused: "Pausada",
  cancelled: "Cancelada",
  partial: "Interrompida com resultados preservados",
  completed: "Recuperação concluída",
};
export default function AbsorptionDialog({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => Promise<void>;
}) {
  const previewRequest = useRef<{ signature: string; key: string } | null>(
      null,
    ),
    recoveryRequest = useRef<{ signature: string; key: string } | null>(null);
  const [raw, setRaw] = useState(""),
    [source, setSource] = useState("chatgpt"),
    [batch, setBatch] = useState<Batch | null>(null),
    [history, setHistory] = useState<History[]>([]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [parsed, setParsed] = useState<Parsed | null>(null),
    [mapping, setMapping] = useState<Record<string, string>>({});
  const [delimiter, setDelimiter] = useState(""),
    [external, setExternal] = useState(false),
    [limit, setLimit] = useState(20);
  const [editing, setEditing] = useState<string | null>(null),
    [draft, setDraft] = useState<Record<string, string>>({}),
    [reason, setReason] = useState(""),
    [editVersion, setEditVersion] = useState(0);
  const selected = useRef<string | null>(null);
  selected.current = batch?.id || null;
  function received(value: Batch) {
    setBatch(value);
    setHistory((rows) =>
      [
        {
          id: value.id,
          source: value.source,
          status: value.status,
          created_at: value.created_at,
        },
        ...rows.filter((r) => r.id !== value.id),
      ].slice(0, 30),
    );
  }
  useEffect(() => {
    let alive = true;
    api<History[]>("/absorption/batches")
      .then((rows) => {
        if (alive) setHistory(rows);
      })
      .catch(() => {
        if (alive)
          setError(
            "Não foi possível carregar o histórico. Reabra a Absorção para tentar novamente.",
          );
      });
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    if (
      !batch ||
      !["pending", "running"].includes(batch.recovery?.status || "") ||
      busy
    )
      return;
    let alive = true;
    const id = batch.id;
    const timer = window.setInterval(() => {
      void api<Batch>(`/absorption/batches/${id}`)
        .then((value) => {
          if (alive && selected.current === id)
            setBatch((current) =>
              current && value.version >= current.version ? value : current,
            );
        })
        .catch(() => {
          if (alive)
            setError(
              "Não foi possível atualizar o progresso. Use Atualizar lote.",
            );
        });
    }, 2500);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [batch?.id, batch?.recovery?.status, busy]);
  async function perform(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function readFile(file?: File) {
    if (!file) return;
    setError("");
    if (file.size > 48000 || !/\.(json|csv|tsv|txt)$/i.test(file.name)) {
      setError("Use JSON, CSV ou texto UTF-8 de até 48 KB.");
      return;
    }
    try {
      setRaw(
        new TextDecoder("utf-8", { fatal: true }).decode(
          await file.arrayBuffer(),
        ),
      );
      setSource(/\.json$/i.test(file.name) ? "json" : "csv");
      setBatch(null);
      setParsed(null);
      setMapping({});
    } catch {
      setError("Não foi possível ler o arquivo. Salve em UTF-8.");
    }
  }
  async function preview() {
    await perform(async () => {
      const input = { raw, mapping, ...(delimiter ? { delimiter } : {}) };
      const analysis = await api<Parsed>("/absorption/parse", "POST", input);
      setParsed(analysis);
      if (
        analysis.mapping_required ||
        (analysis.headers.length > 0 && !parsed)
      ) {
        setMapping(
          Object.fromEntries(
            analysis.headers.map((h) => [String(h.index), h.field]),
          ),
        );
        return;
      }
      const signature = JSON.stringify({ source, ...input });
      if (previewRequest.current?.signature !== signature)
        previewRequest.current = { signature, key: crypto.randomUUID() };
      received(
        await api<Batch>("/absorption/intake", "POST", {
          ...input,
          source,
          request_key: previewRequest.current.key,
        }),
      );
      setEditing(null);
    });
  }
  const [investigationNotice, setInvestigationNotice] = useState("");
  async function investigateImported() {
    const ids =
      batch?.items
        .filter((item) => item.status === "imported" && item.lead_id)
        .map((item) => item.lead_id!) || [];
    if (!ids.length) return;
    await perform(async () => {
      await api("/investigation/requests", "POST", {
        lead_ids: ids.slice(0, 100),
        request_key: crypto.randomUUID(),
      });
      setInvestigationNotice(
        "Investigação agendada. Acompanhe e revise os resultados no Radar.",
      );
    });
  }
  async function commit() {
    if (!batch) return;
    await perform(async () => {
      const result = await api<Batch>(
        `/absorption/batches/${batch.id}/commit`,
        "POST",
        {
          payload_hash: batch.payload_hash,
          version: batch.version,
          confirm: true,
        },
      );
      received(result);
      if (result.counts.imported) await onImported();
    });
  }
  async function recover() {
    if (!batch) return;
    await perform(async () => {
      const signature = JSON.stringify([
        batch.id,
        external,
        limit,
        batch.recovery?.id,
      ]);
      if (recoveryRequest.current?.signature !== signature)
        recoveryRequest.current = { signature, key: crypto.randomUUID() };
      received(
        await api<Batch>(`/absorption/batches/${batch.id}/recover`, "POST", {
          version: batch.version,
          request_key: recoveryRequest.current.key,
          allow_external: external,
          limit,
        }),
      );
    });
  }
  async function control(action: string) {
    if (!batch?.recovery) return;
    await perform(async () =>
      received(
        await api<Batch>(
          `/absorption/batches/${batch.id}/recovery/${batch.recovery!.id}`,
          "POST",
          { action, version: batch.version },
        ),
      ),
    );
  }
  async function refresh(id: string, recheck = false) {
    await perform(async () => {
      received(
        await api<Batch>(
          `/absorption/batches/${id}${recheck ? "/recheck" : ""}`,
          recheck ? "POST" : "GET",
        ),
      );
      setEditing(null);
    });
  }
  function edit(item: Item) {
    setEditing(item.id);
    setEditVersion(item.version);
    setReason("");
    setDraft(
      Object.fromEntries(
        Object.keys(fields).map((k) => [
          k,
          k === "claims"
            ? JSON.stringify(item.record[k] ?? [])
            : String(item.record[k] ?? ""),
        ]),
      ),
    );
  }
  async function save(item: Item) {
    if (!batch) return;
    await perform(async () => {
      const changes = Object.fromEntries(
        Object.entries(draft).filter(
          ([k, v]) =>
            v !==
            (k === "claims"
              ? JSON.stringify(item.record[k] ?? [])
              : String(item.record[k] ?? "")),
        ),
      );
      if (!Object.keys(changes).length) {
        setEditing(null);
        return;
      }
      received(
        await api<Batch>(
          `/absorption/batches/${batch.id}/items/${item.id}`,
          "PATCH",
          {
            version: editVersion,
            changes: {
              ...changes,
              ...("claims" in changes
                ? { claims: JSON.parse(changes.claims) }
                : {}),
            },
            reason: reason || "Correção manual.",
          },
        ),
      );
      setEditing(null);
    });
  }
  async function decide(item: Item, action: string, suggestion_id = "") {
    if (!batch) return;
    await perform(async () => {
      received(
        await api<Batch>(
          `/absorption/batches/${batch.id}/items/${item.id}/decision`,
          "POST",
          { version: editVersion, action, suggestion_id, reason },
        ),
      );
      setReason("");
      setEditing(null);
    });
  }
  const active = ["pending", "running", "paused"].includes(
    batch?.recovery?.status || "",
  );
  return (
    <Modal
      title="Absorver pesquisa"
      wide
      onClose={onClose}
      className="absorption-dialog"
    >
      <div className="absorption-content">
        <p className="absorption-instructions">
          Cole JSON ou uma tabela com cabeçalhos. Confira os registros antes de
          incluí-los no Radar.
        </p>
        <div className="absorption-controls">
          <label className="field">
            <span>Origem</span>
            <select
              disabled={busy}
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setBatch(null);
              }}
            >
              <option value="chatgpt">Pesquisa no ChatGPT</option>
              <option value="json">JSON / outra pesquisa</option>
              <option value="csv">Planilha / CSV</option>
              <option value="manual">Manual</option>
            </select>
          </label>
          <label className="field">
            <span>Arquivo JSON, CSV ou texto</span>
            <input
              type="file"
              disabled={busy}
              accept=".json,.csv,.tsv,.txt"
              onChange={(e) => void readFile(e.target.files?.[0])}
            />
          </label>
        </div>
        <label className="field">
          <span>Empresas (JSON ou tabela)</span>
          <textarea
            disabled={busy}
            spellCheck={false}
            value={raw}
            rows={5}
            onChange={(e) => {
              setRaw(e.target.value);
              setBatch(null);
              setParsed(null);
              setMapping({});
            }}
          />
        </label>
        <div className="absorption-controls">
          <p className="field-hint">
            Até 50 empresas e 48 KB. Dados externos permanecem não verificados.
          </p>
          <label className="field">
            <span>Separador</span>
            <select
              value={delimiter}
              disabled={busy}
              onChange={(e) => {
                setDelimiter(e.target.value);
                setParsed(null);
                setMapping({});
              }}
            >
              <option value="">Automático</option>
              <option value=",">Vírgula</option>
              <option value=";">Ponto e vírgula</option>
              <option value={"\t"}>Tabulação</option>
              <option value="|">Barra vertical</option>
            </select>
          </label>
        </div>
        {parsed && parsed.headers.length > 0 && !batch && (
          <fieldset className="absorption-mapping">
            <legend>Mapear colunas</legend>
            {parsed.headers.map((h) => (
              <label className="field" key={h.index}>
                <span>{h.label || `Coluna ${h.index + 1}`}</span>
                <small>{parsed.sample[0]?.[h.index]}</small>
                <select
                  aria-label={`Destino de ${h.label || h.index + 1}`}
                  value={mapping[h.index] || ""}
                  disabled={busy}
                  onChange={(e) =>
                    setMapping((m) => ({ ...m, [h.index]: e.target.value }))
                  }
                >
                  <option value="">Escolha um campo</option>
                  <option value="ignore">Ignorar</option>
                  {parsed.fields.map((f) => (
                    <option key={f} value={f}>
                      {fields[f] || f}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </fieldset>
        )}
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <div className="absorption-actions">
          <button
            type="button"
            className="button"
            disabled={busy || !raw.trim()}
            onClick={() => void preview()}
          >
            {busy
              ? "Processando…"
              : parsed?.headers.length && !batch
                ? "Conferir mapeamento"
                : "Analisar lote"}
          </button>
          {batch && batch.counts.ready > 0 && (
            <button
              type="button"
              className="button primary"
              disabled={busy}
              onClick={() => void commit()}
            >
              Confirmar {batch.counts.ready} elegíveis
            </button>
          )}
        </div>
        {batch && batch.counts.imported > 0 && (
          <div className="absorption-actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => void investigateImported()}
            >
              Investigar empresas absorvidas
            </button>
            {investigationNotice && <p role="status">{investigationNotice}</p>}
          </div>
        )}
        {batch && (
          <section
            className="absorption-preview"
            aria-label="Resultado da absorção"
          >
            <div className="absorption-summary" role="status">
              <strong>
                {batch.status === "committed"
                  ? "Lote concluído"
                  : batch.status === "partial"
                    ? "Lote parcialmente absorvido"
                    : "Prévia do lote"}
              </strong>
              <span>
                {batch.counts.ready} prontos · {batch.counts.pending} pendentes
                · {batch.counts.duplicate} duplicados · {batch.counts.imported}{" "}
                absorvidos
              </span>
            </div>
            <div className="absorption-recovery">
              {batch.counts.pending > 0 && !active && (
                <>
                  <label className="absorption-consent">
                    <input
                      type="checkbox"
                      checked={external}
                      disabled={busy}
                      onChange={(e) => setExternal(e.target.checked)}
                    />{" "}
                    Permitir consultas à fonte configurada
                  </label>
                  {external && (
                    <label className="field">
                      <span>Limite de reservas externas (até 50 por lote)</span>
                      <input
                        type="number"
                        min={1}
                        max={50}
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                      />
                    </label>
                  )}
                  <button
                    className="button"
                    disabled={busy || limit < 1 || limit > 50}
                    onClick={() => void recover()}
                  >
                    Completar pendências
                  </button>
                </>
              )}
              {batch.recovery && (
                <div role="status">
                  <strong>
                    {states[batch.recovery.status] || batch.recovery.status}
                  </strong>
                  <p>
                    {batch.recovery.processed} de {batch.recovery.total}{" "}
                    registros · {batch.recovery.calls}/{batch.recovery.limit}{" "}
                    reservas externas
                  </p>
                  {batch.recovery.error && <p>{batch.recovery.error}</p>}
                </div>
              )}
              <div className="absorption-actions">
                {active && (
                  <>
                    {batch.recovery?.status === "paused" ? (
                      <button
                        className="button"
                        disabled={busy}
                        onClick={() => void control("resume")}
                      >
                        Retomar recuperação
                      </button>
                    ) : (
                      <button
                        className="button"
                        disabled={busy}
                        onClick={() => void control("pause")}
                      >
                        Pausar recuperação
                      </button>
                    )}
                    <button
                      className="button"
                      disabled={busy}
                      onClick={() => void control("cancel")}
                    >
                      Cancelar recuperação
                    </button>
                  </>
                )}
                <button
                  className="button ghost"
                  disabled={busy}
                  onClick={() => void refresh(batch.id, true)}
                >
                  Atualizar lote
                </button>
              </div>
            </div>
            <div className="absorption-list" role="list">
              {batch.items.map((item) => (
                <div key={item.id} className="absorption-item" role="listitem">
                  <div>
                    <strong>
                      {item.record.name || `Registro ${item.position + 1}`}
                    </strong>
                    <small>
                      {item.record.city || "Cidade pendente"} ·{" "}
                      {item.record.category || "Categoria pendente"}
                    </small>
                  </div>
                  <div>
                    <span
                      className={`absorption-state absorption-state-${item.status}`}
                    >
                      {labels[item.status]}
                    </span>
                    <small>{item.reason}</small>
                    {item.status !== "imported" && (
                      <button
                        className="button ghost"
                        disabled={busy}
                        onClick={() => edit(item)}
                      >
                        Revisar{" "}
                        {item.record.name || `registro ${item.position + 1}`}
                      </button>
                    )}
                  </div>
                  {editing === item.id && (
                    <div className="absorption-editor">
                      {item.issues.length > 0 && (
                        <ul>
                          {item.issues.map((issue, i) => (
                            <li key={i}>{issue}</li>
                          ))}
                        </ul>
                      )}
                      <div className="absorption-edit-fields">
                        {primaryFields.map((field) => (
                          <label className="field" key={field}>
                            <span>{fields[field]}</span>
                            <input
                              disabled={busy}
                              value={draft[field]}
                              onChange={(e) =>
                                setDraft((d) => ({
                                  ...d,
                                  [field]: e.target.value,
                                }))
                              }
                            />
                          </label>
                        ))}
                      </div>
                      <details>
                        <summary>
                          Contatos, fonte e informações adicionais
                        </summary>
                        <div className="absorption-edit-fields">
                          {Object.keys(draft)
                            .filter((field) => !primaryFields.includes(field))
                            .map((field) => (
                              <label className="field" key={field}>
                                <span>{fields[field]}</span>
                                <input
                                  disabled={busy}
                                  value={draft[field]}
                                  onChange={(e) =>
                                    setDraft((d) => ({
                                      ...d,
                                      [field]: e.target.value,
                                    }))
                                  }
                                />
                              </label>
                            ))}
                        </div>
                      </details>
                      <label className="field">
                        <span>Justificativa da revisão</span>
                        <input
                          value={reason}
                          maxLength={500}
                          disabled={busy}
                          onChange={(e) => setReason(e.target.value)}
                        />
                      </label>
                      <div className="absorption-actions">
                        <button
                          className="button primary"
                          disabled={busy}
                          onClick={() => void save(item)}
                        >
                          Salvar correção
                        </button>
                        <button
                          className="button"
                          onClick={() => setEditing(null)}
                        >
                          Fechar revisão
                        </button>
                      </div>
                      {item.matches.length > 0 && (
                        <div>
                          <strong>Correspondências</strong>
                          {item.matches.map((m, i) => (
                            <p key={i}>
                              {m.name} · {m.city} · {m.address}
                              <br />
                              {m.reason}
                            </p>
                          ))}
                          <div className="absorption-actions">
                            <button
                              className="button"
                              disabled={
                                busy ||
                                reason.trim().length < 10 ||
                                item.matches.some((m) => m.kind === "confirmed")
                              }
                              onClick={() => void decide(item, "distinct")}
                            >
                              São empresas distintas
                            </button>
                            <button
                              className="button"
                              disabled={busy || reason.trim().length < 10}
                              onClick={() => void decide(item, "duplicate")}
                            >
                              Confirmar duplicata
                            </button>
                          </div>
                        </div>
                      )}
                      {item.suggestions.map((s) => (
                        <div className="absorption-suggestion" key={s.id}>
                          <strong>{s.record.name}</strong>
                          <p>
                            {s.record.city} · {String(s.record.address || "")}
                            <br />
                            {String(s.record.latitude)},{" "}
                            {String(s.record.longitude)}
                          </p>
                          <small>
                            {s.provider} · {s.reason} ·{" "}
                            {new Date(s.observed_at * 1000).toLocaleDateString(
                              "pt-BR",
                            )}
                          </small>
                          <div className="absorption-actions">
                            <button
                              className="button"
                              disabled={busy || reason.trim().length < 10}
                              onClick={() => void decide(item, "accept", s.id)}
                            >
                              Aceitar localização
                            </button>
                            <button
                              className="button"
                              disabled={busy || reason.trim().length < 10}
                              onClick={() => void decide(item, "reject", s.id)}
                            >
                              Rejeitar sugestão
                            </button>
                          </div>
                        </div>
                      ))}
                      {(item.matches.length > 0 ||
                        item.suggestions.length > 0) && (
                        <small>
                          Descreva a justificativa com pelo menos 10 caracteres
                          para registrar uma decisão.
                        </small>
                      )}
                      <details>
                        <summary>Original e histórico de alterações</summary>
                        <pre
                          tabIndex={0}
                          aria-label="Dados originais e auditoria"
                        >
                          {JSON.stringify(
                            {
                              original: item.original,
                              alteracoes: item.history,
                            },
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
        {history.length > 0 && (
          <details className="absorption-history">
            <summary>Lotes anteriores</summary>
            <div>
              {history.map((row) => (
                <button
                  type="button"
                  key={row.id}
                  disabled={busy}
                  onClick={() => void refresh(row.id)}
                >
                  <span>
                    {new Date(row.created_at * 1000).toLocaleDateString(
                      "pt-BR",
                    )}{" "}
                    · {row.source}
                  </span>
                  <small>
                    {row.status === "committed"
                      ? "Concluído"
                      : row.status === "partial"
                        ? "Parcial"
                        : "Prévia"}
                  </small>
                </button>
              ))}
            </div>
          </details>
        )}
      </div>
    </Modal>
  );
}
