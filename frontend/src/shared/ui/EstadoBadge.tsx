import { cx } from "./cx";

export const ETIQUETA_ESTADO: Record<string, string> = {
  reservado: "Reservado",
  confirmado: "Confirmado",
  asistido: "Asistido",
  ausente: "Ausente",
  cancelado: "Cancelado",
};

const ESTILO: Record<string, { caja: string; punto: string }> = {
  reservado: { caja: "bg-surface-2 text-foreground", punto: "bg-muted" },
  confirmado: { caja: "bg-primary-soft text-primary-hover", punto: "bg-primary" },
  asistido: { caja: "bg-success-soft text-success", punto: "bg-success" },
  ausente: { caja: "bg-warning-soft text-warning", punto: "bg-warning" },
  cancelado: { caja: "bg-danger-soft text-danger", punto: "bg-danger" },
};

/** Estado del turno con punto de color + texto (nunca solo color). */
export function EstadoBadge({ estado, className }: { estado: string; className?: string }) {
  const estilo = ESTILO[estado] ?? { caja: "bg-surface-2 text-foreground", punto: "bg-muted" };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs font-medium",
        estilo.caja,
        className,
      )}
    >
      <span aria-hidden className={cx("size-1.5 rounded-full", estilo.punto)} />
      {ETIQUETA_ESTADO[estado] ?? estado}
    </span>
  );
}
