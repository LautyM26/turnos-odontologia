import type { ReactNode } from "react";
import { NavLink } from "react-router";

import { cx } from "./cx";

export interface Pestana {
  to: string;
  etiqueta: string;
  icono?: ReactNode;
}

/** Pestañas de navegación (C-20 D3): NavLink con `aria-current="page"` y subrayado activo. */
export function Tabs({ etiqueta, pestanas }: { etiqueta: string; pestanas: Pestana[] }) {
  return (
    <nav aria-label={etiqueta} className="-mx-1 overflow-x-auto border-b border-border">
      <ul className="flex min-w-max gap-1 px-1">
        {pestanas.map((p) => (
          <li key={p.to}>
            <NavLink
              to={p.to}
              className={({ isActive }) =>
                cx(
                  "relative inline-flex h-11 items-center gap-2 px-3 text-sm font-medium transition-colors duration-150",
                  "after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:origin-center after:rounded-full after:bg-primary after:transition-transform after:duration-200",
                  isActive
                    ? "text-foreground after:scale-x-100"
                    : "text-muted after:scale-x-0 hover:text-foreground",
                )
              }
            >
              {p.icono ? (
                <span aria-hidden className="inline-flex [&>svg]:size-4">
                  {p.icono}
                </span>
              ) : null}
              {p.etiqueta}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
