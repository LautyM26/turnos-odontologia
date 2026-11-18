import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { cx } from "./cx";

type Tipo = "info" | "exito" | "error" | "alerta";

const ESTILO: Record<Tipo, string> = {
  info: "border-border bg-surface-2 text-foreground",
  exito: "border-success/25 bg-success-soft text-success",
  error: "border-danger/25 bg-danger-soft text-danger",
  alerta: "border-warning/25 bg-warning-soft text-warning",
};

const ICONO: Record<Tipo, typeof Info> = {
  info: Info,
  exito: CircleCheck,
  error: CircleAlert,
  alerta: TriangleAlert,
};

interface Props {
  tipo: Tipo;
  children: ReactNode;
  id?: string;
  className?: string;
}

/** Mensaje junto a la acción: `role="alert"` si es error, `role="status"` en el resto. */
export function Aviso({ tipo, children, id, className = "" }: Props) {
  const Icono = ICONO[tipo];
  return (
    <div
      id={id}
      role={tipo === "error" ? "alert" : "status"}
      className={cx(
        "flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm",
        "motion-safe:animate-[aparecer_180ms_var(--ease-suave)]",
        ESTILO[tipo],
        className,
      )}
    >
      <Icono aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
