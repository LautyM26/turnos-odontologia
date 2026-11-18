import type { ReactNode } from "react";

import { cx } from "./cx";

/** Encabezado de pantalla de la app (C-20 D3): título, descripción, migas y acciones. */
export function PageHeader({
  titulo,
  descripcion,
  migas,
  acciones,
  className,
}: {
  titulo: ReactNode;
  descripcion?: ReactNode;
  migas?: ReactNode;
  acciones?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cx("flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="min-w-0">
        {migas ? <div className="mb-1.5 text-[13px] text-muted">{migas}</div> : null}
        <h1 className="text-2xl font-semibold sm:text-[28px]">{titulo}</h1>
        {descripcion ? <div className="mt-1 text-sm text-muted">{descripcion}</div> : null}
      </div>
      {acciones ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{acciones}</div>
      ) : null}
    </header>
  );
}
