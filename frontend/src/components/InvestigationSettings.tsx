import { useEffect, useState } from "react";
import { api } from "../api";
type Preferences = {
  search: boolean;
  absorption: boolean;
  allow_deep: boolean;
  execution_limit: number;
  daily_limit: number;
  operation_limit: number;
  daily_operation_limit: number;
  freshness_days: number;
};
const limits = [
  ["execution_limit", "Empresas por lote", 25],
  ["daily_limit", "Empresas por dia", 100],
  ["operation_limit", "Consultas por lote", 400],
  ["daily_operation_limit", "Consultas por dia", 500],
  ["freshness_days", "Reutilizar pesquisas por dias", 90],
] as const;
export default function InvestigationSettings() {
  const [data, setData] = useState<Preferences | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    void api<Preferences>("/investigation/preferences")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <section className="panel settings-panel investigation-settings">
      <h2>Investigação automática</h2>
      {error && <p role="alert">{error}</p>}
      {data && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            setSaved(false);
            try {
              setData(
                await api<Preferences>(
                  "/investigation/preferences",
                  "PUT",
                  data,
                ),
              );
              setSaved(true);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <p>
            Novas empresas entram na fila pelas fontes habilitadas. Nenhuma
            mensagem é enviada.
          </p>
          {(
            [
              ["search", "Novas empresas da Busca"],
              ["absorption", "Empresas confirmadas na Absorção"],
              ["allow_deep", "Auditoria seletiva de sites confirmados"],
            ] as const
          ).map(([key, label]) => (
            <label className="field" key={key}>
              <span>
                <input
                  type="checkbox"
                  checked={data[key]}
                  onChange={(e) => {
                    setData({ ...data, [key]: e.target.checked });
                    setSaved(false);
                  }}
                />{" "}
                {label}
              </span>
            </label>
          ))}
          <div className="form-grid">
            {limits.map(([key, label, max]) => (
              <label className="field" key={key}>
                <span>{label}</span>
                <input
                  type="number"
                  required
                  min={1}
                  max={max}
                  value={data[key]}
                  onChange={(e) => {
                    setData({ ...data, [key]: Number(e.target.value) });
                    setSaved(false);
                  }}
                />
              </label>
            ))}
          </div>
          <p className="field-hint">
            Teto diário em UTC, sujeito aos limites globais. Desativar uma fonte
            impede novas entradas; lotes já criados podem ser pausados no Radar.
          </p>
          <button className="button" disabled={busy}>
            {busy ? "Salvando…" : "Salvar investigação"}
          </button>
          {saved && <p role="status">Preferências de investigação salvas.</p>}
        </form>
      )}
    </section>
  );
}
