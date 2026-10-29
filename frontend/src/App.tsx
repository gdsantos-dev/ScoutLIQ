import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { AnimatePresence, MotionConfig, useReducedMotion } from "motion/react";
import { X } from "lucide-react";
import WorkspaceShell, { Notice } from "./components/WorkspaceShell";
import CommandBar from "./components/CommandBar";
import { environmentFor, pageFromHash } from "./navigation";
import type { Environment } from "./navigation";
import { api, ApiError, setCsrf } from "./api";
import type {
  RadarViewState,
  Dashboard,
  Expense,
  Lead,
  RadarSearchInput,
  RadarSearchResponse,
  RadarLocation,
  Page,
  Sale,
  Stage,
  User,
} from "./types";
import { Brand, Skeleton, View, Confirm } from "./components/UI";
import LeadForm from "./components/LeadForm";
import AuthScreen, { type AuthPayload } from "./components/AuthScreen";
import { ExpenseForm, PaymentForm, SaleForm } from "./components/CommerceForms";
import { tr } from "./i18n";
const Radar = lazy(() => import("./pages/Radar"));
const ContextPanel = lazy(() => import("./components/ContextPanel"));
const Actions = lazy(() => import("./pages/Actions"));
const Pipeline = lazy(() => import("./pages/Pipeline"));
const Intelligence = lazy(() => import("./pages/Intelligence"));
const Campaigns = lazy(() => import("./pages/Campaigns"));
const Clients = lazy(() => import("./pages/Clients"));
const Finance = lazy(() => import("./pages/Finance"));
const Automations = lazy(() => import("./pages/Automations"));
const Sites = lazy(() => import("./pages/Sites"));
const Settings = lazy(() => import("./pages/Settings"));
const Integrations = lazy(() => import("./pages/Integrations"));
const About = lazy(() => import("./pages/About"));
type Auth = AuthPayload;

