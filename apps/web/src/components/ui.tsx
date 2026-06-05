"use client";

import { forwardRef, useEffect } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from "react";
import { Spinner, UploadCloud } from "./icons";

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
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-[var(--radius)] border border-border bg-surface-muted px-4 py-3.5 transition hover:bg-subtle">
      <div className="min-w-0">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <div className="truncate text-xs text-muted-foreground">{file ? file.name : hint}</div>
      </div>
      <span
        className={`inline-flex shrink-0 items-center gap-1.5 rounded-[var(--radius)] px-3 py-2 text-xs font-semibold text-white ${
          variant === "primary" ? "bg-ink" : "bg-[var(--color-ink-700)]"
        }`}
      >
        <UploadCloud width={14} height={14} /> 파일 선택
      </span>
      <input
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
    </label>
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
