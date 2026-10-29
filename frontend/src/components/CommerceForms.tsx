import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api";
import { cents, inputDate, money } from "../types";
import type { Campaign, Currency, Lead, Sale } from "../types";
import { Modal, Field, ErrorText, Submit } from "./UI";
import { DateField, SmartSelect } from "./Primitives";
import { currencyOptions, tr } from "../i18n";

export function SaleForm({
  lead,
  timezone,
  defaultCurrency,
  onClose,
  onSaved,
}: {
  lead: Lead;
  timezone: string;
  defaultCurrency: Currency;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [campaigns, setCampaigns] = useState<Campaign[]>([]),
    today = inputDate(timezone);
  useEffect(() => {
    let alive = true;
    api<Campaign[]>("/campaigns")
      .then((items) => { if (alive) setCampaigns(items.filter((item) => item.status === "active")); })
      .catch(() => { if (alive) setCampaigns([]); });
    return () => { alive = false; };
  }, []);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const d = new FormData(e.currentTarget);
    try {
      await api("/sales", "POST", {
        lead_id: lead.id,
        campaign_id: d.get("campaign_id") || null,
        service: d.get("service"),
        amount_cents: cents(d.get("amount")),
        currency: d.get("currency") || defaultCurrency,
        recurring_cents: cents(d.get("recurring")),
        sold_on: d.get("sold_on"),
        due_on: d.get("due_on"),
      });
      await onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={tr("Registrar venda")} onClose={onClose}>
      <p className="form-context">{lead.name}</p>
      {lead.demo && <p className="notice">{tr("Esta venda será de demonstração.")}</p>}
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label={tr("Serviço vendido")} className="span-2">
            <input
              autoFocus
              name="service"
              required
              minLength={2}
              maxLength={160}
              placeholder={tr("Ex.: Site institucional")}
            />
          </Field>
          <Field label={tr("Moeda")}>
            <SmartSelect name="currency" defaultValue={lead.potential_currency || defaultCurrency} ariaLabel={tr("Moeda")} options={currencyOptions} />
          </Field>
          <Field label={tr("Campanha")}>
            <SmartSelect name="campaign_id" defaultValue="" ariaLabel={tr("Campanha")} options={[{ value: "", label: tr("Atribuição automática") }, ...campaigns.map((item) => ({ value: item.id, label: item.name }))]} />
          </Field>
          <Field label={tr("Valor da venda")}>
            <input
              name="amount"
              type="number"
              min="0.01"
              max="10000000"
              step="0.01"
              required
              defaultValue={
                lead.potential_cents ? lead.potential_cents / 100 : ""
              }
            />
          </Field>
          <Field label={tr("Manutenção mensal")}>
            <input
              name="recurring"
              type="number"
              min="0"
              max="10000000"
              step="0.01"
              defaultValue="0"
            />
          </Field>
          <Field label={tr("Data da venda")}>
            <DateField
              name="sold_on"
              defaultValue={today}
              max={today}
              ariaLabel="Data da venda"
            />
          </Field>
          <Field label={tr("Vencimento")}>
            <DateField
              name="due_on"
              defaultValue={today}
              ariaLabel="Vencimento"
            />
          </Field>
        </div>
        <p className="field-hint">
          O cliente será criado ao fechar a venda. Registre os pagamentos em
          Financeiro conforme receber.
        </p>
        <ErrorText error={error} />
        <div className="form-actions">
          <Submit busy={busy}>{tr("Concluir venda")}</Submit>
        </div>
      </form>
    </Modal>
  );
}
export function PaymentForm({
  sale,
  timezone,
  onClose,
  onSaved,
}: {
  sale: Sale;
  timezone: string;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    id = useRef(crypto.randomUUID()),
    today = inputDate(timezone);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const d = new FormData(e.currentTarget);
    try {
      await api(`/sales/${sale.id}/payments`, "POST", {
        amount_cents: cents(d.get("amount")),
        currency: sale.currency,
        paid_on: d.get("paid_on"),
        request_id: id.current,
      });
      await onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={tr("Registrar recebimento")} onClose={onClose}>
      <p className="form-context">{sale.company}</p>
      <p className="muted">
        {tr("Saldo")}: {money(sale.amount_cents - sale.received_cents, sale.currency)}
      </p>
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label={`${tr("Valor recebido")} · ${sale.currency}`}>
            <input
              autoFocus
              name="amount"
              type="number"
              min="0.01"
              max={(sale.amount_cents - sale.received_cents) / 100}
              step="0.01"
              required
            />
          </Field>
          <Field label={tr("Data do recebimento")}>
            <DateField
              name="paid_on"
              min={sale.sold_on}
              max={today}
              defaultValue={today}
              ariaLabel="Data do recebimento"
            />
          </Field>
        </div>
        <ErrorText error={error} />
        <div className="form-actions">
          <Submit busy={busy}>{tr("Salvar recebimento")}</Submit>
        </div>
      </form>
    </Modal>
  );
}
export function ExpenseForm({
  timezone,
  defaultCurrency,
  onClose,
  onSaved,
}: {
  timezone: string;
  defaultCurrency: Currency;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    id = useRef(crypto.randomUUID());
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const d = new FormData(e.currentTarget);
    try {
      await api("/expenses", "POST", {
        description: d.get("description"),
        amount_cents: cents(d.get("amount")),
        currency: d.get("currency") || defaultCurrency,
        incurred_on: d.get("incurred_on"),
        request_id: id.current,
      });
      await onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={tr("Registrar custo")} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <Field label={tr("Descrição")} className="span-2">
            <input
              autoFocus
              name="description"
              minLength={2}
              maxLength={160}
              required
              placeholder={tr("Ex.: Hospedagem")}
            />
          </Field>
          <Field label={tr("Moeda")}>
            <SmartSelect name="currency" defaultValue={defaultCurrency} ariaLabel={tr("Moeda")} options={currencyOptions} />
          </Field>
          <Field label={tr("Valor")}>
            <input
              name="amount"
              type="number"
              min="0.01"
              max="10000000"
              step="0.01"
              required
            />
          </Field>
          <Field label={tr("Data")}>
            <DateField
              name="incurred_on"
              max={inputDate(timezone)}
              defaultValue={inputDate(timezone)}
              ariaLabel="Data do custo"
            />
          </Field>
        </div>
        <ErrorText error={error} />
        <div className="form-actions">
          <Submit busy={busy}>{tr("Salvar custo")}</Submit>
        </div>
      </form>
    </Modal>
  );
}
