import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowUpRight,
  ChevronDown,
  Command,
  LogOut,
  RefreshCw,
  WifiOff,
  X,
} from "lucide-react";
import { Brand, Mark } from "./UI";
import styles from "./WorkspaceShell.module.css";
import { tr } from "../i18n";
import { globalNavigation, navigation } from "../navigation";
import type { Environment } from "../navigation";
import type { Lead, Page, Sale, User } from "../types";
import { inputDate, money } from "../types";

export default function WorkspaceShell({
  children,
  environment,
  page,
  user,
  navigate,
  onEnvironment,
  onCommand,
  onRefresh,
  onLogout,
  hasDemo,
  leads,
  sales,
  onSelect,
  loading,
}: {
  children: ReactNode;
  environment: Environment;
  page: Page;
  user: User;
  navigate: (page: Page) => void;
  onEnvironment: (mode: Environment) => void;
  onCommand: () => void;
  onRefresh: () => void;
  onLogout: () => void;
  hasDemo: boolean;
  leads: Lead[];
  sales: Sale[];
  onSelect: (lead: Lead) => void;
  loading: boolean;
}) {
  const [expandedNav, setExpandedNav] = useState(false);
  useEffect(() => { setExpandedNav(false); }, [page, environment]);
  const [menu, setMenu] = useState(false);
  const [offline, setOffline] = useState(!navigator.onLine);
  const menuRoot = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const online = () => setOffline(!navigator.onLine);
    window.addEventListener("online", online);
    window.addEventListener("offline", online);
    return () => {
      window.removeEventListener("online", online);
      window.removeEventListener("offline", online);
    };
  }, []);
  useEffect(() => {
    if (!menu) return;
    const close = (event: PointerEvent) => {
      if (!menuRoot.current?.contains(event.target as Node)) setMenu(false);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenu(false);
        menuRoot.current?.querySelector("button")?.focus();
      }
    };
    window.addEventListener("pointerdown", close);
    window.addEventListener("keydown", key);
    return () => {
      window.removeEventListener("pointerdown", close);
      window.removeEventListener("keydown", key);
    };
  }, [menu]);
  const today = inputDate(user.timezone);
  const overdue = leads
    .filter(
      (lead) =>
        lead.in_pipeline &&
        !["won", "lost"].includes(lead.stage) &&
        lead.next_action_on &&
        lead.next_action_on <= today,
    )
    .sort((a, b) =>
      (a.next_action_on || "").localeCompare(b.next_action_on || ""),
    );
  const payments = sales.filter(
    (sale) => sale.amount_cents > sale.received_cents && sale.due_on <= today,
  );
  const active = [...navigation, ...globalNavigation].find(
    (item) => item.id === page,
  );
  return (
    <div
      className={`${styles.shell} product-shell environment-${environment}`}
      data-environment={environment}
      data-page={page}
    >
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        {tr("Pular para o conteúdo")}
      </a>
      <header className={`${styles.masthead} workspace-masthead`}>
        <div className={styles.brand} ref={menuRoot}>
          <button
            className={styles.menuTrigger}
            aria-label={tr("Menu do workspace")}
            aria-expanded={menu}
            onClick={() => setMenu((value) => !value)}
          >
            <Mark />
            <Brand />
            <ChevronDown size={14} />
          </button>
          {menu && (
            <div className={`${styles.menu} workspace-menu`} aria-label={tr("Workspace")}>
              <div className={styles.identity}>
                <strong>{user.name}</strong>
                <span>{user.email}</span>
              </div>
              {globalNavigation.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    navigate(item.id);
                    setMenu(false);
                  }}
                >
                  <item.icon size={18} />
                  {tr(item.label)}
                  <ArrowUpRight size={14} />
                </button>
              ))}
              <button
                onClick={() => {
                  setMenu(false);
                  onLogout();
                }}
              >
                <LogOut size={18} />
                {tr("Sair da conta")}
              </button>
            </div>
          )}
        </div>
        <div
          className={`${styles.environments} environment-switch`}
          role="group"
          aria-label={tr("Ambiente")}
        >
          <button
            aria-pressed={environment === "operate"}
            onClick={() => onEnvironment("operate")}
          >
            {tr("Operar")}
          </button>
          <button
            aria-pressed={environment === "manage"}
            onClick={() => onEnvironment("manage")}
          >
            {tr("Gerir clientes")}
          </button>
        </div>
        <div className={styles.utilities}>
          {hasDemo && (
            <button
              className="demo-indicator"
              onClick={() => navigate("settings")}
            >
              {tr("Demonstração")}
            </button>
          )}
          <button
            className={styles.command}
            aria-label={tr("Buscar e executar comandos")}
            onClick={onCommand}
          >
            <Command size={17} />
            <span>{tr("Buscar")}</span>
            <kbd>Ctrl K</kbd>
          </button>
          <button
            className="icon-button refresh-control"
            aria-label={tr("Atualizar dados")}
            disabled={loading}
            onClick={onRefresh}
          >
            <RefreshCw size={17} className={loading ? "spin" : ""} />
          </button>
        </div>
      </header>
      <div className={`${styles.navigation} workspace-navigation`} data-expanded={expandedNav}>
        <button className={styles.navToggle} aria-expanded={expandedNav} aria-controls="workspace-destinations" onClick={() => setExpandedNav(value => !value)}>{tr(active?.label || "Radar")}<ChevronDown size={16}/></button>
        <div id="workspace-destinations" className={styles.destinations}>
        <span className={styles.caption}>
          {tr(environment === "operate" ? "Prospecção" : "Gestão comercial")}
        </span>
        <nav
          className={`${styles.links} context-navigation`}
          aria-label={tr("Navegação principal")}
        >
          {navigation
            .filter((item) => item.environment === environment)
            .map((item) => (
              <button
                key={item.id}
                aria-current={page === item.id ? "page" : undefined}
                onClick={() => navigate(item.id)}
              >
                <item.icon size={18} />
                <span>{tr(item.label)}</span>
              </button>
            ))}
        </nav>
        <nav className={styles.secondary} aria-label={tr("Ferramentas de trabalho")}>
          {[
            ...(environment === "operate" ? navigation.filter(item => item.id === "actions") : []),
            ...globalNavigation.filter(item => ["automations", "integrations"].includes(item.id)),
          ].map(item => <button key={item.id} onClick={() => navigate(item.id)} aria-current={page === item.id ? "page" : undefined}><item.icon size={18}/><span>{tr(item.label)}</span></button>)}
        </nav>
        <span className={styles.date}>
          {new Intl.DateTimeFormat(user.locale, {
            day: "2-digit",
            month: "short",
            timeZone: user.timezone,
          }).format(new Date())}
        </span>
        </div>
      </div>
      {offline && (
        <div className={`${styles.offline} connection-notice`} role="status">
          <WifiOff size={17} />
          {tr(
            "Você está offline. Os dados exibidos podem estar desatualizados.",
          )}
          <button className="text-link" onClick={onRefresh}>
            {tr("Tentar novamente")}
          </button>
        </div>
      )}
      <main
        className={styles.main}
        id="main-content"
        tabIndex={-1}
        aria-label={tr(active?.label || "Radar")}
      >
        {environment === "manage" &&
          ["pipeline", "clients", "sites", "finance"].includes(page) && (
            <section
              className="management-context"
              aria-label={tr("Atenção agora")}
            >
              <div className="management-context-title">
                <span className="eyebrow">{tr("Atenção agora")}</span>
                <span>
                  {overdue.length + payments.length
                    ? tr("Pendências da operação")
                    : tr("Nenhuma pendência para hoje")}
                </span>
              </div>
              {overdue[0] && (
                <button
                  className="context-action"
                  onClick={() => onSelect(overdue[0])}
                >
                  <span>
                    <b>{overdue[0].name}</b>
                    <small>{overdue[0].next_action}</small>
                  </span>
                  <span>
                    {overdue.length > 1 ? `+${overdue.length - 1}` : tr("Hoje")}
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              )}
              {payments[0] && (
                <button
                  className="context-action"
                  onClick={() => navigate("finance")}
                >
                  <span>
                    <b>{tr("Recebimentos pendentes")}</b>
                    <small>{payments[0].company}</small>
                  </span>
                  <span>
                    {money(
                      payments[0].amount_cents - payments[0].received_cents,
                      payments[0].currency,
                    )}
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              )}
            </section>
          )}
        {children}
      </main>
    </div>
  );
}

export function Notice({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  return (
    <div className="workspace-notice" role="status">
      <span className="notice-mark" />
      <span>{tr(message)}</span>
      <button
        className="icon-button"
        aria-label={tr("Fechar notificação")}
        onClick={onClose}
      >
        <X size={17} />
      </button>
    </div>
  );
}
