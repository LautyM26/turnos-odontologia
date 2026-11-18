import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

/** Superficie con borde y radio 14: solo cuando la elevación comunica jerarquía real. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx("rounded-[14px] border border-border bg-surface shadow-xs", className)}
      {...props}
    />
  );
}

export function CardHeader({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: ReactNode;
  descripcion?: ReactNode;
  acciones?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
      <div>
        <h2 className="text-base font-semibold">{titulo}</h2>
        {descripcion ? <p className="mt-0.5 text-sm text-muted">{descripcion}</p> : null}
      </div>
      {acciones ? <div className="flex shrink-0 gap-2">{acciones}</div> : null}
    </div>
  );
}
