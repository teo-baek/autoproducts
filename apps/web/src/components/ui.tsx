"use client";

import { forwardRef, useEffect, useRef, useState } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";
import { ChevronDown, Spinner, UploadCloud, X as XIcon } from "./icons";

/* ── Button ─────────────────────────────────────────────────────────────── */
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
};

const BTN_VARIANTS: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "bg-ink text-white hover:bg-ink-strong",
  secondary: "bg-surface-muted text-foreground border border-border hover:bg-subtle",
  ghost: "text-foreground hover:bg-subtle",
  danger: "bg-[var(--color-danger)] text-white hover:opacity-90",
};

export function Button({
  variant = "primary",
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-[var(--radius)] px-5 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${BTN_VARIANTS[variant]} ${className}`}
      disabled={loading || disabled}
      {...rest}
    >
      {loading && <Spinner width={16} height={16} />}
      {children}
    </button>
  );
}

/* ── TextField ──────────────────────────────────────────────────────────── */
type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  leftIcon?: ReactNode;
  right?: ReactNode;
  labelRight?: ReactNode;
};

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  function TextField(
    { label, leftIcon, right, labelRight, className = "", id, name, ...rest },
    ref
  ) {
    const inputId = id ?? name;
    return (
      <div>
        {label && (
          <div className="mb-2 flex items-center justify-between">
            <label
              htmlFor={inputId}
              className="text-sm font-semibold text-[var(--color-text-secondary)]"
            >
              {label}
            </label>
            {labelRight}
          </div>
        )}
        <div className="relative">
          {leftIcon && (
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-border-strong">
              {leftIcon}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            name={name}
            className={`w-full rounded-[var(--radius)] border border-border bg-subtle px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-placeholder focus:border-ink focus:ring-2 focus:ring-ink/15 ${leftIcon ? "pl-11" : ""} ${right ? "pr-11" : ""} ${className}`}
            {...rest}
          />
          {right && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2">{right}</span>
          )}
        </div>
      </div>
    );
  }
);

/* ── Checkbox ───────────────────────────────────────────────────────────── */
type CheckboxProps = InputHTMLAttributes<HTMLInputElement> & { label?: ReactNode };

export function Checkbox({ label, className = "", ...rest }: CheckboxProps) {
  return (
    <label className="flex cursor-pointer select-none items-start gap-2.5 text-sm text-foreground">
      <input
        type="checkbox"
        className={`mt-0.5 size-4 shrink-0 rounded-[5px] border-border accent-[var(--color-ink)] ${className}`}
        {...rest}
      />
      {label && <span>{label}</span>}
    </label>
  );
}

/* ── SegTabs (segmented control) ────────────────────────────────────────── */
export function SegTabs<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex w-full gap-1 rounded-[var(--radius)] border border-border bg-surface-muted p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`flex-1 rounded-[6px] px-3 py-2.5 text-sm font-semibold transition ${
            value === o.value
              ? "bg-ink text-white shadow-[var(--shadow-sm)]"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ── FileRow (서류 업로드 행) ───────────────────────────────────────────── */
export function FileRow({
  title,
  hint,
  accept = "image/jpeg,image/png,application/pdf",
  file,
  onPick,
  variant = "primary",
}: {
  title: string;
  hint: string;
  accept?: string;
  file: File | null;
  onPick: (f: File | null) => void;
  variant?: "primary" | "secondary";
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center justify-between gap-3 rounded-[var(--radius)] border border-border bg-surface-muted px-4 py-3.5">
      <div className="min-w-0">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <div className="truncate text-xs text-muted-foreground">{file ? file.name : hint}</div>
      </div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className={`inline-flex shrink-0 items-center gap-1.5 rounded-[var(--radius)] px-3 py-2 text-xs font-semibold text-white transition hover:opacity-90 ${
          variant === "primary" ? "bg-ink" : "bg-[var(--color-ink-700)]"
        }`}
      >
        <UploadCloud width={14} height={14} /> {file ? "변경" : "파일 선택"}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
    </div>
  );
}

/* ── Alert ──────────────────────────────────────────────────────────────── */
export function Alert({
  children,
  tone = "danger",
}: {
  children?: ReactNode;
  tone?: "danger" | "success";
}) {
  if (!children) return null;
  const tones = {
    danger: "bg-[var(--color-danger-bg)] text-[var(--color-danger-fg)]",
    success: "bg-[var(--color-success-bg)] text-[var(--color-success-fg)]",
  };
  return (
    <div className={`rounded-[var(--radius)] px-4 py-3 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

/* ── Badge (상태 배지, §1.4 색 시스템) ──────────────────────────────────── */
type BadgeTone = "success" | "warning" | "danger" | "info" | "grade" | "neutral";
const BADGE_TONES: Record<BadgeTone, string> = {
  success: "bg-[var(--color-success-bg)] text-[var(--color-success-fg)]",
  warning: "bg-[var(--color-warning-bg)] text-[var(--color-warning-fg)]",
  danger: "bg-[var(--color-danger-bg)] text-[var(--color-danger-fg)]",
  info: "bg-[var(--color-info-bg)] text-[var(--color-info-fg)]",
  grade: "bg-[var(--color-grade-bg)] text-[var(--color-grade-fg)]",
  neutral: "bg-subtle text-muted-foreground",
};

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${BADGE_TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/* ── Select ─────────────────────────────────────────────────────────────── */
type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  options: { value: string; label: string }[];
  placeholder?: string;
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, options, placeholder, className = "", id, name, ...rest },
  ref
) {
  const selId = id ?? name;
  return (
    <div>
      {label && (
        <label
          htmlFor={selId}
          className="mb-2 block text-sm font-semibold text-[var(--color-text-secondary)]"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <select
          ref={ref}
          id={selId}
          name={name}
          className={`w-full appearance-none rounded-[var(--radius)] border border-border bg-subtle px-4 py-3 pr-10 text-sm text-foreground outline-none transition focus:border-ink focus:ring-2 focus:ring-ink/15 ${className}`}
          {...rest}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown
          width={16}
          height={16}
          className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-border-strong"
        />
      </div>
    </div>
  );
});

/* ── NumberField (₩ 접두 가능) ─────────────────────────────────────────── */
type NumberFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  prefix?: string;
};

export const NumberField = forwardRef<HTMLInputElement, NumberFieldProps>(
  function NumberField({ label, prefix, className = "", id, name, ...rest }, ref) {
    const inputId = id ?? name;
    return (
      <div>
        {label && (
          <label
            htmlFor={inputId}
            className="mb-2 block text-sm font-semibold text-[var(--color-text-secondary)]"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {prefix && (
            <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
              {prefix}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            name={name}
            inputMode="numeric"
            className={`w-full rounded-[var(--radius)] border border-border bg-subtle py-3 text-right text-sm tabular-nums text-foreground outline-none transition placeholder:text-placeholder focus:border-ink focus:ring-2 focus:ring-ink/15 ${prefix ? "pl-9 pr-4" : "px-4"} ${className}`}
            {...rest}
          />
        </div>
      </div>
    );
  }
);

/* ── Dialog (범용 모달 — 헤더+본문+풋터) ───────────────────────────────── */
const DIALOG_SIZES = { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl", xl: "max-w-5xl" };

export function Dialog({
  open,
  onClose,
  title,
  icon,
  size = "md",
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  icon?: ReactNode;
  size?: keyof typeof DIALOG_SIZES;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <div className="absolute inset-0 bg-ink-strong/45 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        className={`relative flex max-h-[90vh] w-full flex-col ${DIALOG_SIZES[size]} overflow-hidden rounded-[var(--radius-xl)] bg-surface shadow-[var(--shadow-lg)]`}
      >
        {(title || icon) && (
          <div className="flex shrink-0 items-center gap-3 border-b border-divider px-7 py-5">
            {icon && (
              <span className="flex size-9 items-center justify-center rounded-full border border-border text-foreground">
                {icon}
              </span>
            )}
            <h2 className="text-xl font-bold text-foreground">{title}</h2>
            <button
              type="button"
              onClick={onClose}
              className="ml-auto text-border-strong transition hover:text-foreground"
              aria-label="닫기"
            >
              <XIcon width={20} height={20} />
            </button>
          </div>
        )}
        {/* 본문만 스크롤 — 헤더/푸터는 고정(min-h-0 이 있어야 flex 자식이 스크롤됨) */}
        <div className="min-h-0 flex-1 overflow-y-auto px-7 py-6">{children}</div>
        {footer && (
          <div className="flex shrink-0 items-center justify-end gap-3 border-t border-divider bg-surface px-7 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Popover (앵커 메뉴 — 바깥 클릭 닫힘) ──────────────────────────────── */
export function Popover({
  trigger,
  children,
  align = "end",
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "start" | "end";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      {trigger({ open, toggle: () => setOpen((o) => !o) })}
      {open && (
        <div
          className={`absolute top-full z-40 mt-2 min-w-[15rem] rounded-[var(--radius-lg)] border border-divider bg-surface p-1.5 shadow-[var(--shadow-lg)] ${
            align === "end" ? "right-0" : "left-0"
          }`}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

/* ── Card ───────────────────────────────────────────────────────────────── */
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-[var(--radius-lg)] border border-divider bg-surface shadow-[var(--shadow-sm)] ${className}`}
    >
      {children}
    </div>
  );
}

/* ── Modal (중앙 팝업) ──────────────────────────────────────────────────── */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  actionLabel = "확인",
  tone = "danger",
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children?: ReactNode;
  actionLabel?: string;
  tone?: "danger" | "neutral";
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative w-full max-w-sm rounded-[var(--radius-xl)] bg-surface p-7 text-center shadow-[var(--shadow-lg)]"
      >
        {tone === "danger" && (
          <div className="mx-auto mb-4 flex size-11 items-center justify-center rounded-full bg-[var(--color-danger-bg)] text-lg font-bold text-[var(--color-danger-fg)]">
            !
          </div>
        )}
        {title && <h2 className="text-lg font-bold text-foreground">{title}</h2>}
        {description && <p className="mt-2 text-sm text-muted-foreground">{description}</p>}
        {children}
        <div className="mt-6">
          <Button onClick={onClose} className="w-full">
            {actionLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
