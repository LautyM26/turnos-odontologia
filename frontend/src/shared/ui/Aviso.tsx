import type { ReactNode } from "react";

type Tipo = "info" | "exito" | "error" | "alerta";

const ESTILO: Record<Tipo, string> = {
  info: "border-border bg-surface",
  exito: "border-success bg-success-soft text-success",
  error: "border-danger bg-danger-soft text-danger",
  alerta: "border-warning bg-warning-soft text-warning",
};

interface Props {
  tipo: Tipo;
  children: ReactNode;
  id?: string;
  className?: string;
}

/** Mensaje junto a la acción: `role="alert"` si es error, `role="status"` en el resto. */
export function Aviso({ tipo, children, id, className = "" }: Props) {
  return (
    <div
      id={id}
      role={tipo === "error" ? "alert" : "status"}
      className={`rounded-md border px-3 py-2 text-sm ${ESTILO[tipo]} ${className}`}
    >
      {children}
    </div>
  );
}
