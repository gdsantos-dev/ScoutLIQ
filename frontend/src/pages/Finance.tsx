import { lazy, Suspense, useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Download,
  Plus,
  Trash2,
} from "lucide-react";
import type { Currency, Dashboard, Sale, Expense } from "../types";
import { money, dateLabel } from "../types";
import { tr, currencyOptions } from "../i18n";
import { SmartSelect } from "../components/Primitives";
import { Confirm, Empty, PageHead, SectionTitle } from "../components/UI";
const TrendChart = lazy(() => import("../components/TrendChart"));
export default function Finance({
  dashboard,
  sales,
  expenses,
  onPayment,
  onExpense,
  onDeleteExpense,
  onDeleteSale,
  onExport,
  period,
  setPeriod,
  reduced,
}: {
  dashboard: Dashboard;
  sales: Sale[];
  expenses: Expense[];
  onPayment: (s: Sale) => void;
  onExpense: () => void;
  onDeleteExpense: (e: Expense) => void;
  onDeleteSale: (s: Sale) => Promise<void>;
  onExport: () => void;
  period: string;
  setPeriod: (value: string) => void;
  reduced: boolean;
}) {
  const [tab, setTab] = useState("receivable"),
    [currency, setCurrency] = useState<Currency>(dashboard.currency),
    [removingSale, setRemovingSale] = useState<Sale | null>(null),
    [busy, setBusy] = useState(false),
    [deleteError, setDeleteError] = useState(""),
    summary = dashboard.by_currency[currency] ?? {
      today_cents: 0,
      today_count: 0,
      previous_cents: 0,
      trend: [],
      revenue_cents: 0,
      received_cents: 0,
      cost_cents: 0,
      profit_cents: 0,
      receivable_cents: 0,
      recurring_cents: 0,
    },
    currencySales = sales.filter((s) => s.currency === currency),
    currencyExpenses = expenses.filter((e) => e.currency === currency),
    pending = currencySales.filter((s) => s.received_cents < s.amount_cents);
  const payments = currencySales
    .flatMap((s) =>
      s.payments.map((p) => ({ ...p, company: s.company, demo: s.demo })),
    )
    .sort((a, b) => b.paid_on.localeCompare(a.paid_on));
  return (
    <>
      <PageHead
        title={tr("Financeiro")}
        eyebrow={tr("Financeiro").toUpperCase()}
      >
        <SmartSelect
          compact
          value={currency}
          onChange={(value) => setCurrency(value as Currency)}
          ariaLabel={tr("Moeda")}
          options={currencyOptions.filter(
            (option) =>
              dashboard.by_currency[option.value as Currency] ||
              option.value === dashboard.currency,
          )}
        />
        <button className="button" onClick={onExport}>
          <Download size={16} />
          {tr("Exportar dados")}
        </button>
        <button className="button primary" onClick={onExpense}>
          <Plus size={16} />
          {tr("Registrar custo")}
        </button>
      </PageHead>
      <div className="finance-summary panel">
        <div className="finance-main">
          <span>{tr("Resultado de caixa")}</span>
          <strong>{money(summary.profit_cents, currency)}</strong>
          <p>{tr("Recebimentos menos custos · todo o período")}</p>
        </div>
        <div className="finance-stat">
          <ArrowDownLeft size={19} />
          <span>{tr("Recebimentos")}</span>
          <b>{money(summary.received_cents, currency)}</b>
        </div>
        <div className="finance-stat">
          <ArrowUpRight size={19} />
          <span>{tr("Custos")}</span>
          <b>{money(summary.cost_cents, currency)}</b>
        </div>
      </div>
      <div className="finance-secondary">
        <div>
          <span>{tr("Vendas acumuladas")}</span>
          <b>{money(summary.revenue_cents, currency)}</b>
        </div>
        <div>
          <span>{tr("A receber")}</span>
          <b>{money(summary.receivable_cents, currency)}</b>
        </div>
        <div>
          <span>{tr("Recorrência contratada / mês")}</span>
          <b>{money(summary.recurring_cents, currency)}</b>
        </div>
      </div>
      <section className="finance-trend">
        <div>
          <h2>{tr("Evolução das vendas")}</h2>
          <SmartSelect
            ariaLabel={tr("Período")}
            value={period}
            onChange={setPeriod}
            options={[
              { value: "today", label: tr("Hoje") },
              { value: "7d", label: tr("7 dias") },
              { value: "30d", label: tr("30 dias") },
              { value: "month", label: tr("Este mês") },
            ]}
          />
        </div>
        <Suspense fallback={<div className="skeleton map-skeleton" />}>
          <TrendChart
            data={summary.trend}
            reduced={reduced}
            currency={currency}
          />
        </Suspense>
      </section>
      <section className="panel ledger">
        <SectionTitle title={tr("Movimentações")} />
        <div className="tabs">
          {[
            ["receivable", tr("A receber")],
            ["sales", tr("Vendas")],
            ["payments", tr("Recebimentos")],
            ["expenses", tr("Custos")],
          ].map(([id, label]) => (
            <button
              key={id}
              className={tab === id ? "active" : ""}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="table-scroll management-desktop-table">
          <table>
            <thead>
              <tr>
                <th>{tr(tab === "expenses" ? "Descrição" : "Empresa")}</th>
                <th>{tr(tab === "receivable" ? "Vencimento" : "Data")}</th>
                <th>{tr("Valor")}</th>
                <th>
                  <span className="sr-only">{tr("Ação")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {tab === "receivable" &&
                pending.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <strong>{s.company}</strong>
                      <small className="cell-note">
                        {s.service}
                        {s.demo ? ` · ${tr("Exemplo")}` : ""}
                      </small>
                    </td>
                    <td data-label={tr("Vencimento")}>
                      <span
                        className={s.due_on < dashboard.today ? "overdue" : ""}
                      >
                        {dateLabel(s.due_on)}
                        {s.due_on < dashboard.today
                          ? ` · ${tr("Vencido")}`
                          : ""}
                      </span>
                    </td>
                    <td data-label={tr("Valor")} className="numeric">
                      {money(s.amount_cents - s.received_cents, s.currency)}
                    </td>
                    <td>
                      <button
                        className="button small"
                        onClick={() => onPayment(s)}
                      >
                        {tr("Receber")}
                      </button>
                    </td>
                  </tr>
                ))}
              {tab === "sales" &&
                [...currencySales]
                  .sort((a, b) => b.sold_on.localeCompare(a.sold_on))
                  .map((s) => (
                    <tr key={s.id}>
                      <td>
                        <strong>{s.company}</strong>
                        <small className="cell-note">
                          {s.service}
                          {s.demo ? ` · ${tr("Exemplo")}` : ""}
                        </small>
                      </td>
                      <td data-label={tr("Data")}>{dateLabel(s.sold_on)}</td>
                      <td data-label={tr("Valor")} className="numeric">
                        {money(s.amount_cents, s.currency)}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="icon-button danger-ghost"
                          aria-label={`Excluir venda de ${s.company}`}
                          onClick={() => {
                            setDeleteError("");
                            setRemovingSale(s);
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
              {tab === "payments" &&
                payments.map((p) => (
                  <tr key={p.id}>
                    <td>
                      {p.company}
                      {p.demo && (
                        <small className="cell-note">{tr("Exemplo")}</small>
                      )}
                    </td>
                    <td data-label={tr("Data")}>{dateLabel(p.paid_on)}</td>
                    <td data-label={tr("Valor")} className="numeric positive">
                      {money(p.amount_cents, p.currency)}
                    </td>
                    <td>{tr("Recebido")}</td>
                  </tr>
                ))}
              {tab === "expenses" &&
                currencyExpenses.map((e) => (
                  <tr key={e.id}>
                    <td>
                      {e.description}
                      {e.demo && (
                        <small className="cell-note">{tr("Exemplo")}</small>
                      )}
                    </td>
                    <td data-label={tr("Data")}>{dateLabel(e.incurred_on)}</td>
                    <td data-label={tr("Valor")} className="numeric">
                      {money(e.amount_cents, e.currency)}
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`Excluir custo ${e.description}`}
                        onClick={() => onDeleteExpense(e)}
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="management-mobile-list finance-mobile-ledger">
          {tab === "receivable" &&
            pending.map((s) => (
              <article className="management-mobile-row finance-mobile-row" key={s.id}>
                <div className="finance-mobile-primary">
                  <span>
                    <strong>{s.company}</strong>
                    <small>
                      {s.service}
                      {s.demo ? ` · ${tr("Exemplo")}` : ""}
                    </small>
                  </span>
                  <b>{money(s.amount_cents - s.received_cents, s.currency)}</b>
                </div>
                <div className="finance-mobile-meta">
                  <span className={s.due_on < dashboard.today ? "overdue" : ""}>
                    {tr("Vencimento")}: {dateLabel(s.due_on)}
                    {s.due_on < dashboard.today ? ` · ${tr("Vencido")}` : ""}
                  </span>
                  <button className="button small" onClick={() => onPayment(s)}>
                    {tr("Receber")}
                  </button>
                </div>
              </article>
            ))}
          {tab === "sales" &&
            [...currencySales]
              .sort((a, b) => b.sold_on.localeCompare(a.sold_on))
              .map((s) => (
                <article className="management-mobile-row finance-mobile-row" key={s.id}>
                  <div className="finance-mobile-primary">
                    <span>
                      <strong>{s.company}</strong>
                      <small>
                        {s.service}
                        {s.demo ? ` · ${tr("Exemplo")}` : ""}
                      </small>
                    </span>
                    <b>{money(s.amount_cents, s.currency)}</b>
                  </div>
                  <div className="finance-mobile-meta">
                    <span>{dateLabel(s.sold_on)}</span>
                    <button
                      type="button"
                      className="icon-button danger-ghost"
                      aria-label={`Excluir venda de ${s.company}`}
                      onClick={() => {
                        setDeleteError("");
                        setRemovingSale(s);
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </article>
              ))}
          {tab === "payments" &&
            payments.map((p) => (
              <article className="management-mobile-row finance-mobile-row" key={p.id}>
                <div className="finance-mobile-primary">
                  <span>
                    <strong>{p.company}</strong>
                    <small>{p.demo ? tr("Exemplo") : tr("Recebimento")}</small>
                  </span>
                  <b className="positive">{money(p.amount_cents, p.currency)}</b>
                </div>
                <div className="finance-mobile-meta">
                  <span>{dateLabel(p.paid_on)}</span>
                  <span>{tr("Recebido")}</span>
                </div>
              </article>
            ))}
          {tab === "expenses" &&
            currencyExpenses.map((e) => (
              <article className="management-mobile-row finance-mobile-row" key={e.id}>
                <div className="finance-mobile-primary">
                  <span>
                    <strong>{e.description}</strong>
                    <small>{e.demo ? tr("Exemplo") : tr("Custo")}</small>
                  </span>
                  <b>{money(e.amount_cents, e.currency)}</b>
                </div>
                <div className="finance-mobile-meta">
                  <span>{dateLabel(e.incurred_on)}</span>
                  <button
                    className="icon-button danger-ghost"
                    aria-label={`Excluir custo ${e.description}`}
                    onClick={() => onDeleteExpense(e)}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </article>
            ))}
        </div>
        {((tab === "receivable" && !pending.length) ||
          (tab === "sales" && !currencySales.length) ||
          (tab === "payments" && !payments.length) ||
          (tab === "expenses" && !currencyExpenses.length)) && (
          <Empty
            title={
              tab === "receivable"
                ? "Tudo em dia."
                : "Nenhuma movimentação por aqui."
            }
            description={
              tab === "receivable"
                ? "Não há valores pendentes de recebimento."
                : "Registre a primeira movimentação para acompanhar seus resultados."
            }
          />
        )}
      </section>
      <p className="field-hint">
        {tr(
          "Recorrência é o valor mensal contratado dos projetos ativos e em andamento. Cobranças recorrentes não são geradas automaticamente.",
        )}
      </p>
      {removingSale && (
        <Confirm
          title={`Excluir venda de ${removingSale.company}?`}
          description="A venda, os recebimentos e qualquer registro de site vinculado serão removidos. O estabelecimento não será apagado e voltará para Encontrado no Pipeline."
          label={tr("Excluir venda")}
          busy={busy}
          error={deleteError}
          onClose={() => {
            if (!busy) setRemovingSale(null);
          }}
          onConfirm={() => {
            void (async () => {
              setBusy(true);
              setDeleteError("");
              try {
                await onDeleteSale(removingSale);
                setRemovingSale(null);
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
