import type { ReactNode } from "react";

/** Vacío compuesto: ícono, título, explicación y la acción para poblarlo. */
export function EmptyState({
  icono,
  titulo,
  texto,
  accion,
}: {
  icono: ReactNode;
  titulo: string;
  texto?: string;
  accion?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <span
        aria-hidden
        className="mb-3 grid size-11 place-items-center rounded-xl bg-primary-soft text-primary [&>svg]:size-5"
      >
        {icono}
      </span>
      <p className="font-heading text-base font-semibold">{titulo}</p>
      {texto ? <p className="mt-1 max-w-sm text-sm text-muted">{texto}</p> : null}
      {accion ? <div className="mt-4">{accion}</div> : null}
    </div>
  );
}
