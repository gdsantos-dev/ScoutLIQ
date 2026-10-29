import { useId, useState } from "react";
import { api } from "../api";
import { tr } from "../i18n";
import type { Lead } from "../types";
import "./commercial-review.css";

const fields = [
  [
    "independence",
    "Autonomia",
    [
      ["unknown", "Não verificada"],
      ["independent", "Independente / autonomia local verificada"],
      ["centralized", "Centralizada"],
    ],
  ],
  [
    "operating_status",
    "Operação",
    [
      ["unknown", "Não verificada"],
      ["active", "Ativa"],
      ["closed", "Encerrada"],
    ],
  ],
  [
    "business_type",
    "Modelo comercial",
    [
      ["unknown", "Não verificado"],
      ["local", "Atendimento local"],
      ["b2b", "B2B verificado"],
    ],
  ],
  [
    "size",
    "Porte",
    [
      ["unknown", "Não verificado"],
      ["small_medium", "Pequena ou média"],
      ["large", "Grande organização"],
    ],
  ],
  [
    "entity_type",
    "Natureza",
    [
      ["unknown", "Não verificada"],
      ["commercial", "Empresa comercial verificada"],
      ["public", "Entidade pública"],
    ],
  ],
] as const;

export default function CommercialReview({
  lead,
  onUpdated,
}: {
  lead: Lead;
  onUpdated: (lead: Lead) => void;
}) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [version, setVersion] = useState(lead.version);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  function begin() {
    setValues(
      Object.fromEntries(
        fields.map(([key]) => [key, lead.qualification?.[key] || "unknown"]),
      ),
    );
    setVersion(lead.version);
    setReason("");
    setError("");
    setNotice("");
    setEditing(true);
  }
  async function save(confirmExisting = false) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<Lead>(
        `/smart-searches/leads/${lead.id}/review`,
        "POST",
        {
          ...(confirmExisting
            ? Object.fromEntries(
                fields.map(([key]) => [
                  key,
                  lead.qualification?.[key] || "unknown",
                ]),
              )
            : values),
          version: confirmExisting ? lead.version : version,
          confirm_existing: confirmExisting,
          reason: reason.trim(),
        },
      );
      onUpdated(updated);
      window.dispatchEvent(new Event("scout:qualification-reviewed"));
      setEditing(false);
      setNotice(tr("Revisão registrada."));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="commercial-review" aria-label={tr("Revisão comercial")}>
      <div className="commercial-review-heading">
        <h3>{tr("Revisão comercial")}</h3>
        {!editing && (
          <div className="form-actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => void save(true)}
            >
              {tr("Confirmar avaliação atual")}
            </button>
            <button className="button" disabled={busy} onClick={begin}>
              {tr("Revisar dados comerciais")}
            </button>
          </div>
        )}
      </div>
      {!editing ? (
        <>
          <dl>
            {fields.map(([key, label, options]) => (
              <div key={key}>
                <dt>{tr(label)}</dt>
                <dd>
                  {tr(
                    options.find(
                      ([value]) => value === lead.qualification?.[key],
                    )?.[1] || options[0][1],
                  )}
                </dd>
              </div>
            ))}
          </dl>
          {lead.qualification?.review_reason && (
            <p>{lead.qualification.review_reason}</p>
          )}
        </>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <div className="commercial-review-fields">
            {fields.map(([key, label, options]) => (
              <div key={key}>
                <label htmlFor={`${id}-${key}`}>{tr(label)}</label>
                <select
                  id={`${id}-${key}`}
                  value={values[key]}
                  disabled={busy}
                  onChange={(e) =>
                    setValues((current) => ({
                      ...current,
                      [key]: e.target.value,
                    }))
                  }
                >
                  {options.map(([value, name]) => (
                    <option key={value} value={value}>
                      {tr(name)}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          <label htmlFor={`${id}-reason`}>{tr("Evidência e motivo")}</label>
          <textarea
            id={`${id}-reason`}
            required
            minLength={10}
            maxLength={500}
            value={reason}
            disabled={busy}
            onChange={(e) => setReason(e.target.value)}
          />
          {error && <p role="alert">{error}</p>}
          <div className="form-actions">
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => setEditing(false)}
            >
              {tr("Cancelar")}
            </button>
            <button
              className="button primary"
              disabled={busy || reason.trim().length < 10}
            >
              {tr(busy ? "Salvando…" : "Registrar revisão")}
            </button>
          </div>
        </form>
      )}
      {!editing && error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
