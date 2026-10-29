import { tr, currentLocale } from "../i18n";
import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import { createPortal } from "react-dom";
import {
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

export type SelectOption = {
  value: string;
  label: string;
  meta?: string;
  disabled?: boolean;
};

type SmartSelectProps = {
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  options: SelectOption[];
  name?: string;
  ariaLabel?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  compact?: boolean;
};

export function SmartSelect({
  value,
  defaultValue = "",
  onChange,
  options,
  name,
  ariaLabel,
  placeholder = "Selecionar",
  disabled = false,
  className = "",
  compact = false,
}: SmartSelectProps) {
  const controlled = value !== undefined;
  const [internal, setInternal] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({});
  const listId = useId();
  const current = controlled ? value! : internal;
  const selected = options.find((option) => option.value === current);

  useEffect(() => {
    if (open)
      menu.current
        ?.querySelector(`[id="${listId}-${active}"]`)
        ?.scrollIntoView({ block: "nearest" });
  }, [open, active, listId]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!root.current?.contains(target) && !menu.current?.contains(target)) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const index = Math.max(
      0,
      options.findIndex((option) => option.value === current),
    );
    setActive(index);
  }, [open, current, options]);

  useLayoutEffect(() => {
    if (!open || !trigger.current) return;

    let frame = 0;
    const update = () => {
      if (!trigger.current) return;
      const rect = trigger.current.getBoundingClientRect();
      const viewportPadding = 8;
      const gap = 6;
      const width = Math.min(
        Math.max(rect.width, 210),
        Math.max(210, window.innerWidth - viewportPadding * 2),
      );
      const measuredHeight =
        menu.current?.offsetHeight ?? Math.min(290, options.length * 44 + 10);
      const roomBelow = window.innerHeight - rect.bottom - viewportPadding;
      const roomAbove = rect.top - viewportPadding;
      const openBelow =
        roomBelow >= Math.min(measuredHeight, 220) || roomBelow >= roomAbove;
      const top = openBelow
        ? rect.bottom + gap
        : Math.max(viewportPadding, rect.top - measuredHeight - gap);
      const left = Math.min(
        Math.max(viewportPadding, rect.left),
        Math.max(viewportPadding, window.innerWidth - width - viewportPadding),
      );

      setMenuStyle({
        top,
        left,
        width,
        maxHeight: Math.min(
          290,
          Math.max(140, openBelow ? roomBelow - gap : roomAbove - gap),
        ),
      });
    };

    update();
    frame = window.requestAnimationFrame(update);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, options.length]);

  const choose = (next: SelectOption) => {
    if (next.disabled) return;
    if (!controlled) setInternal(next.value);
    onChange?.(next.value);
    setOpen(false);
    trigger.current?.focus();
  };

  const keyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    if (!open && ["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      return;
    }
    if (event.key === "Tab") {
      setOpen(false);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      let next = active;
      for (let i = 0; i < options.length; i += 1) {
        next = (next + direction + options.length) % options.length;
        if (!options[next]?.disabled) break;
      }
      setActive(next);
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const option = options[active];
      if (option) choose(option);
    }
  };

  return (
    <div
      ref={root}
      className={`smart-select ${open ? "open" : ""} ${compact ? "compact" : ""} ${className}`.trim()}
    >
      {name && <input type="hidden" name={name} value={current} />}
      <button
        ref={trigger}
        type="button"
        className="smart-select-trigger"
        role="combobox"
        aria-activedescendant={open ? `${listId}-${active}` : undefined}
        aria-label={tr(ariaLabel || placeholder)}
        aria-expanded={open}
        aria-controls={listId}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => setOpen((state) => !state)}
        onKeyDown={keyDown}
      >
        <span className={selected ? "" : "placeholder"}>
          {tr(selected?.label ?? placeholder)}
        </span>
        <ChevronDown size={15} aria-hidden="true" />
      </button>
      {open &&
        createPortal(
          <div
            ref={menu}
            className="smart-select-menu smart-select-menu-portal"
            id={listId}
            role="listbox"
            aria-label={ariaLabel || tr("Selecionar")}
            style={menuStyle}
          >
            {options.map((option, index) => (
              <button
                type="button"
                key={`${option.value}-${option.label}`}
                className={`smart-select-option ${option.value === current ? "selected" : ""} ${index === active ? "active" : ""}`}
                role="option"
                id={`${listId}-${index}`}
                tabIndex={-1}
                aria-selected={option.value === current}
                disabled={option.disabled}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(option)}
              >
                <span>
                  <strong>{tr(option.label)}</strong>
                  {option.meta && <small>{option.meta}</small>}
                </span>
                {option.value === current && <Check size={14} />}
              </button>
            ))}
          </div>,
          root.current?.closest("dialog") ?? document.body,
        )}
    </div>
  );
}

type DateFieldProps = {
  name: string;
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  min?: string;
  max?: string;
  ariaLabel?: string;
  disabled?: boolean;
};

const iso = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const parseIso = (value: string) => {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1, 12);
};

