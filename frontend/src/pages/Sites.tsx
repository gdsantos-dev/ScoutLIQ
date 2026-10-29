import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Plus, Search, RefreshCw, Pencil, Trash2 } from "lucide-react";
import { api } from "../api";
import type { Currency, Lead, Sale } from "../types";
import { activeCurrency, money, cents, dateLabel } from "../types";
import { currencyOptions, tr } from "../i18n";
import {
  PageHead,
  Modal,
  Field,
  Submit,
  ErrorText,
  Empty,
  Confirm,
  ExternalLink,
} from "../components/UI";
import { DateField, SmartSelect } from "../components/Primitives";

type Site = {
  id: string;
  sale_id: string;
  name: string;
  url: string;
  domain: string;
  domain_owner: string;
  renewal_on: string | null;
  hosting: string;
  plan: string;
  maintenance: string;
  monthly_revenue_cents: number;
  monthly_cost_cents: number;
  annual_domain_cost_cents: number;
  currency: Currency;
  monthly_margin_cents: number;
  ssl_status: string;
  ssl_expires_on: string | null;
  analytics_url: string;
  repository_url: string;
  admin_url: string;
  status: string;
  notes: string;
  demo: boolean;
  version: number;
  alerts: string[];
};
const statuses = {
  building: "Em construção",
  active: "Ativo",
  paused: "Pausado",
  issue: "Com problema",
  archived: "Arquivado",
};
const sslStates = {
  unknown: "Não informado",
  valid: "Válido",
  expiring: "A vencer",
  issue: "Com problema",
};

