import { useEffect, useId, useRef, useState } from "react";
import { api } from "../api";
import { tr } from "../i18n";
import type { Lead } from "../types";
import type {
  CommercialIntent,
  SearchLocation as Location,
  SearchArea,
} from "../searchTypes";
import { Modal } from "./UI";
import SearchCriteria, {
  criteriaFrom,
  type Criteria,
  type PreparedSearch,
} from "./SearchCriteria";
import "./unified-search.css";

export type SearchJob = {
  id: string;
  status: string;
  reason: string;
  error: string;
  intent: CommercialIntent;
  counters: Record<string, number>;
  results: { id: string; group: string; reason: string; lead: Lead }[];
  updated_at: number;
  deadline: number;
  limits: {
    provider_pages: number;
    candidates: number;
    investigations: number;
  };
  coverage: { sector: string; coverage: string; reason: string }[];
  plan?: {
    decision: string;
    scope: string;
    steps: {
      sector: string;
      pages: number;
      qualified: number;
      discarded: number;
      exhausted: boolean;
    }[];
  };
};
type LaunchResponse =
  | { status: "started"; job: SearchJob }
  | { status: "location_conflict"; message: string }
  | { status: "clarification"; messages: string[] };
const kinds = {
  district: "Bairro ou distrito",
  city: "Cidade",
  county: "Região",
  state: "Estado",
  country: "País",
};
const areaLabel = (area: SearchArea) =>
  tr(area.kind === "polygon" ? "Território desenhado" : "Área visível do mapa");
const states: Record<string, string> = {
  pending: "Aguardando início",
  running: "Coletando",
  investigating: "Investigando",
  paused: "Pausada",
  completed: "Meta atingida",
  partial: "Resultado parcial",
  cancelled: "Cancelada",
};