const prettyDate = (value: string) =>
  value
    ? parseIso(value).toLocaleDateString(currentLocale(), {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : tr("Selecionar data");

export function DateField({
  name,
  value,
  defaultValue = "",
  onChange,
  min,
  max,
  ariaLabel,
  disabled = false,
}: DateFieldProps) {
  const controlled = value !== undefined;
  const [internal, setInternal] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const current = controlled ? value! : internal;
  const initial = current ? parseIso(current) : new Date();
  const [cursor, setCursor] = useState(
    new Date(initial.getFullYear(), initial.getMonth(), 1, 12),
  );
  const root = useRef<HTMLDivElement>(null);
  const dateButton = useRef<HTMLButtonElement>(null);
  const calendar = useRef<HTMLDivElement>(null);
  const [calendarStyle, setCalendarStyle] = useState<CSSProperties>({});
  const [focusedDate, setFocusedDate] = useState(current || iso(new Date()));
  const calendarId = useId();

  useLayoutEffect(() => {
    if (!open) return;
    const position = () => {
      const rect = dateButton.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(304, window.innerWidth - 24);
      const height = calendar.current?.offsetHeight || 360;
      const below = window.innerHeight - rect.bottom;
      const top =
        below >= height + 12
          ? rect.bottom + 6
          : Math.max(12, rect.top - height - 6);
      setCalendarStyle({
        position: "fixed",
        top,
        left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
        width,
        right: "auto",
        bottom: "auto",
        maxHeight: window.innerHeight - 24,
        overflowY: "auto",
      });
    };
    position();
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    return () => {
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
    };
  }, [open]);
  useEffect(() => {
    if (open)
      calendar.current
        ?.querySelector<HTMLButtonElement>(`[data-date="${focusedDate}"]`)
        ?.focus({ preventScroll: true });
  }, [open, focusedDate]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        !root.current?.contains(target) &&
        !calendar.current?.contains(target)
      ) {
        setOpen(false);
      }
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);

  const days = useMemo(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1, 12);
    const start = new Date(first);
    start.setDate(1 - first.getDay());
    return Array.from({ length: 42 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      return date;
    });
  }, [cursor]);

  const pick = (next: string) => {
    if ((min && next < min) || (max && next > max)) return;
    if (!controlled) setInternal(next);
    onChange?.(next);
    setOpen(false);
    dateButton.current?.focus();
  };

  return (
    <div className={`date-field ${open ? "open" : ""}`} ref={root}>
      <input type="hidden" name={name} value={current} />
      <button
        type="button"
        className="date-trigger"
        ref={dateButton}
        aria-haspopup="dialog"
        aria-controls={calendarId}
        aria-label={ariaLabel ? tr(ariaLabel) : undefined}
        aria-expanded={open}
        disabled={disabled}
        onClick={() => {
          if (!open) {
            const next = current || iso(new Date());
            setFocusedDate(next);
            const date = parseIso(next);
            setCursor(new Date(date.getFullYear(), date.getMonth(), 1, 12));
          }
          setOpen((state) => !state);
        }}
      >
        <CalendarDays size={15} />
        <span className={current ? "" : "placeholder"}>
          {prettyDate(current)}
        </span>
      </button>
      {open &&
        createPortal(
          <div
            ref={calendar}
            style={calendarStyle}
            className="date-popover"
            id={calendarId}
            role="dialog"
            aria-label={tr("Calendário")}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                setOpen(false);
                dateButton.current?.focus();
              }
              if (
                ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
                  event.key,
                ) &&
                event.target instanceof HTMLElement &&
                event.target.dataset.date
              ) {
                event.preventDefault();
                const next = parseIso(event.target.dataset.date);
                next.setDate(
                  next.getDate() +
                    (event.key === "ArrowLeft"
                      ? -1
                      : event.key === "ArrowRight"
                        ? 1
                        : event.key === "ArrowUp"
                          ? -7
                          : 7),
                );
                const value = iso(next);
                if ((min && value < min) || (max && value > max)) return;
                setCursor(new Date(next.getFullYear(), next.getMonth(), 1, 12));
                setFocusedDate(value);
              }
            }}
          >
            <div className="date-popover-head">
              <button
                type="button"
                aria-label={tr("Mês anterior")}
                onClick={() =>
                  setCursor(
                    (date) =>
                      new Date(date.getFullYear(), date.getMonth() - 1, 1, 12),
                  )
                }
              >
                <ChevronLeft size={16} />
              </button>
              <strong>
                {cursor.toLocaleDateString(currentLocale(), {
                  month: "long",
                  year: "numeric",
                })}
              </strong>
              <button
                type="button"
                aria-label={tr("Próximo mês")}
                onClick={() =>
                  setCursor(
                    (date) =>
                      new Date(date.getFullYear(), date.getMonth() + 1, 1, 12),
                  )
                }
              >
                <ChevronRight size={16} />
              </button>
            </div>
            <div className="date-weekdays" aria-hidden="true">
              {Array.from(
                { length: 7 },
                (_, index) => new Date(2026, 0, 4 + index),
              ).map((day, index) => (
                <span key={index}>
                  {day.toLocaleDateString(currentLocale(), {
                    weekday: "narrow",
                  })}
                </span>
              ))}
            </div>
            <div className="date-grid">
              {days.map((date) => {
                const value = iso(date);
                const outside = date.getMonth() !== cursor.getMonth();
                const unavailable = Boolean(
                  (min && value < min) || (max && value > max),
                );
                return (
                  <button
                    type="button"
                    key={value}
                    className={`${outside ? "outside" : ""} ${value === current ? "selected" : ""}`}
                    disabled={unavailable}
                    data-date={value}
                    tabIndex={value === focusedDate ? 0 : -1}
                    aria-pressed={value === current}
                    aria-label={date.toLocaleDateString(currentLocale())}
                    onClick={() => pick(value)}
                  >
                    {date.getDate()}
                  </button>
                );
              })}
            </div>
            <div className="date-popover-foot">
              <button
                type="button"
                disabled={Boolean(
                  (min && iso(new Date()) < min) ||
                  (max && iso(new Date()) > max),
                )}
                onClick={() => pick(iso(new Date()))}
              >
                {tr("Hoje")}
              </button>
            </div>
          </div>,
          root.current?.closest("dialog") ?? document.body,
        )}
    </div>
  );
}

export function ControlLabel({ children }: { children: ReactNode }) {
  return <span className="control-label">{children}</span>;
}
