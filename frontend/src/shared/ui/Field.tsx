import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

import { cx } from "./cx";

export interface PropsControl {
  id: string;
  "aria-describedby"?: string | undefined;
  "aria-invalid"?: boolean | undefined;
}

interface FieldProps {
  id: string;
  label: string;
  ayuda?: string | undefined;
  error?: string | undefined;
  className?: string;
  children: (control: PropsControl) => ReactNode;
}

/** Label arriba, ayuda y error debajo, asociados al control con aria-describedby (MASTER.md). */
export function Field({ id, label, ayuda, error, className, children }: FieldProps) {
  const descripcion = [error ? `${id}-error` : null, ayuda ? `${id}-ayuda` : null]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[13px] font-medium text-foreground">
        {label}
      </label>
      {children({
        id,
        "aria-describedby": descripcion || undefined,
        "aria-invalid": error ? true : undefined,
      })}
      {error ? (
        <p id={`${id}-error`} className="text-[13px] text-danger">
          {error}
        </p>
      ) : null}
      {ayuda ? (
        <p id={`${id}-ayuda`} className="text-xs text-muted">
          {ayuda}
        </p>
      ) : null}
    </div>
  );
}

const CONTROL =
  "w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground shadow-xs " +
  "transition-[border-color,box-shadow] duration-150 placeholder:text-muted " +
  "hover:border-border-strong focus:border-primary focus:outline-none focus:ring-3 focus:ring-focus " +
  "aria-[invalid=true]:border-danger disabled:cursor-not-allowed disabled:bg-surface-2";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(CONTROL, "h-10", className)} {...props} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx(CONTROL, "h-10 cursor-pointer pr-8", className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx(CONTROL, "min-h-20 py-2", className)} {...props} />;
}
