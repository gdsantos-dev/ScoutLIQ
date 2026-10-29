import { localeOptions, tr } from "../i18n";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, PointerEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-react";
import { api, ApiError } from "../api";
import type { Locale, User } from "../types";
import { ErrorText, Field } from "./UI";
import { SmartSelect } from "./Primitives";

export type AuthPayload = { user: User; csrf: string };
type AuthMode =
  | "login"
  | "register"
  | "verify-pending"
  | "forgot"
  | "reset"
  | "verified"
  | "reset-done"
  | "verify-error";

type AuthConfig = {
  registration_enabled: boolean;
  email_configured: boolean;
};

type MessageResponse = { message: string };
type RegisterResponse = MessageResponse & {
  email: string;
  email_sent: boolean;
};

function authTokens() {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  return {
    verifyToken: params.get("verify_token") || "",
    resetToken: params.get("reset_token") || "",
  };
}

function clearAuthHash() {
  if (!window.location.hash) return;
  window.history.replaceState(
    null,
    "",
    window.location.pathname + window.location.search,
  );
}

export default function AuthScreen({
  onLogin,
  initialError,
}: {
  onLogin: (auth: AuthPayload) => void;
  initialError: string;
}) {
  const tokens = useMemo(authTokens, []);
  const [mode, setMode] = useState<AuthMode>(
    tokens.verifyToken
      ? "verify-pending"
      : tokens.resetToken
        ? "reset"
        : "login",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError);
  const [notice, setNotice] = useState("");
  const [pendingEmail, setPendingEmail] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [registrationEnabled, setRegistrationEnabled] = useState(true);
  const [locale, setLocale] = useState<Locale>(() => {
    const browser = navigator.language.toLowerCase();
    const detected = browser.startsWith("es")
      ? "es"
      : browser.startsWith("en")
        ? "en-US"
        : "pt-BR";
    document.documentElement.lang = detected;
    return detected;
  });

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  useEffect(() => {
    let alive = true;
    api<AuthConfig>("/auth/config")
      .then((config) => {
        if (alive) setRegistrationEnabled(config.registration_enabled);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!tokens.verifyToken) return;
    let alive = true;
    setBusy(true);
    setError("");
    api<MessageResponse>("/auth/verify-email", "POST", {
      token: tokens.verifyToken,
    })
      .then((result) => {
        if (!alive) return;
        clearAuthHash();
        setNotice(result.message);
        setMode("verified");
      })
      .catch((requestError) => {
        if (!alive) return;
        setError((requestError as Error).message);
        setMode("verify-error");
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
    };
  }, [tokens.verifyToken]);

  function go(next: AuthMode) {
    setMode(next);
    setError("");
    setNotice("");
    setPasswordVisible(false);
  }

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") || "");
    try {
      onLogin(
        await api<AuthPayload>("/auth/login", "POST", {
          email,
          password: data.get("password"),
        }),
      );
    } catch (requestError) {
      const err = requestError as ApiError;
      setError(err.message);
      if (
        err.status === 403 &&
        err.message.toLowerCase().includes("confirme")
      ) {
        setPendingEmail(email);
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password") || "");
    const confirmation = String(data.get("password_confirmation") || "");
    if (password !== confirmation) {
      setBusy(false);
      setError("As senhas não conferem.");
      return;
    }
    try {
      const result = await api<RegisterResponse>("/auth/register", "POST", {
        name: data.get("name"),
        email: data.get("email"),
        password,
      });
      setPendingEmail(result.email);
      setNotice(result.message);
      setMode("verify-pending");
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function resendVerification() {
    if (!pendingEmail) {
      go("login");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api<MessageResponse>(
        "/auth/resend-verification",
        "POST",
        {
          email: pendingEmail,
        },
      );
      setNotice(result.message);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function submitForgot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const result = await api<MessageResponse>(
        "/auth/forgot-password",
        "POST",
        {
          email: data.get("email"),
        },
      );
      setNotice(result.message);
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function submitReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password") || "");
    const confirmation = String(data.get("password_confirmation") || "");
    if (password !== confirmation) {
      setBusy(false);
      setError("As senhas não conferem.");
      return;
    }
    try {
      const result = await api<MessageResponse>(
        "/auth/reset-password",
        "POST",
        {
          token: tokens.resetToken,
          password,
        },
      );
      clearAuthHash();
      setNotice(result.message);
      setMode("reset-done");
    } catch (requestError) {
      setError((requestError as Error).message);
    } finally {
      setBusy(false);
    }
  }


  const heroMark = useRef<HTMLDivElement>(null);

  function updateHeroMark(event: PointerEvent<HTMLDivElement>) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const node = heroMark.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    const x = Math.max(-0.5, Math.min(0.5, (event.clientX - rect.left) / rect.width - 0.5));
    const y = Math.max(-0.5, Math.min(0.5, (event.clientY - rect.top) / rect.height - 0.5));
    node.style.setProperty("--mark-rx", `${8 - y * 12}deg`);
    node.style.setProperty("--mark-ry", `${-16 + x * 18}deg`);
    node.style.setProperty("--mark-rz", `${4 + x * 2.5}deg`);
    node.style.setProperty("--mark-lift", `${Math.abs(x) * 5 + Math.abs(y) * 4}px`);
  }

  function engageHeroMark(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType === "touch") {
      try { event.currentTarget.setPointerCapture(event.pointerId); } catch { /* no-op */ }
    }
    updateHeroMark(event);
  }

  function resetHeroMark(event?: PointerEvent<HTMLDivElement>) {
    if (event?.pointerType === "touch") {
      try { event.currentTarget.releasePointerCapture(event.pointerId); } catch { /* no-op */ }
    }
    const node = heroMark.current;
    if (!node) return;
    node.style.removeProperty("--mark-rx");
    node.style.removeProperty("--mark-ry");
    node.style.removeProperty("--mark-rz");
    node.style.removeProperty("--mark-lift");
  }

  const passwordToggle = (
    <button
      type="button"
      className="icon-button"
      aria-label={
        passwordVisible
          ? tr("Ocultar senha", locale)
          : tr("Mostrar senha", locale)
      }
      onClick={() => setPasswordVisible(!passwordVisible)}
    >
      {passwordVisible ? <EyeOff size={18} /> : <Eye size={18} />}
    </button>
  );

  return (
    <div className="login-page">
      <header>
        <span className="orliq-signature">ORLIQ</span>
        <div className="auth-locale">
          <SmartSelect
            compact
            value={locale}
            onChange={(value) => {
              document.documentElement.lang = value;
              setLocale(value as Locale);
            }}
            ariaLabel={tr("Idioma", locale)}
            options={localeOptions}
          />
        </div>
      </header>
      <main className="login-layout">
        <section className="login-story" aria-label="ScoutLIQ">
          <div
            ref={heroMark}
            className="login-hero-mark"
            onPointerDown={engageHeroMark}
            onPointerMove={updateHeroMark}
            onPointerUp={resetHeroMark}
            onPointerCancel={resetHeroMark}
            onPointerLeave={resetHeroMark}
          >
            <span className="login-hero-orbit orbit-a" aria-hidden="true" />
            <span className="login-hero-orbit orbit-b" aria-hidden="true" />
            <img src="/scoutliq-mark.png" alt="" aria-hidden="true" draggable={false} />
          </div>
          <div className="login-story-copy">
            <strong>ScoutLIQ</strong>
            <p>{tr("Prospecção, clientes e gestão de sites.", locale)}</p>
          </div>
        </section>
        <section className="login-card">
          {mode === "login" && (
            <>
              <div className="login-card-icon">
                <LockKeyhole size={22} />
              </div>
              <h2>{tr("Entrar", locale)}</h2>
              <form onSubmit={submitLogin}>
                <Field label="E-mail">
                  <input
                    name="email"
                    type="email"
                    autoComplete="username"
                    autoFocus
                    required
                    maxLength={254}
                    placeholder="seu@email.com"
                  />
                </Field>
                <Field label={tr("Senha")}>
                  <div className="password-input">
                    <input
                      name="password"
                      type={passwordVisible ? "text" : "password"}
                      autoComplete="current-password"
                      maxLength={256}
                      required
                    />
                    {passwordToggle}
                  </div>
                </Field>
                {notice && <p className="auth-notice">{notice}</p>}
                <ErrorText error={error} />
                {pendingEmail && error && (
                  <button
                    className="auth-inline-link"
                    type="button"
                    onClick={resendVerification}
                    disabled={busy}
                  >
                    {tr("Reenviar confirmação")}
                  </button>
                )}
                <button
                  className="button primary"
                  type="submit"
                  disabled={busy}
                >
                  {busy ? "…" : tr("Entrar", locale)}
                  <ArrowRight size={18} />
                </button>
              </form>
              <div className="auth-links">
                <button type="button" onClick={() => go("forgot")}>
                  {tr("Esqueci a senha", locale)}
                </button>
                {registrationEnabled && (
                  <button type="button" onClick={() => go("register")}>
                    {tr("Criar conta", locale)}
                  </button>
                )}
              </div>
            </>
          )}

          {mode === "register" && (
            <>
              <div className="login-card-icon">
                <UserRound size={22} />
              </div>
              <h2>{tr("Criar conta", locale)}</h2>
              <form onSubmit={submitRegister}>
                <Field label={tr("Nome")}>
                  <input
                    name="name"
                    type="text"
                    autoComplete="name"
                    autoFocus
                    required
                    maxLength={80}
                  />
                </Field>
                <Field label="E-mail">
                  <input
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    maxLength={254}
                    placeholder="seu@email.com"
                  />
                </Field>
                <Field label={tr("Senha")}>
                  <div className="password-input">
                    <input
                      name="password"
                      type={passwordVisible ? "text" : "password"}
                      autoComplete="new-password"
                      minLength={12}
                      maxLength={256}
                      required
                    />
                    {passwordToggle}
                  </div>
                </Field>
                <Field label={tr("Confirmar senha")}>
                  <input
                    name="password_confirmation"
                    type={passwordVisible ? "text" : "password"}
                    autoComplete="new-password"
                    minLength={12}
                    maxLength={256}
                    required
                  />
                </Field>
                <p className="auth-hint">
                  {tr("Use pelo menos 12 caracteres.", locale)}
                </p>
                <ErrorText error={error} />
                <button
                  className="button primary"
                  type="submit"
                  disabled={busy}
                >
                  {busy ? tr("Criando…", locale) : tr("Criar conta", locale)}
                  <ArrowRight size={18} />
                </button>
              </form>
              <div className="auth-links auth-links-single">
                <button type="button" onClick={() => go("login")}>
                  <ArrowLeft size={14} />
                  {tr("Já tenho uma conta", locale)}
                </button>
              </div>
            </>
          )}

          {mode === "forgot" && (
            <>
              <div className="login-card-icon">
                <KeyRound size={22} />
              </div>
              <h2>{tr("Recuperar senha", locale)}</h2>
              <p className="muted">
                {tr(
                  "Enviaremos um link de recuperação para seu e-mail.",
                  locale,
                )}
              </p>
              <form onSubmit={submitForgot}>
                <Field label="E-mail">
                  <input
                    name="email"
                    type="email"
                    autoComplete="email"
                    autoFocus
                    required
                    maxLength={254}
                    placeholder="seu@email.com"
                  />
                </Field>
                {notice && <p className="auth-notice">{notice}</p>}
                <ErrorText error={error} />
                <button
                  className="button primary"
                  type="submit"
                  disabled={busy}
                >
                  {busy
                    ? tr("Enviando…", locale)
                    : tr("Enviar recuperação", locale)}
                  <ArrowRight size={18} />
                </button>
              </form>
              <div className="auth-links auth-links-single">
                <button type="button" onClick={() => go("login")}>
                  <ArrowLeft size={14} />
                  {tr("Voltar para entrar", locale)}
                </button>
              </div>
            </>
          )}

          {mode === "reset" && (
            <>
              <div className="login-card-icon">
                <KeyRound size={22} />
              </div>
              <h2>{tr("Nova senha")}</h2>
              <p className="muted">
                {tr("Defina uma nova senha para sua conta.", locale)}
              </p>
              <form onSubmit={submitReset}>
                <Field label={tr("Nova senha")}>
                  <div className="password-input">
                    <input
                      name="password"
                      type={passwordVisible ? "text" : "password"}
                      autoComplete="new-password"
                      autoFocus
                      minLength={12}
                      maxLength={256}
                      required
                    />
                    {passwordToggle}
                  </div>
                </Field>
                <Field label={tr("Confirmar senha")}>
                  <input
                    name="password_confirmation"
                    type={passwordVisible ? "text" : "password"}
                    autoComplete="new-password"
                    minLength={12}
                    maxLength={256}
                    required
                  />
                </Field>
                <ErrorText error={error} />
                <button
                  className="button primary"
                  type="submit"
                  disabled={busy}
                >
                  {busy
                    ? tr("Salvando…", locale)
                    : tr("Salvar nova senha", locale)}
                  <ArrowRight size={18} />
                </button>
              </form>
              <div className="auth-links auth-links-single">
                <button
                  type="button"
                  onClick={() => {
                    clearAuthHash();
                    go("login");
                  }}
                >
                  <ArrowLeft size={14} />
                  {tr("Voltar para entrar", locale)}
                </button>
              </div>
            </>
          )}

          {mode === "verify-pending" && (
            <div className="auth-state">
              <div className="login-card-icon">
                <Mail size={22} />
              </div>
              <h2>{tr("Confira seu e-mail", locale)}</h2>
              <p className="muted">
                {notice ||
                  `Enviamos a confirmação para ${pendingEmail || "seu e-mail"}.`}
              </p>
              <ErrorText error={error} />
              <button
                className="button primary"
                type="button"
                onClick={resendVerification}
                disabled={busy || !pendingEmail}
              >
                {busy
                  ? tr("Enviando…", locale)
                  : tr("Reenviar confirmação", locale)}
                <Mail size={17} />
              </button>
              <button
                className="auth-inline-link"
                type="button"
                onClick={() => go("login")}
              >
                {tr("Voltar para entrar", locale)}
              </button>
            </div>
          )}

          {mode === "verified" && (
            <div className="auth-state">
              <div className="login-card-icon auth-success-icon">
                <CheckCircle2 size={22} />
              </div>
              <h2>{tr("E-mail confirmado", locale)}</h2>
              <p className="muted">
                {notice || tr("Sua conta está pronta para uso.", locale)}
              </p>
              <button
                className="button primary"
                type="button"
                onClick={() => go("login")}
              >
                {tr("Entrar", locale)}
                <ArrowRight size={18} />
              </button>
            </div>
          )}

          {mode === "reset-done" && (
            <div className="auth-state">
              <div className="login-card-icon auth-success-icon">
                <CheckCircle2 size={22} />
              </div>
              <h2>{tr("Senha alterada", locale)}</h2>
              <p className="muted">{notice}</p>
              <button
                className="button primary"
                type="button"
                onClick={() => go("login")}
              >
                {tr("Entrar com a nova senha", locale)}
                <ArrowRight size={18} />
              </button>
            </div>
          )}

          {mode === "verify-error" && (
            <div className="auth-state">
              <div className="login-card-icon">
                <Mail size={22} />
              </div>
              <h2>{tr("Não foi possível confirmar", locale)}</h2>
              <ErrorText error={error} />
              <button
                className="button"
                type="button"
                onClick={() => go("login")}
              >
                <ArrowLeft size={16} />
                {tr("Voltar para entrar", locale)}
              </button>
            </div>
          )}
        </section>
      </main>
      <footer>
        <span>{tr("ScoutLIQ · Um produto ORLIQ", locale)}</span>
      </footer>
    </div>
  );
}
