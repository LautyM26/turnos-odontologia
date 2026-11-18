/**
 * Shell autenticado (C-07 D5): sidebar con la navegación principal y barra superior con
 * identidad, roles y "Cerrar sesión" (spec web-session). En < 1024 px la sidebar es un panel
 * que se abre con "Abrir menú" y se cierra con Escape, con el overlay o al navegar.
 * Las rutas pueden pedir ancho completo con `handle: { anchoCompleto: true }` (la agenda).
 */

import { CalendarDays, LogOut, Menu, Users, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useMatches, useNavigate } from "react-router";

import { cx } from "@/shared/ui/cx";

import { rolesLegibles } from "./roles";
import { cerrarSesion, useSesion } from "./session";

const NAVEGACION = [
  { to: "/agenda", etiqueta: "Agenda", Icono: CalendarDays },
  { to: "/pacientes", etiqueta: "Pacientes", Icono: Users },
] as const;

function iniciales(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

export function AppLayout() {
  const me = useSesion();
  const navigate = useNavigate();
  const location = useLocation();
  const matches = useMatches();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const anchoCompleto = matches.some(
    (m) => (m.handle as { anchoCompleto?: boolean } | undefined)?.anchoCompleto,
  );

  // Cerrar el menú móvil al navegar (pathname cambia).
  // biome-ignore lint/correctness/useExhaustiveDependencies: depende solo del cambio de ruta
  useEffect(() => {
    setMenuAbierto(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuAbierto) {
      return;
    }
    const alTeclear = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        setMenuAbierto(false);
      }
    };
    document.addEventListener("keydown", alTeclear);
    return () => document.removeEventListener("keydown", alTeclear);
  }, [menuAbierto]);

  async function salir(): Promise<void> {
    await cerrarSesion();
    await navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <a
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:shadow-md"
        href="#contenido"
      >
        Saltar al contenido
      </a>

      {menuAbierto && (
        <button
          type="button"
          aria-label="Cerrar menú"
          tabIndex={-1}
          className="fixed inset-0 z-30 bg-foreground/30 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMenuAbierto(false)}
        />
      )}

      <aside
        id="menu-principal"
        className={cx(
          "fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col border-r border-border bg-surface",
          "transition-transform duration-[240ms] ease-suave lg:w-[248px] lg:translate-x-0",
          menuAbierto ? "translate-x-0 shadow-lg" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between gap-3 px-5">
          <div className="flex items-center gap-2.5">
            <span
              aria-hidden
              className="grid size-8 place-items-center rounded-[10px] bg-primary font-heading text-sm font-bold text-primary-foreground shadow-xs"
            >
              T
            </span>
            <span className="font-heading text-[15px] font-semibold leading-tight">
              Turnos
              <span className="block text-xs font-medium text-muted">Odontología</span>
            </span>
          </div>
          <button
            type="button"
            aria-label="Cerrar menú"
            className="grid size-8 cursor-pointer place-items-center rounded-lg text-muted hover:bg-surface-2 lg:hidden"
            onClick={() => setMenuAbierto(false)}
          >
            <X aria-hidden className="size-4" />
          </button>
        </div>

        <nav aria-label="Principal" className="flex-1 px-3 py-2">
          <ul className="space-y-0.5">
            {NAVEGACION.map(({ to, etiqueta, Icono }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  className={({ isActive }) =>
                    cx(
                      "group flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors duration-150",
                      isActive
                        ? "bg-primary-soft text-primary-hover"
                        : "text-muted hover:bg-surface-2 hover:text-foreground",
                    )
                  }
                >
                  <Icono aria-hidden className="size-[18px]" strokeWidth={1.75} />
                  {etiqueta}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="border-t border-border px-5 py-4 text-xs text-muted">
          Clínica Piloto
          <span className="block">Datos sintéticos de demostración</span>
        </div>
      </aside>

      <div className="lg:pl-[248px]">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-surface/85 px-4 backdrop-blur-md sm:px-6">
          <button
            type="button"
            aria-label="Abrir menú"
            aria-expanded={menuAbierto}
            aria-controls="menu-principal"
            className="grid size-9 cursor-pointer place-items-center rounded-lg border border-border bg-surface text-foreground hover:bg-surface-2 lg:hidden"
            onClick={() => setMenuAbierto(true)}
          >
            <Menu aria-hidden className="size-[18px]" />
          </button>
          {me && (
            <div className="ml-auto flex min-w-0 items-center gap-3">
              <span
                aria-hidden
                className="hidden size-8 shrink-0 place-items-center rounded-full bg-primary-soft text-xs font-semibold text-primary-hover sm:grid"
              >
                {iniciales(me.email)}
              </span>
              <span className="min-w-0 text-sm leading-tight">
                <span className="block truncate font-medium">{me.email}</span>
                <span className="block truncate text-xs text-muted">{rolesLegibles(me)}</span>
              </span>
              <button
                className="inline-flex h-9 shrink-0 cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm font-medium transition-colors hover:bg-surface-2"
                type="button"
                onClick={salir}
              >
                <LogOut aria-hidden className="size-4" />
                Cerrar sesión
              </button>
            </div>
          )}
        </header>
        <main
          id="contenido"
          className={cx(
            anchoCompleto ? "px-4 py-5 sm:px-6" : "mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8",
          )}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
