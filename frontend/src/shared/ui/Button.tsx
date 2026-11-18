import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

type Variante = "primary" | "secondary" | "ghost" | "danger";
type Tamano = "sm" | "md";

const VARIANTE: Record<Variante, string> = {
  primary:
    "bg-primary text-primary-foreground shadow-xs hover:bg-primary-hover disabled:hover:bg-primary",
  secondary:
    "border border-border bg-surface text-foreground shadow-xs hover:border-border-strong hover:bg-surface-2",
  ghost: "text-foreground hover:bg-surface-2",
  danger: "border border-danger/30 bg-surface text-danger hover:bg-danger-soft",
};

const TAMANO: Record<Tamano, string> = {
  sm: "h-8 gap-1.5 rounded-lg px-3 text-[13px]",
  md: "h-10 gap-2 rounded-[10px] px-4 text-sm",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamano?: Tamano;
  cargando?: boolean;
  icono?: ReactNode;
}

/** Botón base (MASTER.md): una línea, contraste AA, feedback de presión y estado de carga. */
export function Button({
  variante = "primary",
  tamano = "md",
  cargando = false,
  icono,
  className,
  children,
  disabled,
  type = "button",
  ...resto
}: Props) {
  return (
    <button
      type={type}
      className={cx(
        "inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap font-medium",
        "transition-[background-color,border-color,color,transform] duration-150 ease-suave",
        "active:translate-y-px disabled:cursor-not-allowed disabled:opacity-55",
        VARIANTE[variante],
        TAMANO[tamano],
        className,
      )}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      {...resto}
    >
      {cargando ? (
        <Loader2 aria-hidden className="size-4 animate-spin" />
      ) : (
        icono && (
          <span aria-hidden className="inline-flex [&>svg]:size-4">
            {icono}
          </span>
        )
      )}
      {children}
    </button>
  );
}
