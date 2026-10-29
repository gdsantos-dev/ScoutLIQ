import { tr } from "../i18n";
import { useState } from "react";
import { Search, ArrowUpRight, Check, Trash2 } from "lucide-react";
import type { Payment, Sale } from "../types";
import { money, dateLabel } from "../types";
import { Confirm, Empty, Modal, PageHead } from "../components/UI";
import { SmartSelect } from "../components/Primitives";
export default function Clients({
  sales,
  onPayment,
  onStatus,
  onDeleteSale,
  onDeletePayment,
  onSelectLead,
}: {
  sales: Sale[];
  onPayment: (s: Sale) => void;
  onStatus: (s: Sale, status: string) => Promise<void>;
  onDeleteSale: (s: Sale) => Promise<void>;
  onDeletePayment: (s: Sale, p: Payment) => Promise<void>;
  onSelectLead: (leadId: string) => void;
}) {
  const [filter, setFilter] = useState("all"),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState<string | null>(null),
    [busy, setBusy] = useState(false),
    [deleteError, setDeleteError] = useState(""),
    [removing, setRemoving] = useState<
      | { kind: "sale"; sale: Sale }
      | { kind: "payment"; sale: Sale; payment: Payment }
      | null
    >(null);
  const items = sales.filter(
      (s) =>
        (filter === "all" ||
          (filter === "recurring" &&
            s.recurring_cents > 0 &&
            s.project_status !== "finished") ||
          s.project_status === filter) &&
        s.company.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
    ),
    sale = sales.find((s) => s.id === selected);
  return (
    <>
      <PageHead title={tr("Clientes")} eyebrow="CLIENTES">
        <span className="count-label">
          {sales.length} {sales.length === 1 ? "cliente" : "clientes"}
        </span>
      </PageHead>
      <div className="filter-bar">
        <div className="tabs">
          {[
            ["all", "Todos"],
            ["active", "Ativos"],
            ["progress", "Em andamento"],
            ["recurring", "Recorrentes"],
            ["finished", "Finalizados"],
          ].map(([id, label]) => (
            <button
              key={id}
              className={id === filter ? "active" : ""}
              onClick={() => setFilter(id)}
            >
              {tr(label)}
            </button>
          ))}
        </div>
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label={tr("Buscar cliente")}
            placeholder={tr("Buscar cliente")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      <div className="panel table-panel management-desktop-table">
        {items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{tr("Empresa")}</th>
                  <th>{tr("Serviço")}</th>
                  <th>{tr("Valor")}</th>
                  <th>{tr("Projeto")}</th>
                  <th>{tr("Recebido")}</th>
                  <th>
                    <span className="sr-only">Ação</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <button
                        className="company-cell"
                        onClick={() => onSelectLead(s.lead_id)}
                      >
                        <span className="table-avatar">
                          {s.company.slice(0, 1)}
                        </span>
                        <span>
                          <strong>{s.company}</strong>
                          <small>
                            {s.contact || dateLabel(s.sold_on)}
                            {s.demo ? " · Exemplo" : ""}
                          </small>
                        </span>
                      </button>
                    </td>
                    <td data-label={tr("Serviço")}>
                      {s.service}
                      {s.recurring_cents > 0 && (
                        <small className="cell-note">
                          + {money(s.recurring_cents, s.currency)}/mês
                        </small>
                      )}
                    </td>
                    <td className="numeric" data-label={tr("Valor")}>
                      {money(s.amount_cents, s.currency)}
                    </td>
                    <td data-label={tr("Projeto")}>
                      <span className={`badge status-${s.project_status}`}>
                        {tr(
                          s.project_status === "progress"
                            ? "Em andamento"
                            : s.project_status === "active"
                              ? "Ativo"
                              : "Finalizado",
                        )}
                      </span>
                    </td>
                    <td className="numeric" data-label={tr("Recebido")}>
                      {s.received_cents === s.amount_cents ? (
                        <span className="paid-label">
                          <Check size={14} />
                          {tr("Quitado")}
                        </span>
                      ) : (
                        money(s.received_cents, s.currency)
                      )}
                    </td>
                    <td>
                      <div className="table-row-actions">
                        <button
                          className="icon-button"
                          aria-label={`Abrir ${s.company}`}
                          onClick={() => setSelected(s.id)}
                        >
                          <ArrowUpRight size={18} />
                        </button>
                        <button
                          type="button"
                          className="icon-button danger-ghost"
                          aria-label={`Excluir venda de ${s.company}`}
                          onClick={() => {
                            setDeleteError("");
                            setRemoving({ kind: "sale", sale: s });
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={tr("Nenhum cliente encontrado.")}
            description="Ao registrar uma venda no Pipeline, o cliente aparece aqui."
          />
        )}
      </div>
      <section className="management-mobile-list client-mobile-list" aria-label={tr("Clientes")}>
        {items.length ? (
          items.map((s) => (
            <article className="management-mobile-row client-mobile-row" key={s.id}>
              <div className="management-mobile-row-head">
                <button
                  className="management-mobile-identity"
                  onClick={() => setSelected(s.id)}
                >
                  <span className="table-avatar">{s.company.slice(0, 1)}</span>
                  <span>
                    <strong>{s.company}</strong>
                    <small>
                      {s.contact || dateLabel(s.sold_on)}
                      {s.demo ? " · Exemplo" : ""}
                    </small>
                  </span>
                </button>
                <span className={`badge status-${s.project_status}`}>
                  {tr(
                    s.project_status === "progress"
                      ? "Em andamento"
                      : s.project_status === "active"
                        ? "Ativo"
                        : "Finalizado",
                  )}
                </span>
              </div>
              <div className="management-mobile-service">
                <span>{s.service}</span>
                {s.recurring_cents > 0 && (
                  <small>+ {money(s.recurring_cents, s.currency)}/mês</small>
                )}
              </div>
              <div className="management-mobile-metrics">
                <div>
                  <span>{tr("Venda")}</span>
                  <b>{money(s.amount_cents, s.currency)}</b>
                </div>
                <div>
                  <span>{tr("Recebido")}</span>
                  <b>
                    {s.received_cents === s.amount_cents
                      ? tr("Quitado")
                      : money(s.received_cents, s.currency)}
                  </b>
                </div>
              </div>
              <div className="management-mobile-actions">
                <button className="text-link" onClick={() => onSelectLead(s.lead_id)}>
                  {tr("Contexto")}
                  <ArrowUpRight size={15} />
                </button>
                {s.received_cents < s.amount_cents && (
                  <button className="button small" onClick={() => onPayment(s)}>
                    {tr("Receber")}
                  </button>
                )}
                <button className="button small" onClick={() => setSelected(s.id)}>
                  {tr("Detalhes")}
                </button>
              </div>
            </article>
          ))
        ) : (
          <Empty
            title={tr("Nenhum cliente encontrado.")}
            description="Ao registrar uma venda no Pipeline, o cliente aparece aqui."
          />
        )}
      </section>
      {sale && (
        <Modal title={sale.company} onClose={() => setSelected(null)}>
          <button
            className="text-link client-context-link"
            onClick={() => {
              setSelected(null);
              onSelectLead(sale.lead_id);
            }}
          >
            {tr("Contexto do cliente")}
            <ArrowUpRight size={16} />
          </button>
          <p className="muted">
            {sale.service} · {dateLabel(sale.sold_on)}
          </p>
          <div className="detail-summary">
            <div>
              <span>{tr("Venda")}</span>
              <b>{money(sale.amount_cents, sale.currency)}</b>
            </div>
            <div>
              <span>{tr("Recebido")}</span>
              <b>{money(sale.received_cents, sale.currency)}</b>
            </div>
            <div>
              <span>{tr("Manutenção mensal")}</span>
              <b>{money(sale.recurring_cents, sale.currency)}</b>
            </div>
          </div>
          <div className="field">
            <span>{tr("Status do projeto")}</span>
            <SmartSelect
              ariaLabel={tr("Status do projeto")}
              value={sale.project_status}
              disabled={busy}
              onChange={async (next) => {
                setBusy(true);
                try {
                  await onStatus(sale, next);
                } finally {
                  setBusy(false);
                }
              }}
              options={[
                { value: "progress", label: "Em andamento" },
                { value: "active", label: "Ativo" },
                { value: "finished", label: "Finalizado" },
              ]}
            />
          </div>
          <h3 className="subsection-heading">{tr("Recebimentos")}</h3>
          {sale.payments.length ? (
            sale.payments.map((p) => (
              <div className="ledger-line" key={p.id}>
                <span>{dateLabel(p.paid_on)}</span>
                <b>{money(p.amount_cents, p.currency)}</b>
                <button
                  type="button"
                  className="icon-button danger-ghost"
                  aria-label={`Excluir recebimento de ${money(p.amount_cents, p.currency)}`}
                  onClick={() => {
                    setDeleteError("");
                    setRemoving({ kind: "payment", sale, payment: p });
                  }}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))
          ) : (
            <p className="muted">Nenhum recebimento registrado.</p>
          )}
          <div className="form-actions client-sale-actions">
            {sale.received_cents < sale.amount_cents && (
              <button
                className="button primary"
                onClick={() => {
                  setSelected(null);
                  onPayment(sale);
                }}
              >
                Registrar recebimento
              </button>
            )}
            <button
              type="button"
              className="button danger-outline"
              onClick={() => {
                setDeleteError("");
                setRemoving({ kind: "sale", sale });
              }}
            >
              <Trash2 size={16} />
              Excluir venda
            </button>
          </div>
        </Modal>
      )}
      {removing && (
        <Confirm
          title={
            removing.kind === "sale"
              ? `Excluir venda de ${removing.sale.company}?`
              : "Excluir recebimento?"
          }
          description={
            removing.kind === "sale"
              ? "A venda, os recebimentos e qualquer registro de site vinculado serão removidos. O estabelecimento não será apagado e voltará para Encontrado no Pipeline."
              : `O recebimento de ${money(removing.payment.amount_cents, removing.payment.currency)} será removido e os totais financeiros serão recalculados.`
          }
          label={
            removing.kind === "sale" ? "Excluir venda" : "Excluir recebimento"
          }
          busy={busy}
          error={deleteError}
          onClose={() => {
            if (!busy) setRemoving(null);
          }}
          onConfirm={() => {
            void (async () => {
              setBusy(true);
              setDeleteError("");
              try {
                if (removing.kind === "sale") {
                  await onDeleteSale(removing.sale);
                  setSelected(null);
                } else {
                  await onDeletePayment(removing.sale, removing.payment);
                }
                setRemoving(null);
              } catch (error) {
                setDeleteError((error as Error).message);
              } finally {
                setBusy(false);
              }
            })();
          }}
        />
      )}
    </>
  );
}
