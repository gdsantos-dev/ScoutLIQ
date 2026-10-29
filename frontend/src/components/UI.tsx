import { tr } from "../i18n";
import { Children, cloneElement, isValidElement, useId, useRef } from "react";
import type { ReactNode, FormEvent } from "react";
import { X, ArrowUpRight, LoaderCircle, ScanLine } from "lucide-react";
import { motion } from "motion/react";
import { useDialogLifecycle } from "./dialogLifecycle";

export function Brand() {
  return (
    <span className="brand">
      Scout<span>LIQ</span>
    </span>
  );
}
export function Mark() {
  return (
    <img
      className="brand-mark"
      src="/scoutliq-mark.png"
      alt=""
      aria-hidden="true"
      draggable={false}
    />
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <ScanLine size={30} />
      <h3>{tr(title)}</h3>
      {description && <p>{tr(description)}</p>}
      {action}
    </div>
  );
}
export function Skeleton() {
  return (
    <div
      className="loading-view"
      aria-label={tr("Carregando dados")}
      role="status"
    >
      <div className="skeleton heading-skeleton" />
      <div className="skeleton map-skeleton" />
      <div className="skeleton heading-skeleton" />
    </div>
  );
}
export function ErrorText({ error }: { error: string }) {
  return error ? (
    <p className="error-text" role="alert">
      {error}
    </p>
  ) : null;
}
export function Submit({
  busy,
  children,
}: {
  busy: boolean;
  children: ReactNode;
}) {
  return (
    <button className="button primary" disabled={busy} type="submit">
      {busy ? <LoaderCircle className="spin" size={17} /> : null}
      {busy ? tr("Salvando…") : children}
    </button>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
  className = "",
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useId();
  useDialogLifecycle(ref, true);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "wide" : ""} ${className}`.trim()}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) {
          const r = ref.current.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            onClose();
        }
      }}
      aria-labelledby={heading}
    >
      <div className="modal-head">
        <h2 id={heading}>{tr(title)}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label={tr("Fechar")}
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Confirm({
  title,
  description,
  label,
  onConfirm,
  onClose,
  busy,
  error,
}: {
  title: string;
  description: string;
  label: string;
  onConfirm: () => void;
  onClose: () => void;
  busy: boolean;
  error: string;
}) {
  return (
    <Modal title={title} onClose={onClose}>
      <p className="muted">{tr(description)}</p>
      <ErrorText error={error} />
      <div className="form-actions">
        <button className="button" onClick={onClose} disabled={busy}>
          {tr("Cancelar")}
        </button>
        <button className="button danger" disabled={busy} onClick={onConfirm}>
          {busy ? tr("Aguarde…") : tr(label)}
        </button>
      </div>
    </Modal>
  );
}
export function SectionTitle({
  title,
  action,
}: {
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-title">
      <h2>{tr(title)}</h2>
      {action}
    </div>
  );
}
export function PageHead({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow?: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        {eyebrow &&
          eyebrow.toLocaleLowerCase() !== title.toLocaleLowerCase() && (
            <p className="eyebrow">{eyebrow}</p>
          )}
        <h1>{tr(title)}</h1>
      </div>
      <div className="head-actions">{children}</div>
    </div>
  );
}
export function View({ children }: { children: ReactNode }) {
  return (
    <motion.div
      data-testid="page-view"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.div>
  );
}
export function ExternalLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <a
      className="text-link"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
      <ArrowUpRight size={15} />
    </a>
  );
}
export function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`field ${className}`}>
      <span>{tr(label)}</span>
      {Children.map(children, (child) =>
        isValidElement<{ ariaLabel?: string }>(child) &&
        typeof child.type === "function"
          ? cloneElement(child, {
              ariaLabel: child.props.ariaLabel || tr(label),
            })
          : child,
      )}
    </label>
  );
}
export type FormHandler = (event: FormEvent<HTMLFormElement>) => void;