function SiteForm({
  item,
  sales,
  leads,
  onClose,
  onSaved,
}: {
  item: Site | null;
  sales: Sale[];
  leads: Lead[];
  onClose: () => void;
  onSaved: (site: Site) => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(e.currentTarget);
    const fields = [
      "sale_id",
      "currency",
      "name",
      "url",
      "domain",
      "domain_owner",
      "hosting",
      "plan",
      "maintenance",
      "ssl_status",
      "analytics_url",
      "repository_url",
      "admin_url",
      "status",
      "notes",
    ];
    const body: Record<string, unknown> = Object.fromEntries(
      fields.map((key) => [key, form.get(key)]),
    );
    for (const key of ["renewal_on", "ssl_expires_on"])
      body[key] = form.get(key) || null;
    for (const key of [
      "monthly_revenue_cents",
      "monthly_cost_cents",
      "annual_domain_cost_cents",
    ])
      body[key] = cents(form.get(key));
    if (item) body.version = item.version;
    try {
      onSaved(
        await api<Site>(
          item ? `/sites/${item.id}` : "/sites",
          item ? "PUT" : "POST",
          body,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const text = (key: keyof Site, label: string, max = 160, type = "text") => (
    <Field label={label}>
      {type === "date" ? (
        <DateField
          name={String(key)}
          defaultValue={String(item?.[key] ?? "")}
          ariaLabel={label}
        />
      ) : (
        <input
          name={key}
          type={type}
          maxLength={max}
          defaultValue={String(item?.[key] ?? "")}
        />
      )}
    </Field>
  );
  return (
    <Modal title={item ? "Editar site" : "Novo site"} onClose={onClose} wide>
      <form onSubmit={submit} className="site-form">
        <div className="form-grid">
          <Field label={tr("Cliente")}>
            <SmartSelect
              ariaLabel="Cliente"
              name="sale_id"
              defaultValue={item?.sale_id ?? ""}
              placeholder={tr("Selecionar cliente")}
              options={[
                { value: "", label: "Selecionar cliente", disabled: true },
                ...sales.map((sale) => {
                  const lead = leads.find((entry) => entry.id === sale.lead_id);
                  return {
                    value: sale.id,
                    label: sale.company,
                    meta: [lead?.city, lead?.address || lead?.phone || sale.service, sale.demo ? "Exemplo" : ""].filter(Boolean).join(" · "),
                  };
                }),
              ]}
            />
          </Field>
          <Field label={tr("Moeda")}>
            <SmartSelect
              name="currency"
              defaultValue={item?.currency ?? sales.find((sale) => sale.id === item?.sale_id)?.currency ?? activeCurrency()}
              ariaLabel={tr("Moeda")}
              options={currencyOptions}
            />
          </Field>
          <Field label={tr("Nome do site")}>
            <input
              name="name"
              required
              minLength={2}
              maxLength={160}
              defaultValue={item?.name ?? ""}
            />
          </Field>
          {text("url", "URL do site", 500, "url")}
          <Field label={tr("Status do site")}>
            <SmartSelect
              ariaLabel="Status do site"
              name="status"
              defaultValue={item?.status ?? "building"}
              options={Object.entries(statuses).map(([value, label]) => ({ value, label }))}
            />
          </Field>
          {text("domain", "Domínio", 253)}
          {text("domain_owner", "Titular do domínio")}
          {text("renewal_on", "Renovação do domínio", 10, "date")}
          {text("hosting", "Hospedagem")}
          {text("plan", "Plano de manutenção")}
          <Field label={tr("Receita mensal")}>
            <input
              name="monthly_revenue_cents"
              type="number"
              min="0"
              max="10000000"
              step="0.01"
              required
              defaultValue={(item?.monthly_revenue_cents ?? 0) / 100}
            />
          </Field>
          <Field label={tr("Custo mensal")}>
            <input
              name="monthly_cost_cents"
              type="number"
              min="0"
              max="10000000"
              step="0.01"
              required
              defaultValue={(item?.monthly_cost_cents ?? 0) / 100}
            />
          </Field>
          <Field label={tr("Custo anual do domínio")}>
            <input
              name="annual_domain_cost_cents"
              type="number"
              min="0"
              max="10000000"
              step="0.01"
              required
              defaultValue={(item?.annual_domain_cost_cents ?? 0) / 100}
            />
          </Field>
          <Field label={tr("Situação do SSL")}>
            <SmartSelect
              ariaLabel="Situação do SSL"
              name="ssl_status"
              defaultValue={item?.ssl_status ?? "unknown"}
              options={Object.entries(sslStates).map(([value, label]) => ({ value, label }))}
            />
          </Field>
          {text("ssl_expires_on", "Vencimento do SSL", 10, "date")}
        </div>
        <Field label={tr("Manutenção incluída")}>
          <textarea
            name="maintenance"
            rows={2}
            maxLength={3000}
            defaultValue={item?.maintenance ?? ""}
            placeholder="Hospedagem, domínio, suporte e pequenas alterações. Descreva o que foi contratado."
          />
        </Field>
        <details>
          <summary>Links e observações</summary>
          <div className="form-grid">
            {text("analytics_url", "Painel de analytics", 500, "url")}
            {text("repository_url", "Repositório", 500, "url")}
            {text("admin_url", "Painel administrativo", 500, "url")}
          </div>
          <p className="muted">
            Cadastre apenas os endereços dos painéis, sem senhas ou tokens.
          </p>
          <Field label={tr("Observações do site")}>
            <textarea
              name="notes"
              rows={3}
              maxLength={5000}
              defaultValue={item?.notes ?? ""}
            />
          </Field>
        </details>
        <ErrorText error={error} />
        <div className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <Submit busy={busy}>Salvar site</Submit>
        </div>
      </form>
    </Modal>
  );
}

export default function Sites({
  sales,
  leads,
}: {
  sales: Sale[];
  leads: Lead[];
}) {
  const [items, setItems] = useState<Site[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false),
    [deleteError, setDeleteError] = useState("");
  const [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [editing, setEditing] = useState<Site | null | undefined>(undefined),
    [selected, setSelected] = useState<Site | null>(null),
    [removing, setRemoving] = useState<Site | null>(null);
  async function load() {
    setLoading(true);
    setError("");
    try {
      setItems(await api<Site[]>("/sites"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    let active = true;
    api<Site[]>("/sites")
      .then((v) => {
        if (active) setItems(v);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const company = (s: Site) =>
    sales.find((v) => v.id === s.sale_id)?.company ?? "Cliente";
  const filtered = items.filter(
    (s) =>
      (filter === "all" ||
        (filter === "alerts" ? s.alerts.length > 0 : s.status === filter)) &&
      `${s.name} ${s.domain} ${company(s)}`
        .toLocaleLowerCase()
        .includes(query.toLocaleLowerCase()),
  );
  const active = items.filter((s) => s.status === "active");
  const summaryByCurrency = active.reduce<Record<string, { revenue:number; cost:number }>>((acc, site) => {
    const currency = site.currency || "BRL";
    const row = acc[currency] || { revenue: 0, cost: 0 };
    row.revenue += site.monthly_revenue_cents;
    row.cost += site.monthly_cost_cents;
    acc[currency] = row;
    return acc;
  }, {});
  const summaryText = (kind: "revenue" | "cost" | "margin") => Object.entries(summaryByCurrency).map(([currency, values]) => {
    const amount = kind === "margin" ? values.revenue - values.cost : values[kind];
    return money(amount, currency as Currency);
  }).join(" · ") || money(0);
  return (
    <>
      <PageHead title={tr("Sites")}>
        <button
          className="button primary"
          onClick={() => setEditing(null)}
          disabled={!sales.length}
        >
          <Plus size={16} />
          Novo site
        </button>
      </PageHead>
      <div className="site-summary">
        <span>
          <strong>{items.length}</strong> {items.length === 1 ? "site cadastrado" : "sites cadastrados"}
        </span>
        <span>
          Receita mensal <strong>{summaryText("revenue")}</strong>
        </span>
        <span>
          Custo mensal <strong>{summaryText("cost")}</strong>
        </span>
        <span>
          Margem mensal <strong>{summaryText("margin")}</strong>
        </span>
      </div>
      <p className="site-scope">
        Valores previstos dos sites ativos. Custos anuais de domínio são
        separados; recebimentos e despesas ficam no Financeiro.
      </p>
      <div className="filter-bar">
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label={tr("Buscar site")}
            placeholder="Site, domínio ou cliente"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <SmartSelect
          ariaLabel="Filtrar sites"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "Todos os sites" },
            { value: "alerts", label: "Com alertas" },
            ...Object.entries(statuses).map(([value, label]) => ({ value, label })),
          ]}
        />
        <button
          className="icon-button"
          aria-label={tr("Atualizar sites")}
          onClick={load}
          disabled={loading}
        >
          <RefreshCw size={17} />
        </button>
      </div>
      <ErrorText error={error} />
      <div className="panel table-panel management-desktop-table">
        {loading ? (
          <p className="site-loading" role="status">
            Carregando sites…
          </p>
        ) : filtered.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Site / cliente</th>
                  <th>{tr("Domínio")}</th>
                  <th>Status</th>
                  <th>Renovação</th>
                  <th>Margem / mês</th>
                  <th>Alertas</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <button
                        className="company-cell"
                        onClick={() => setSelected(s)}
                      >
                        <span>
                          <strong>{s.name}</strong>
                          <small>
                            {company(s)}
                            {s.demo ? " · Exemplo" : ""}
                          </small>
                        </span>
                      </button>
                    </td>
                    <td>{s.domain || "—"}</td>
                    <td>{statuses[s.status as keyof typeof statuses]}</td>
                    <td>{s.renewal_on ? dateLabel(s.renewal_on) : "—"}</td>
                    <td className="numeric">{money(s.monthly_margin_cents, s.currency)}</td>
                    <td>
                      {s.alerts.length ? (
                        <span className="site-alert">
                          {s.alerts.join(" · ")}
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={
              query || filter !== "all"
                ? "Nenhum site encontrado"
                : "Nenhum site cadastrado"
            }
            description={
              sales.length
                ? "Cadastre um site para acompanhar domínio, manutenção e custos."
                : "Registre uma venda para vincular o primeiro site a um cliente."
            }
          />
        )}
      </div>
      <section className="management-mobile-list site-mobile-list" aria-label={tr("Sites")}>
        {loading ? (
          <p className="site-loading" role="status">Carregando sites…</p>
        ) : filtered.length ? (
          filtered.map((s) => (
            <article className="management-mobile-row site-mobile-row" key={s.id}>
              <div className="management-mobile-row-head">
                <button
                  className="management-mobile-identity site-mobile-identity"
                  onClick={() => setSelected(s)}
                >
                  <span>
                    <strong>{s.name}</strong>
                    <small>
                      {company(s)}
                      {s.demo ? " · Exemplo" : ""}
                    </small>
                  </span>
                </button>
                <span className={`badge status-${s.status}`}>
                  {statuses[s.status as keyof typeof statuses]}
                </span>
              </div>
              <div className="site-mobile-domain">
                <span>{s.domain || "Domínio não informado"}</span>
                {s.renewal_on && <small>Renova em {dateLabel(s.renewal_on)}</small>}
              </div>
              <div className="management-mobile-metrics">
                <div>
                  <span>Margem / mês</span>
                  <b>{money(s.monthly_margin_cents, s.currency)}</b>
                </div>
                <div>
                  <span>Alertas</span>
                  <b>{s.alerts.length || "—"}</b>
                </div>
              </div>
              {s.alerts.length > 0 && (
                <p className="site-alert site-mobile-alert">{s.alerts.join(" · ")}</p>
              )}
              <div className="management-mobile-actions">
                {s.url && <ExternalLink href={s.url}>Abrir site</ExternalLink>}
                <button className="button small" onClick={() => setSelected(s)}>
                  {tr("Detalhes")}
                </button>
              </div>
            </article>
          ))
        ) : (
          <Empty
            title={query || filter !== "all" ? "Nenhum site encontrado" : "Nenhum site cadastrado"}
            description={
              sales.length
                ? "Cadastre um site para acompanhar domínio, manutenção e custos."
                : "Registre uma venda para vincular o primeiro site a um cliente."
            }
          />
        )}
      </section>
      <p className="site-scope">
        Alertas calculados pelas datas e situações cadastradas. Não há
        monitoramento automático de disponibilidade ou certificado.
      </p>
      {editing !== undefined && (
        <SiteForm
          item={editing}
          sales={sales}
          leads={leads}
          onClose={() => setEditing(undefined)}
          onSaved={(site) => {
            setItems((prev) =>
              [...prev.filter((s) => s.id !== site.id), site].sort((a, b) =>
                a.name.localeCompare(b.name),
              ),
            );
            setEditing(undefined);
            setSelected(null);
          }}
        />
      )}
      {selected && (
        <Modal title={selected.name} onClose={() => setSelected(null)} wide>
          <p>
            {company(selected)}
            {selected.demo ? " · Exemplo" : ""}
          </p>
          {selected.alerts.map((a) => (
            <p key={a} className="site-alert">
              {a}
            </p>
          ))}
          <dl className="site-details">
            {Object.entries({
              Domínio: selected.domain,
              Titular: selected.domain_owner,
              Renovação: selected.renewal_on,
              Hospedagem: selected.hosting,
              Plano: selected.plan,
              Status: statuses[selected.status as keyof typeof statuses],
              "Receita mensal": money(selected.monthly_revenue_cents, selected.currency),
              "Custo mensal": money(selected.monthly_cost_cents, selected.currency),
              "Margem mensal": money(selected.monthly_margin_cents, selected.currency),
              "Domínio / ano": money(selected.annual_domain_cost_cents, selected.currency),
              SSL: sslStates[selected.ssl_status as keyof typeof sslStates],
              "Vencimento SSL": selected.ssl_expires_on,
              "Manutenção incluída": selected.maintenance,
              Observações: selected.notes,
            }).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value || "Não informado"}</dd>
              </div>
            ))}
          </dl>
          <div className="site-links">
            {[
              [selected.url, "Abrir site"],
              [selected.analytics_url, "Analytics"],
              [selected.repository_url, "Repositório"],
              [selected.admin_url, "Painel administrativo"],
            ]
              .filter(([url]) => url)
              .map(([url, label]) => (
                <ExternalLink key={label} href={url}>
                  {label}
                </ExternalLink>
              ))}
          </div>
          <div className="modal-actions">
            <button
              className="button secondary"
              onClick={() => {
                setRemoving(selected);
                setSelected(null);
              }}
            >
              <Trash2 size={16} />
              Excluir registro
            </button>
            <button
              className="button primary"
              onClick={() => {
                setEditing(selected);
                setSelected(null);
              }}
            >
              <Pencil size={16} />
              Editar site
            </button>
          </div>
        </Modal>
      )}
      {removing && (
        <Confirm
          label={tr("Excluir registro")}
          busy={deleteBusy}
          error={deleteError}
          title={tr("Excluir registro do site?")}
          description={`O registro de ${removing.name} será removido. O site publicado e a venda do cliente permanecem intactos.`}
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            setDeleteBusy(true);
            setDeleteError("");
            try {
              await api(`/sites/${removing.id}`, "DELETE");
              setItems((prev) => prev.filter((s) => s.id !== removing.id));
              setRemoving(null);
            } catch (e) {
              setDeleteError((e as Error).message);
            } finally {
              setDeleteBusy(false);
            }
          }}
        />
      )}
    </>
  );
}
