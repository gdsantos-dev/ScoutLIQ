import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Download, LockKeyhole, Database } from "lucide-react";
import type { Currency, Locale, User } from "../types";
import { api } from "../api";
import { PageHead, Field, ErrorText, Submit, Confirm } from "../components/UI";
import { SmartSelect } from "../components/Primitives";
import { currencyOptions, localeOptions, tr } from "../i18n";
import InvestigationSettings from "../components/InvestigationSettings";
export default function Settings({
  user,
  onUser,
  onDemo,
  onClearDemo,
  onExport,
  onLogout,
  hasDemo,
}: {
  user: User;
  onUser: (u: User) => void;
  onDemo: () => Promise<void>;
  onClearDemo: () => Promise<void>;
  onExport: () => void;
  onLogout: () => void;
  hasDemo: boolean;
}) {
  const [motion, setMotion] = useState(user.motion),
    [locale, setLocale] = useState<Locale>(user.locale),
    [defaultCurrency, setDefaultCurrency] = useState<Currency>(
      user.default_currency,
    ),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false),
    [passwordError, setPasswordError] = useState(""),
    [passwordBusy, setPasswordBusy] = useState(false),
    [confirm, setConfirm] = useState(false),
    [demoBusy, setDemoBusy] = useState(false);
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dataset.currency = defaultCurrency;
    return () => {
      document.documentElement.lang = user.locale;
      document.documentElement.dataset.currency = user.default_currency;
    };
  }, [locale, defaultCurrency, user.locale, user.default_currency]);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    const d = new FormData(e.currentTarget);
    try {
      const next = await api<User>("/settings", "PUT", {
        name: d.get("name"),
        timezone: d.get("timezone"),
        locale,
        default_currency: defaultCurrency,
        accent: user.accent,
        motion,
      });
      onUser(next);
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function password(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPasswordBusy(true);
    setPasswordError("");
    const d = new FormData(e.currentTarget);
    if (d.get("new_password") !== d.get("confirm")) {
      setPasswordError(tr("As novas senhas não coincidem.", locale));
      setPasswordBusy(false);
      return;
    }
    try {
      await api("/auth/password", "PUT", {
        current_password: d.get("current_password"),
        new_password: d.get("new_password"),
      });
      onLogout();
    } catch (e) {
      setPasswordError((e as Error).message);
    } finally {
      setPasswordBusy(false);
    }
  }
  async function demo(remove = false) {
    setDemoBusy(true);
    setError("");
    try {
      if (remove) await onClearDemo();
      else await onDemo();
      setConfirm(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDemoBusy(false);
    }
  }
  return (
    <>
      <PageHead
        title={tr("Configurações", locale)}
        eyebrow={tr("Configurações", locale).toUpperCase()}
      />
      <div className="settings-layout">
        <section className="panel settings-panel">
          <h2>{tr("Seu espaço", locale)}</h2>
          <form onSubmit={save}>
            <div className="form-grid">
              <Field label={tr("Nome da operação", locale)}>
                <input
                  name="name"
                  required
                  minLength={2}
                  maxLength={80}
                  defaultValue={user.name}
                />
              </Field>
              <Field label={tr("Fuso horário", locale)}>
                <SmartSelect
                  name="timezone"
                  ariaLabel={tr("Fuso horário", locale)}
                  defaultValue={user.timezone}
                  options={Array.from(
                    new Set([
                      user.timezone,
                      "America/Sao_Paulo",
                      "America/Manaus",
                      "America/New_York",
                      "America/Los_Angeles",
                      "America/Mexico_City",
                      "America/Bogota",
                      "Europe/Madrid",
                      "Europe/Lisbon",
                      "UTC",
                    ]),
                  ).map((z) => ({
                    value: z,
                    label: z
                      .replace("America/", "")
                      .replace("Europe/", "")
                      .replaceAll("_", " "),
                  }))}
                />
              </Field>
              <Field label={tr("Idioma", locale)}>
                <SmartSelect
                  value={locale}
                  onChange={(value) => {
                    document.documentElement.lang = value;
                    setLocale(value as Locale);
                    setSaved(false);
                  }}
                  ariaLabel={tr("Idioma", locale)}
                  options={localeOptions.map((option) => ({
                    ...option,
                    label: tr(option.label, locale),
                  }))}
                />
              </Field>
              <Field label={tr("Moeda padrão", locale)}>
                <SmartSelect
                  value={defaultCurrency}
                  onChange={(value) => {
                    setDefaultCurrency(value as Currency);
                    setSaved(false);
                  }}
                  ariaLabel={tr("Moeda padrão", locale)}
                  options={currencyOptions.map((option) => ({
                    ...option,
                    label: tr(option.label, locale),
                  }))}
                />
              </Field>
            </div>
            <div className="settings-section">
              <h3>{tr("Movimento da interface", locale)}</h3>
              <div className="radio-options">
                <label>
                  <input
                    type="radio"
                    name="motion"
                    value="full"
                    checked={motion === "full"}
                    onChange={() => {
                      setMotion("full");
                      setSaved(false);
                    }}
                  />
                  <span>
                    {tr("Completo", locale)}
                    <small>{tr("Transições e sinais sutis.", locale)}</small>
                  </span>
                </label>
                <label>
                  <input
                    type="radio"
                    name="motion"
                    value="reduced"
                    checked={motion === "reduced"}
                    onChange={() => {
                      setMotion("reduced");
                      setSaved(false);
                    }}
                  />
                  <span>
                    {tr("Reduzido", locale)}
                    <small>
                      {tr("Uma experiência mais estática.", locale)}
                    </small>
                  </span>
                </label>
              </div>
              <p className="field-hint">
                {tr(
                  "A preferência de movimento reduzido do seu dispositivo sempre é respeitada.",
                  locale,
                )}
              </p>
            </div>
            <ErrorText error={error} />
            <div className="form-actions">
              {saved && (
                <span className="positive" role="status">
                  {tr("Preferências salvas", locale)}
                </span>
              )}
              <Submit busy={busy}>{tr("Salvar preferências", locale)}</Submit>
            </div>
          </form>
        </section>
        <section className="panel settings-panel">
          <h2>
            <Database size={19} />
            {tr("Seus dados", locale)}
          </h2>
          <p className="muted">
            {tr(
              "Exporte estabelecimentos, vendas e movimentações da operação em JSON.",
              locale,
            )}
          </p>
          <button className="button" onClick={onExport}>
            <Download size={16} />
            {tr("Exportar meus dados", locale)}
          </button>
          <div className="settings-section">
            <h3>{tr("Dados de demonstração", locale)}</h3>
            <p className="muted">
              {tr(
                "Carrega exemplos identificados, removíveis sem afetar cadastros reais.",
                locale,
              )}
            </p>
            <button
              className="button"
              disabled={demoBusy}
              onClick={() => (hasDemo ? setConfirm(true) : void demo())}
            >
              {demoBusy
                ? "Aguarde…"
                : hasDemo
                  ? "Remover exemplos"
                  : "Carregar exemplos"}
            </button>
          </div>
          <div className="settings-section">
            <h3>{tr("Fontes de estabelecimentos", locale)}</h3>
            <p className="muted">
              {tr(
                "O Radar usa a fonte configurada no servidor. Cadastro manual permanece disponível.",
                locale,
              )}
            </p>
            <span className="badge">{tr("V1 · Operação privada", locale)}</span>
          </div>
        </section>
        <section className="panel settings-panel">
          <h2>
            <LockKeyhole size={19} />
            {tr("Acesso e segurança", locale)}
          </h2>
          <p className="muted">{user.email}</p>
          <form onSubmit={password}>
            <Field label="Senha atual">
              <input
                type="password"
                name="current_password"
                autoComplete="current-password"
                required
                maxLength={256}
              />
            </Field>
            <div className="form-grid">
              <Field label="Nova senha">
                <input
                  type="password"
                  name="new_password"
                  autoComplete="new-password"
                  required
                  minLength={12}
                  maxLength={256}
                />
              </Field>
              <Field label="Confirmar nova senha">
                <input
                  type="password"
                  name="confirm"
                  autoComplete="new-password"
                  required
                  minLength={12}
                  maxLength={256}
                />
              </Field>
            </div>
            <p className="field-hint">
              Use pelo menos 12 caracteres. Todas as sessões serão encerradas
              após a alteração.
            </p>
            <ErrorText error={passwordError} />
            <div className="form-actions">
              <Submit busy={passwordBusy}>{tr("Alterar senha", locale)}</Submit>
            </div>
          </form>
        </section>
        <InvestigationSettings />
        <section className="settings-brand">
          <span className="eyebrow">{tr("UM PRODUTO ORLIQ", locale)}</span>
          <h2>ScoutLIQ</h2>

          <span className="muted">{"1.38.3-dev"}</span>
        </section>
      </div>
      {confirm && (
        <Confirm
          title="Remover dados de demonstração?"
          description="Isso apaga os estabelecimentos fictícios e as vendas e pagamentos vinculados a eles. Seus cadastros reais serão preservados."
          label="Remover exemplos"
          onConfirm={() => void demo(true)}
          onClose={() => setConfirm(false)}
          busy={demoBusy}
          error={error}
        />
      )}
    </>
  );
}
