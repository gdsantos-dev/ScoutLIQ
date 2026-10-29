import { useMemo, useState } from "react";
import {
  Check,
  Clipboard,
  Database,
  Download,
  Link2,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import { PageHead } from "../components/UI";
import {
  bridgeFilename,
  buildBridgePackage,
  type BridgeProfile,
  type BridgeScope,
} from "../ecosystemBridge";
import { tr } from "../i18n";
import type { Lead, Sale, User } from "../types";
import { GmailConnection } from '../components/Communication';

function saveJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Integrations({
  user,
  leads,
  sales,
  onNotice,
}: {
  user: User;
  leads: Lead[];
  sales: Sale[];
  onNotice: (message: string) => void;
}) {
  const [profile, setProfile] = useState<BridgeProfile>("workspace");
  const [scopes, setScopes] = useState<BridgeScope[]>([
    "commercial",
    "delivery",
    "finance",
  ]);
  const [includeContacts, setIncludeContacts] = useState(false);
  const [copied, setCopied] = useState(false);

  const options = useMemo(
    () => ({
      profile,
      scopes: profile === "dashliq_finance" ? (["finance"] as BridgeScope[]) : scopes,
      includeContacts,
    }),
    [profile, scopes, includeContacts],
  );
  const payload = useMemo(
    () => buildBridgePackage({ user, leads, sales, options }),
    [user, leads, sales, options],
  );
  const encoded = useMemo(() => JSON.stringify(payload, null, 2), [payload]);
  const summary = payload.summary;

  function toggleScope(scope: BridgeScope) {
    setScopes((current) =>
      current.includes(scope)
        ? current.length === 1
          ? current
          : current.filter((item) => item !== scope)
        : [...current, scope],
    );
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(encoded);
      setCopied(true);
      onNotice("Pacote ORLIQ copiado.");
      setTimeout(() => setCopied(false), 1800);
    } catch {
      onNotice("Não foi possível copiar. Use Baixar pacote.");
    }
  }

  function download() {
    saveJson(bridgeFilename(profile), payload);
    onNotice("Pacote ORLIQ gerado.");
  }

  return (
    <div className="integration-workspace">
      <PageHead title={tr("Integrações")} eyebrow={tr("Ecossistema ORLIQ")} />
      <GmailConnection />

      <section className="integration-intro">
        <div>
          <span className="eyebrow">ORLIQ BRIDGE · V1</span>
          <h2>{tr("Leve dados do Scout sem acoplar produtos")}</h2>
          <p>
            {tr(
              "Gere um pacote versionado para o ecossistema ORLIQ. Nenhum dado é enviado automaticamente e nenhum destino recebe acesso direto ao seu workspace.",
            )}
          </p>
        </div>
        <span className="integration-contract">
          <Link2 size={17} />
          orliq.bridge / 1
        </span>
      </section>

      <div className="integration-grid">
        <section className="integration-section">
          <div className="integration-section-head">
            <div>
              <span className="eyebrow">{tr("DESTINO")}</span>
              <h2>{tr("Perfil do pacote")}</h2>
            </div>
          </div>
          <div className="integration-profile-list">
            <button
              className="integration-profile"
              data-active={profile === "workspace"}
              onClick={() => setProfile("workspace")}
            >
              <Database size={20} />
              <span>
                <strong>{tr("Ecossistema ORLIQ")}</strong>
                <small>{tr("Pipeline, clientes, entregas e financeiro em um contrato único.")}</small>
              </span>
              {profile === "workspace" && <Check size={17} />}
            </button>
            <button
              className="integration-profile"
              data-active={profile === "dashliq_finance"}
              onClick={() => setProfile("dashliq_finance")}
            >
              <WalletCards size={20} />
              <span>
                <strong>DashLIQ · Financeiro</strong>
                <small>{tr("Vendas, recebimentos, recorrência e valores ainda a receber.")}</small>
              </span>
              {profile === "dashliq_finance" && <Check size={17} />}
            </button>
          </div>
        </section>

        <section className="integration-section">
          <div className="integration-section-head">
            <div>
              <span className="eyebrow">{tr("CONTEÚDO")}</span>
              <h2>{tr("O que sai do Scout")}</h2>
            </div>
          </div>
          {profile === "workspace" ? (
            <div className="integration-scope-list">
              {([
                ["commercial", "Comercial", "Negociações, etapa, Score e próxima ação."],
                ["delivery", "Clientes e entregas", "Vendas fechadas, serviço e andamento."],
                ["finance", "Financeiro", "Recebimentos, valores a receber e recorrência."],
              ] as [BridgeScope, string, string][]).map(([id, label, description]) => (
                <label key={id} className="integration-scope">
                  <input
                    type="checkbox"
                    checked={scopes.includes(id)}
                    onChange={() => toggleScope(id)}
                  />
                  <span>
                    <strong>{tr(label)}</strong>
                    <small>{tr(description)}</small>
                  </span>
                </label>
              ))}
            </div>
          ) : (
            <div className="integration-fixed-scope">
              <WalletCards size={19} />
              <div>
                <strong>{tr("Financeiro somente")}</strong>
                <p>{tr("O perfil DashLIQ reduz o pacote ao que é útil para conciliação financeira futura.")}</p>
              </div>
            </div>
          )}
          <label className="integration-contact-toggle">
            <input
              type="checkbox"
              checked={includeContacts}
              onChange={(event) => setIncludeContacts(event.target.checked)}
            />
            <span>
              <strong>{tr("Incluir dados de contato")}</strong>
              <small>{tr("Nome, telefone, WhatsApp, Instagram e e-mail quando disponíveis.")}</small>
            </span>
          </label>
        </section>
      </div>

      <section className="integration-preview">
        <div className="integration-section-head">
          <div>
            <span className="eyebrow">{tr("PRÉVIA")}</span>
            <h2>{tr("Pacote pronto para handoff")}</h2>
          </div>
          <span className="integration-size">
            {new Intl.NumberFormat(user.locale).format(new Blob([encoded]).size)} bytes
          </span>
        </div>

        <div className="integration-summary">
          <div>
            <span>{tr("Negociações")}</span>
            <strong>{summary.leads}</strong>
          </div>
          <div>
            <span>{tr("Vendas")}</span>
            <strong>{summary.sales}</strong>
          </div>
          <div>
            <span>{tr("Recebíveis BRL")}</span>
            <strong>{new Intl.NumberFormat(user.locale, { style: "currency", currency: "BRL" }).format((summary.receivable_by_currency.BRL || 0) / 100)}</strong>
          </div>
          <div>
            <span>{tr("Recorrência BRL")}</span>
            <strong>{new Intl.NumberFormat(user.locale, { style: "currency", currency: "BRL" }).format((summary.recurring_by_currency.BRL || 0) / 100)}</strong>
          </div>
        </div>

        <div className="integration-actions">
          <button className="button primary" onClick={download}>
            <Download size={16} />
            {tr("Baixar pacote")}
          </button>
          <button className="button" onClick={() => void copy()}>
            {copied ? <Check size={16} /> : <Clipboard size={16} />}
            {copied ? tr("Copiado") : tr("Copiar JSON")}
          </button>
        </div>
      </section>

      <section className="integration-safety">
        <ShieldCheck size={19} />
        <div>
          <strong>{tr("Sem sincronização silenciosa")}</strong>
          <p>
            {tr(
              "A v1.29 cria o contrato e o handoff. O Scout não envia nada para o DashLIQ ou outro serviço sem uma ação explícita sua. Notas internas não entram no Bridge v1.",
            )}
          </p>
        </div>
      </section>
    </div>
  );
}