export function SearchHistory({
  current,
  onSelect,
}: {
  current: string | null;
  onSelect: (id: string) => void;
}) {
  const [jobs, setJobs] = useState<SearchJob[]>([]);
  const [error, setError] = useState("");
  async function load() {
    try {
      setJobs(await api<SearchJob[]>("/smart-searches"));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    let live = true;
    api<SearchJob[]>("/smart-searches")
      .then((rows) => {
        if (live) setJobs(rows);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [current]);
  return (
    <details
      className="search-history"
      onToggle={(e) => {
        if (e.currentTarget.open) void load();
      }}
    >
      <summary>{tr("Buscas recentes")}</summary>
      {error && <p role="alert">{error}</p>}
      {!error && !jobs.length && <p>{tr("Nenhuma busca iniciada.")}</p>}
      <ul>
        {jobs.map((job) => (
          <li key={job.id}>
            <button
              type="button"
              aria-current={job.id === current ? "true" : undefined}
              onClick={() => onSelect(job.id)}
            >
              <strong>{job.intent.query || (job.intent.sectors.length ? job.intent.sectors.map((sector) => tr(sector)).join(", ") : tr("Exploração geral"))}</strong>
              <span>
                {job.intent.area
                  ? areaLabel(job.intent.area)
                  : job.intent.location?.formatted ||
                    job.intent.legacy?.location ||
                    job.intent.market.city}{" "}
                · {tr(states[job.status] || job.status)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function SearchDialog({
  onClose,
  onStarted,
  storageKey,
  initialText = "",
  initialIntent,
  initialArea,
}: {
  onClose: () => void;
  onStarted: (job: SearchJob) => void;
  storageKey: string;
  initialText?: string;
  initialIntent?: CommercialIntent;
  initialArea?: SearchArea;
}) {
  const [area, setArea] = useState<SearchArea | null>(
    initialIntent?.area || initialArea || null,
  );
  const [text, setText] = useState(initialIntent?.query || initialText);
  const [prepared, setPrepared] = useState<PreparedSearch | null>(null);
  const [criteria, setCriteria] = useState<Criteria | null>(() =>
    initialIntent ? criteriaFrom(initialIntent) : null,
  );
  const [adjusting, setAdjusting] = useState(false);
  const [target, setTarget] = useState<number>(initialIntent?.target || 50);
  const [selected, setSelected] = useState<{
    place: Location;
    query: string;
  } | null>(() => {
    if (initialArea) return null;
    // A saved search owns its geography; never replace it with a remembered place.
    if (initialIntent)
      return initialIntent.location
        ? { place: initialIntent.location, query: initialIntent.location.name }
        : null;
    try {
      const value = JSON.parse(
        localStorage.getItem(storageKey + ":search-location") || "null",
      );
      const place = value?.place;
      return place &&
        ["id", "formatted", "country", "country_code"].every(
          (field) => typeof place[field] === "string",
        ) &&
        Object.hasOwn(kinds, place.administrative_type) &&
        typeof value.query === "string" &&
        value.query.length >= 2
        ? value
        : null;
    } catch {
      return null;
    }
  });
  const [where, setWhere] = useState(
    selected?.place.formatted || initialIntent?.market.city || "",
  );
  const [options, setOptions] = useState<Location[]>([]);
  const [active, setActive] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [locationError, setLocationError] = useState("");
  const [conflict, setConflict] = useState("");
  const key = useRef(crypto.randomUUID());
  const listId = useId();
  const input = useRef<HTMLInputElement>(null);
  const reset = () => {
    key.current = crypto.randomUUID();
    setConflict("");
    setError("");
  };
  useEffect(() => {
    if (area || selected || where.trim().length < 2) {
      setOptions([]);
      setLoading(false);
      return;
    }
    let live = true;
    setLoading(true);
    setLocationError("");
    setActive(-1);
    const timer = setTimeout(() => {
      api<Location[]>(
        `/smart-searches/locations?q=${encodeURIComponent(where.trim())}`,
      )
        .then((rows) => {
          if (live) setOptions(rows);
        })
        .catch((e) => {
          if (live) {
            setLocationError(e.message);
            setOptions([]);
          }
        })
        .finally(() => {
          if (live) setLoading(false);
        });
    }, 350);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [where, selected, area]);
  function choose(place: Location) {
    setSelected({ place, query: where.trim() });
    setWhere(place.formatted);
    setOptions([]);
    setActive(-1);
    reset();
    input.current?.focus();
  }
  async function adjust() {
    setBusy(true);
    setError("");
    try {
      const value = await api<PreparedSearch>(
        "/smart-searches/prepare",
        "POST",
        { text, target },
      );
      setPrepared(value);
      setCriteria((current) => current || criteriaFrom(value.intent));
      setAdjusting(true);
      reset();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function launch(confirm_location = false) {
    if (busy || (!selected && !area)) return;
    setBusy(true);
    setError("");
    try {
      const response = await api<LaunchResponse>(
        "/smart-searches/launch",
        "POST",
        {
          text,
          target,
          ...(area
            ? { area }
            : {
                location: {
                  id: selected!.place.id,
                  query: selected!.query,
                  country: selected!.place.country_code,
                },
              }),
          request_key: key.current,
          confirm_location,
          ...(criteria ? { criteria } : {}),
        },
        45000,
      );
      if (response.status === "location_conflict") {
        setConflict(tr(response.message));
        return;
      }
      if (response.status === "clarification") {
        setError(response.messages.map((message) => tr(message)).join(" "));
        return;
      }
      try {
        if (selected && !area)
          localStorage.setItem(
            storageKey + ":search-location",
            JSON.stringify(selected),
          );
      } catch {
        /* Storage can be disabled. */
      }
      onStarted(response.job);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Buscar empresas" onClose={onClose} className="unified-search">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void launch();
        }}
      >
        <label>
          {tr("O que buscar (opcional)")}
          <input
            autoComplete="off"
            maxLength={1200}
            value={text}
            disabled={busy}
            onChange={(e) => {
              setText(e.target.value);
              setPrepared(null);
              setCriteria(null);
              setAdjusting(false);
              reset();
            }}
            placeholder={tr("Todos os setores ou um pedido específico")}
          />
        </label>
        <div className="search-location-field">
          {area ? (
            <>
              <label>
                {tr("Onde?")}
                <input readOnly value={areaLabel(area)} />
              </label>
              <button
                type="button"
                className="text-link"
                disabled={busy}
                onClick={() => {
                  setArea(null);
                  setSelected(null);
                  setWhere("");
                  reset();
                }}
              >
                {tr("Escolher outra localização")}
              </button>
            </>
          ) : (
            <>
              <label>
                {tr("Onde?")}
                <input
                  ref={input}
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={options.length > 0}
                  aria-controls={options.length ? listId : undefined}
                  aria-activedescendant={
                    active >= 0 && options[active]
                      ? `${listId}-${active}`
                      : undefined
                  }
                  autoComplete="off"
                  required
                  maxLength={160}
                  value={where}
                  disabled={busy}
                  onChange={(e) => {
                    setWhere(e.target.value);
                    setSelected(null);
                    setOptions([]);
                    reset();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Escape" && options.length) {
                      e.preventDefault();
                      e.stopPropagation();
                      setOptions([]);
                      setActive(-1);
                    }
                    if (e.key === "ArrowDown" && options.length) {
                      e.preventDefault();
                      setActive((n) => (n + 1) % options.length);
                    }
                    if (e.key === "ArrowUp" && options.length) {
                      e.preventDefault();
                      setActive(
                        (n) => (n - 1 + options.length) % options.length,
                      );
                    }
                    if (e.key === "Enter" && active >= 0 && options[active]) {
                      e.preventDefault();
                      choose(options[active]);
                    }
                  }}
                />
              </label>
              {options.length > 0 && (
                <ul id={listId} role="listbox" aria-label={tr("Localizações")}>
                  {options.map((place, index) => (
                    <li
                      id={`${listId}-${index}`}
                      key={place.id}
                      role="option"
                      aria-selected={active === index}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => choose(place)}
                    >
                      <strong>{place.formatted}</strong>
                      <span>{tr(kinds[place.administrative_type])}</span>
                    </li>
                  ))}
                </ul>
              )}
              {(selected?.place.source === "geoapify" ||
                options.some((place) => place.source === "geoapify")) && (
                <p className="search-attribution">
                  <a
                    href="https://www.geoapify.com/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Geoapify
                  </a>{" "}
                  ·{" "}
                  <a
                    href="https://www.openstreetmap.org/copyright"
                    target="_blank"
                    rel="noreferrer"
                  >
                    © OpenStreetMap
                  </a>
                </p>
              )}
              {loading && <p role="status">{tr("Buscando localizações…")}</p>}
              {locationError && (
                <p role="alert" className="error-text">
                  {locationError}
                </p>
              )}
              {!loading &&
                !selected &&
                where.length >= 2 &&
                !options.length &&
                !locationError && (
                  <p role="status">{tr("Nenhuma localização encontrada.")}</p>
                )}
              {selected && (
                <p className="muted">
                  {tr(kinds[selected.place.administrative_type])} ·{" "}
                  {selected.place.country}
                </p>
              )}
            </>
          )}
        </div>
        <div className="field">
          <label htmlFor={`${listId}-target`}>{tr("Quantidade")}</label>
          <select
            id={`${listId}-target`}
            value={target}
            disabled={busy}
            onChange={(e) => {
              setTarget(Number(e.target.value));
              reset();
            }}
          >
            {[25, 50, 75, 100].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="text-link"
          disabled={busy}
          aria-expanded={adjusting}
          onClick={() => (prepared ? setAdjusting(!adjusting) : void adjust())}
        >
          {tr("Ajustar critérios")}
        </button>
        {initialIntent && criteria && !adjusting && (
          <p className="muted">{tr("Critérios da busca salva aplicados.")}</p>
        )}
        {adjusting && prepared && criteria && (
          <SearchCriteria
            value={criteria}
            sectors={prepared.sectors}
            warnings={prepared.warnings}
            onChange={(value) => {
              setCriteria(value);
              reset();
            }}
          />
        )}
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
        {conflict && (
          <div role="alert">
            <p>{conflict}</p>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => void launch(true)}
            >
              {tr(area ? "Usar área selecionada" : "Usar local selecionado")}
            </button>
          </div>
        )}
        <div className="form-actions">
          <button type="button" className="button" onClick={onClose}>
            {tr("Cancelar")}
          </button>
          <button
            className="button primary"
            disabled={busy || (!selected && !area)}
          >
            {tr(busy ? "Iniciando…" : "Buscar empresas")}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function SearchProgress({
  jobId,
  onResults,
  onDismiss,
  onSaved,
}: {
  jobId: string;
  onResults: (job: SearchJob, group: string) => void;
  onDismiss: () => void;
  onSaved: () => void;
}) {
  const [job, setJob] = useState<SearchJob | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [group, setGroup] = useState("all");
  const [refresh, setRefresh] = useState(0);
  const [saving, setSaving] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    setSaveOpen(false);
    setSaveName("");
    setSaved(false);
  }, [jobId]);
  async function save() {
    if (saving || !job || saveName.trim().length < 2) return;
    setSaving(true);
    setError("");
    try {
      await api(`/smart-searches/${job.id}/save`, "POST", {
        name: saveName.trim(),
      });
      setSaved(true);
      setSaveOpen(false);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  useEffect(() => {
    const refreshReview = () => setRefresh((n) => n + 1);
    window.addEventListener("scout:qualification-reviewed", refreshReview);
    return () =>
      window.removeEventListener("scout:qualification-reviewed", refreshReview);
  }, []);
  const callback = useRef(onResults);
  callback.current = onResults;
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const value = await api<SearchJob>(`/smart-searches/${jobId}`);
        if (live) {
          setJob(value);
          setError("");
          if (["pending", "running", "investigating"].includes(value.status))
            timer = setTimeout(load, 4000);
        }
      } catch (e) {
        if (live) setError((e as Error).message);
      }
    }
    setJob(null);
    setGroup("all");
    void load();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [jobId, refresh]);
  useEffect(() => {
    if (job) callback.current(job, group);
  }, [job, group]);
  async function control(action: string) {
    setBusy(true);
    setError("");
    try {
      setJob(
        await api<SearchJob>(`/smart-searches/${jobId}/action`, "POST", {
          action,
        }),
      );
      setRefresh((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const active =
    job &&
    ["pending", "running", "investigating", "paused"].includes(job.status);
  return (
    <section className="search-progress" aria-label={tr("Busca em andamento")}>
      {job ? (
        <>
          <div className="search-progress-heading">
            <div>
              <strong>{job.intent.query || (job.intent.sectors.length ? job.intent.sectors.map((sector) => tr(sector)).join(", ") : tr("Exploração geral"))}</strong>
              <span>
                {(job.intent.area && areaLabel(job.intent.area)) ||
                  job.intent.location?.formatted ||
                  job.intent.legacy?.location ||
                  [job.intent.market.city, job.intent.market.country]
                    .filter(Boolean)
                    .join(", ")}
              </span>
            </div>
            <span role="status">{tr(states[job.status] || job.status)}</span>
          </div>
          <div className="search-progress-counts" aria-live="polite">
            <strong>
              {job.counters.qualified || 0} / {job.intent.target}{" "}
              {tr("qualificadas")}
            </strong>
            <span>
              {job.counters.discovered || 0} {tr("encontradas")}
            </span>
            <span>
              {job.counters.investigating || 0} {tr("em investigação")}
            </span>
          </div>
          {(job.reason || job.error) && <p>{tr(job.reason || job.error)}</p>}
          <details className="search-execution-details">
            <summary>{tr("Detalhes da execução")}</summary>
            {job.plan && (
              <>
                <h3>{tr("Plano de descoberta")}</h3>
                <p>{tr(job.plan.decision)}</p>
                <ul>
                  {job.plan.steps.map((step) => (
                    <li key={step.sector}>
                      <strong>{tr(step.sector || "Exploração geral")}</strong>: {step.pages}{" "}
                      {tr("páginas coletadas")}, {step.qualified}{" "}
                      {tr("qualificadas")}, {step.discarded} {tr("descartadas")}
                      {step.exhausted && <> · {tr("Coleta encerrada")}</>}
                    </li>
                  ))}
                </ul>
                <p>{tr(job.plan.scope)}</p>
              </>
            )}
            <h3>{tr("Cobertura e limites")}</h3>
            {job.coverage.map((item) => (
              <p key={item.sector}>
                {tr(item.sector || "Exploração geral")}: {tr(item.coverage)} {tr(item.reason)}
              </p>
            ))}
            <dl>
              <div>
                <dt>{tr("Páginas coletadas / limite")}</dt>
                <dd>
                  {job.counters.calls || 0} / {job.limits.provider_pages}
                </dd>
              </div>
              <div>
                <dt>{tr("Limite de candidatos")}</dt>
                <dd>{job.limits.candidates}</dd>
              </div>
              <div>
                <dt>{tr("Investigações / limite")}</dt>
                <dd>
                  {job.counters.investigated || 0} / {job.limits.investigations}
                </dd>
              </div>
              <div>
                <dt>{tr("Prazo da busca")}</dt>
                <dd>
                  {new Date(job.deadline * 1000).toLocaleString(
                    document.documentElement.lang || "pt-BR",
                  )}
                </dd>
              </div>
            </dl>
          </details>
          <div className="search-progress-actions">
            <label>
              {tr("Exibir resultados")}
              <select value={group} onChange={(e) => setGroup(e.target.value)}>
                <option value="all">{tr("Todos os resultados")}</option>
                <option value="qualified">{tr("Qualificadas")}</option>
                <option value="investigating">{tr("Em investigação")}</option>
                <option value="discarded">{tr("Descartadas")}</option>
              </select>
            </label>
            {active && (
              <>
                <button
                  className="button"
                  disabled={busy}
                  onClick={() =>
                    void control(job.status === "paused" ? "resume" : "pause")
                  }
                >
                  {tr(job.status === "paused" ? "Retomar" : "Pausar")}
                </button>
                <button
                  className="button"
                  disabled={busy}
                  onClick={() => void control("cancel")}
                >
                  {tr("Cancelar busca")}
                </button>
              </>
            )}
            <button className="button" onClick={onDismiss}>
              {tr("Voltar ao Radar completo")}
            </button>
            <button
              className="button"
              disabled={saved || saving}
              onClick={() => setSaveOpen(!saveOpen)}
              aria-expanded={saveOpen}
            >
              {tr(saved ? "Busca salva" : "Salvar busca")}
            </button>
          </div>
          {saveOpen && (
            <form
              className="search-save"
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <label>
                {tr("Nome da busca")}
                <input
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  minLength={2}
                  maxLength={80}
                  required
                  disabled={saving}
                />
              </label>
              <button
                className="button"
                disabled={saving || saveName.trim().length < 2}
              >
                {tr("Salvar")}
              </button>
              <button
                type="button"
                className="button"
                disabled={saving}
                onClick={() => setSaveOpen(false)}
              >
                {tr("Cancelar")}
              </button>
            </form>
          )}
        </>
      ) : (
        <p role="status">{tr("Carregando busca…")}</p>
      )}
      {error && (
        <p role="alert" className="error-text">
          {error}{" "}
          <button className="button" onClick={() => setRefresh((n) => n + 1)}>
            {tr("Tentar novamente")}
          </button>
        </p>
      )}
    </section>
  );
}