export default function App() {
  const [user, setUser] = useState<User | null>(null),
    [authLoading, setAuthLoading] = useState(true),
    [authError, setAuthError] = useState("");
  const [page, setPage] = useState<Page>(pageFromHash);
  const [environment, setEnvironment] = useState<Environment>(
    () => environmentFor(pageFromHash()) ?? "operate",
  );
  const lastPages = useRef<Record<Environment, Page>>({
    operate: "radar",
    manage: "actions",
  });
  const radarViews = useRef<Partial<Record<Page, RadarViewState>>>({});
  const [commandOpen, setCommandOpen] = useState(false);
  const [radarIntent, setRadarIntent] = useState("");
  const [radarSearchId, setRadarSearchId] = useState("");
  const [leads, setLeads] = useState<Lead[]>([]),
    [sales, setSales] = useState<Sale[]>([]),
    [expenses, setExpenses] = useState<Expense[]>([]),
    [dashboard, setDashboard] = useState<Dashboard | null>(null),
    [period, setPeriod] = useState("7d"),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(() =>
      new URLSearchParams(location.hash.split("?")[1] || "").get("lead"),
    ),
    [editing, setEditing] = useState<Lead | true | "pipeline" | null>(null),
    [selling, setSelling] = useState<Lead | null>(null),
    [payment, setPayment] = useState<Sale | null>(null),
    [expenseOpen, setExpenseOpen] = useState(false),
    [busy, setBusy] = useState(false);
  const [deletion, setDeletion] = useState<{
      kind: "lead" | "expense";
      id: string;
      name: string;
    } | null>(null),
    [deleteError, setDeleteError] = useState("");
  const systemReduced = useReducedMotion(),
    reduced = !!systemReduced || user?.motion === "reduced",
    selected = leads.find((l) => l.id === selectedId),
    loadVersion = useRef(0),
    periodRef = useRef(period);
  periodRef.current = period;
  const acceptAuth = useCallback((auth: Auth) => {
    document.documentElement.lang = auth.user.locale;
    document.documentElement.dataset.currency = auth.user.default_currency;
    setCsrf(auth.csrf);
    setUser(auth.user);
    setAuthError("");
  }, []);
  const localLogout = useCallback(() => {
    setUser(null);
    setCsrf("");
    setLeads([]);
    setSales([]);
    setExpenses([]);
    setDashboard(null);
    setSelectedId(null);
    setEditing(null);
    setSelling(null);
    setPayment(null);
    setExpenseOpen(false);
    setDeletion(null);
    setCommandOpen(false);
    setRadarIntent("");
    setRadarSearchId("");
    radarViews.current = {};
    loadVersion.current++;
  }, []);
  useEffect(() => {
    let alive = true;
    api<Auth>("/auth/me")
      .then((a) => {
        if (alive) acceptAuth(a);
      })
      .catch((e) => {
        if (alive && !(e instanceof ApiError && e.status === 401))
          setAuthError(e.message);
      })
      .finally(() => {
        if (alive) setAuthLoading(false);
      });
    const expired = () => {
      localLogout();
      setAuthError("Sua sessão expirou. Entre novamente.");
    };
    window.addEventListener("session-expired", expired);
    return () => {
      alive = false;
      window.removeEventListener("session-expired", expired);
    };
  }, [acceptAuth, localLogout]);
  useEffect(() => {
    const hash = () => {
      const next = pageFromHash();
      setPage(next);
      setSelectedId(
        new URLSearchParams(location.hash.split("?")[1] || "").get("lead"),
      );
      const mode = environmentFor(next);
      if (mode) {
        setEnvironment(mode);
        lastPages.current[mode] = next;
      }
    };
    window.addEventListener("hashchange", hash);
    return () => window.removeEventListener("hashchange", hash);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.accent = "crimson";
    document.documentElement.dataset.motion = reduced ? "reduced" : "full";
    if (user) document.documentElement.lang = user.locale;
    document.documentElement.dataset.currency = user?.default_currency ?? "BRL";
  }, [user?.accent, user?.locale, user?.default_currency, reduced]);
  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(id);
  }, [notice]);
  const refresh = useCallback(async () => {
    const version = ++loadVersion.current;
    const requestedPeriod = periodRef.current;
    const [l, s, e, d] = await Promise.all([
      api<Lead[]>("/leads"),
      api<Sale[]>("/sales"),
      api<Expense[]>("/expenses"),
      api<Dashboard>(`/dashboard?period=${requestedPeriod}`),
    ]);
    if (version !== loadVersion.current) return;
    setLeads(l);
    setSales(s);
    setExpenses(e);
    if (requestedPeriod === periodRef.current) setDashboard(d);
    setError("");
  }, []);
  useEffect(() => {
    if (!user) return;
    setLoading(true);
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [user?.id, user?.timezone, user?.locale, user?.default_currency, refresh]);
  useEffect(() => {
    if (!user) return;
    let alive = true;
    api<Dashboard>(`/dashboard?period=${period}`)
      .then((d) => {
        if (alive) setDashboard(d);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [period, user?.id, user?.timezone, user?.default_currency]);
  const navigate = (next: Page) => {
    location.hash = next;
    setPage(next);
    const mode = environmentFor(next);
    if (mode) {
      setEnvironment(mode);
      lastPages.current[mode] = next;
    }
    setSelectedId(null);
  };
  const closeDrawer = useCallback(() => {
    setSelectedId(null);
    const [route, query] = location.hash.split("?");
    const params = new URLSearchParams(query || "");
    params.delete("lead");
    history.replaceState(
      null,
      "",
      `${location.pathname}${location.search}${route}${params.size ? `?${params}` : ""}`,
    );
  }, []);
  const saved = async () => {
    await refresh().catch(() =>
      setError(
        "Registro salvo. Não foi possível atualizar a tela; use Atualizar dados antes de continuar.",
      ),
    );
    setNotice("Alterações salvas.");
  };
  async function move(lead: Lead, stage: Stage) {
    if (busy) return;
    if (stage === "won") {
      setSelectedId(null);
      setSelling(lead);
      return;
    }
    if (lead.stage === "won") {
      setNotice("Vendas fechadas são gerenciadas em Clientes.");
      return;
    }
    setBusy(true);
    setError("");
    setLeads((current) =>
      current.map((l) =>
        l.id === lead.id ? { ...l, stage, in_pipeline: true } : l,
      ),
    );
    try {
      const updated = await api<Lead>(`/leads/${lead.id}/stage`, "PATCH", {
        stage,
        version: lead.version,
      });
      setLeads((current) =>
        current.map((l) => (l.id === lead.id ? updated : l)),
      );
      setNotice(
        !lead.in_pipeline && stage === "discovered"
          ? "Oportunidade salva no Pipeline."
          : "Etapa atualizada.",
      );
    } catch (e) {
      await refresh().catch(() =>
        setLeads((current) =>
          current.map((l) => (l.id === lead.id ? lead : l)),
        ),
      );
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const loadRadarLocations = useCallback(
    async (query: string, country = "") => {
      const lang = user?.locale?.split("-")[0] ?? "en";
      const params = new URLSearchParams({ q: query, lang });
      if (country) params.set("country", country);
      return api<RadarLocation[]>(`/radar/locations?${params.toString()}`);
    },
    [user?.locale],
  );

  async function discover(input: RadarSearchInput) {
    const result = await api<RadarSearchResponse>(
      "/radar/search",
      "POST",
      input,
      90000,
    );
    setLeads((current) => {
      const merged = new Map(current.map((lead) => [lead.id, lead]));
      result.results.forEach((lead) => merged.set(lead.id, lead));
      return Array.from(merged.values()).sort(
        (a, b) => b.score.value - a.score.value,
      );
    });
    return result;
  }

  async function logout() {
    try {
      await api("/auth/logout", "POST");
      localLogout();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function exportData() {
    try {
      const data = await api("/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `scoutliq-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice("Exportação concluída.");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function remove() {
    if (!deletion) return;
    setBusy(true);
    setDeleteError("");
    try {
      await api(
        `/${deletion.kind === "lead" ? "leads" : "expenses"}/${deletion.id}`,
        "DELETE",
      );
      setSelectedId(null);
      await refresh();
      setDeletion(null);
      setNotice("Registro excluído.");
    } catch (e) {
      setDeleteError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!user) return;
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (!document.querySelector("dialog[open]") && !selectedId)
          setCommandOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [user, selectedId]);
  if (authLoading)
    return (
      <div className="boot-screen">
        <Brand />
        <span className="boot-line" />
      </div>
    );
  if (!user)
    return <AuthScreen onLogin={acceptAuth} initialError={authError} />;
  const hasDemo = leads.some((l) => l.demo);
  return (
    <MotionConfig reducedMotion={reduced ? "always" : "never"}>
      <WorkspaceShell
        environment={environment}
        page={page}
        user={user}
        navigate={navigate}
        onEnvironment={(mode) => navigate(lastPages.current[mode])}
        onCommand={() => setCommandOpen(true)}
        onRefresh={() => {
          setLoading(true);
          refresh()
            .catch((e) => setError(e.message))
            .finally(() => setLoading(false));
        }}
        onLogout={() => void logout()}
        hasDemo={hasDemo}
        leads={leads}
        sales={sales}
        loading={loading}
        onSelect={(lead) => setSelectedId(lead.id)}
      >
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button
              className="text-link"
              onClick={() => refresh().catch((e) => setError(e.message))}
            >
              {tr("Tentar novamente")}
            </button>
            <button
              className="icon-button"
              aria-label={tr("Fechar aviso")}
              onClick={() => setError("")}
            >
              <X size={16} />
            </button>
          </div>
        )}
        {loading && !dashboard ? (
          <Skeleton />
        ) : dashboard ? (
          <Suspense fallback={<Skeleton />}>
            <View key={page}>
              {(page === "radar" ||
                page === "opportunities" ||
                page === "monitors") && (
                <Radar
                  remembered={radarViews.current[page]}
                  onRemember={(state) => {
                    radarViews.current[page] = state;
                  }}
                  surface={page as "radar" | "opportunities" | "monitors"}
                  intent={radarIntent}
                  onIntentConsumed={() => setRadarIntent("")}
                  searchId={radarSearchId}
                  onSearchConsumed={() => setRadarSearchId("")}
                  onOpenSearch={(id) => {
                    setRadarSearchId(id);
                    navigate("radar");
                  }}
                  selectedId={selectedId ?? undefined}
                  leads={leads}
                  onSelect={(l) => setSelectedId(l.id)}
                  onAdd={() => setEditing(true)}
                  onDiscover={discover}
                  onLoadLocations={loadRadarLocations}
                  onLeadUpdated={(updated) =>
                    setLeads((current) => {
                      const exists = current.some(
                        (lead) => lead.id === updated.id,
                      );
                      const next = exists
                        ? current.map((lead) =>
                            lead.id === updated.id ? updated : lead,
                          )
                        : [...current, updated];
                      return next.sort((a, b) => b.score.value - a.score.value);
                    })
                  }
                  onSaveOpportunity={(lead) => void move(lead, "discovered")}
                  busy={busy}
                  reduced={reduced}
                  storageKey={`scoutliq-radar-last-search:${user.id}`}
                  timezone={user.timezone}
                />
              )}
              {page === "actions" && (
                <Actions
                  leads={leads}
                  timezone={user.timezone}
                  onSelect={(lead) => setSelectedId(lead.id)}
                  onLeadUpdated={(updated) =>
                    setLeads((current) =>
                      current.map((lead) =>
                        lead.id === updated.id ? updated : lead,
                      ),
                    )
                  }
                  onNotice={setNotice}
                  storageKey={`scoutliq-outreach-templates:${user.id}`}
                />
              )}
              {page === "pipeline" && (
                <Pipeline
                  storageKey={`scoutliq-followup:${user.id}`}
                  leads={leads}
                  onSelect={(l) => setSelectedId(l.id)}
                  onMove={(l, s) => void move(l, s)}
                  onAdd={() => setEditing("pipeline")}
                  onAbsorbed={refresh}
                  busy={busy}
                  timezone={user.timezone}
                />
              )}
              {page === "intelligence" && <Intelligence />}
              {page === "campaigns" && (
                <Campaigns
                  leads={leads}
                  onSelect={(lead) => setSelectedId(lead.id)}
                />
              )}
              {page === "clients" && (
                <Clients
                  sales={sales}
                  onSelectLead={setSelectedId}
                  onPayment={setPayment}
                  onStatus={async (s, status) => {
                    try {
                      await api(`/sales/${s.id}`, "PATCH", {
                        project_status: status,
                      });
                      await saved();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                  onDeleteSale={async (s) => {
                    await api(`/sales/${s.id}`, "DELETE");
                    await saved();
                    setNotice("Venda excluída. O lead voltou para Encontrado.");
                  }}
                  onDeletePayment={async (s, p) => {
                    await api(`/sales/${s.id}/payments/${p.id}`, "DELETE");
                    await saved();
                    setNotice("Recebimento excluído.");
                  }}
                />
              )}
              {page === "sites" && <Sites sales={sales} leads={leads} />}
              {page === "finance" && (
                <Finance
                  period={period}
                  setPeriod={setPeriod}
                  reduced={reduced}
                  dashboard={dashboard}
                  sales={sales}
                  expenses={expenses}
                  onPayment={setPayment}
                  onExpense={() => setExpenseOpen(true)}
                  onDeleteExpense={(e) => {
                    setDeleteError("");
                    setDeletion({
                      kind: "expense",
                      id: e.id,
                      name: e.description,
                    });
                  }}
                  onDeleteSale={async (s) => {
                    await api(`/sales/${s.id}`, "DELETE");
                    await saved();
                    setNotice("Venda excluída. O lead voltou para Encontrado.");
                  }}
                  onExport={() => void exportData()}
                />
              )}
              {page === "automations" && (
                <Automations
                  leads={leads}
                  onOpenSearch={(id) => {
                    setRadarSearchId(id);
                    navigate("radar");
                  }}
                />
              )}
              {page === "integrations" && (
                <Integrations
                  user={user}
                  leads={leads}
                  sales={sales}
                  onNotice={setNotice}
                />
              )}
              {page === "about" && <About user={user} />}
              {page === "settings" && (
                <Settings
                  user={user}
                  onUser={setUser}
                  onDemo={async () => {
                    await api("/demo", "POST");
                    await saved();
                  }}
                  onClearDemo={async () => {
                    await api("/demo", "DELETE");
                    await saved();
                  }}
                  hasDemo={hasDemo}
                  onExport={() => void exportData()}
                  onLogout={localLogout}
                />
              )}
            </View>
          </Suspense>
        ) : !error ? (
          <Skeleton />
        ) : null}
      </WorkspaceShell>
      <AnimatePresence>
        <Suspense
          fallback={
            <div className="workspace-notice" role="status">
              {tr("Carregando dados")}
            </div>
          }
        >
          {selected && (
            <ContextPanel
              key={selected.id}
              environment={environment}
              sales={sales.filter((sale) => sale.lead_id === selected.id)}
              onManage={() => {
                const destination =
                  selected.stage === "won" ? "clients" : "pipeline";
                navigate(destination);
                location.hash = `${destination}?lead=${encodeURIComponent(selected.id)}`;
              }}
              lead={selected}
              onClose={closeDrawer}
              onEdit={() => {
                setEditing(selected);
              }}
              onDelete={() => {
                setSelectedId(null);
                setDeleteError("");
                setDeletion({
                  kind: "lead",
                  id: selected.id,
                  name: selected.name,
                });
              }}
              onSale={() => {
                setSelectedId(null);
                setSelling(selected);
              }}
              onMove={(s) => void move(selected, s)}
              onLeadUpdated={(updated) =>
                setLeads((current) =>
                  current.map((lead) =>
                    lead.id === updated.id ? updated : lead,
                  ),
                )
              }
              busy={busy}
              timezone={user.timezone}
            />
          )}
        </Suspense>
      </AnimatePresence>
      {editing && (
        <LeadForm
          lead={
            editing === true || editing === "pipeline" ? undefined : editing
          }
          addToPipeline={editing === "pipeline"}
          onClose={() => setEditing(null)}
          onSaved={saved}
        />
      )}
      {selling && (
        <SaleForm
          lead={selling}
          timezone={user.timezone}
          defaultCurrency={user.default_currency}
          onClose={() => setSelling(null)}
          onSaved={saved}
        />
      )}
      {payment && (
        <PaymentForm
          sale={payment}
          timezone={user.timezone}
          onClose={() => setPayment(null)}
          onSaved={saved}
        />
      )}
      {expenseOpen && (
        <ExpenseForm
          timezone={user.timezone}
          defaultCurrency={user.default_currency}
          onClose={() => setExpenseOpen(false)}
          onSaved={saved}
        />
      )}
      {deletion && (
        <Confirm
          title={`Excluir ${deletion.name}?`}
          description="Esta ação remove o registro permanentemente."
          label="Excluir registro"
          onConfirm={() => void remove()}
          onClose={() => setDeletion(null)}
          busy={busy}
          error={deleteError}
        />
      )}
      {notice && <Notice message={notice} onClose={() => setNotice("")} />}
      {commandOpen && (
        <CommandBar
          leads={leads}
          onClose={() => setCommandOpen(false)}
          navigate={navigate}
          onSelect={(lead) => {
            const destination = lead.stage === "won" ? "clients" : page;
            navigate(destination);
            location.hash = `${destination}?lead=${encodeURIComponent(lead.id)}`;
            setSelectedId(lead.id);
          }}
          onAdd={() => setEditing(true)}
          onSearch={(query) => {
            setRadarIntent(query);
            navigate("radar");
          }}
        />
      )}
    </MotionConfig>
  );
}
