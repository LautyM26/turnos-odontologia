/**
 * Layout de las páginas públicas (C-20 D2): header con marca, "Ingresar" y tema; footer con
 * enlaces legales. Lo comparten landing, reserva, comprobante, reprogramación y legales.
 */

import { LogIn } from "lucide-react";
import { Link, Outlet } from "react-router";

import { ToggleTema } from "./ToggleTema";

export function Marca() {
  return (
    <Link
      to="/"
      className="flex items-center gap-2.5 rounded-lg"
      aria-label="Turnos Odontología, inicio"
    >
      <span
        aria-hidden
        className="grid size-8 place-items-center rounded-[10px] bg-primary font-heading text-sm font-bold text-primary-foreground shadow-xs"
      >
        T
      </span>
      <span aria-hidden className="font-heading text-[15px] font-semibold leading-tight">
        Turnos
        <span className="block text-xs font-medium text-muted">Odontología</span>
      </span>
    </Link>
  );
}

export function PublicLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border/70 bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <Marca />
          <div className="ml-auto flex items-center gap-2">
            <ToggleTema />
            <Link
              to="/login"
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm font-medium transition-colors hover:bg-surface-2"
            >
              <LogIn aria-hidden className="size-4" />
              Ingresar
            </Link>
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm text-muted sm:px-6">
          <p>Turnos Odontología. Datos de demostración sintéticos.</p>
          <nav aria-label="Legales" className="flex gap-4">
            <Link className="hover:text-foreground hover:underline" to="/privacidad">
              Privacidad
            </Link>
            <Link className="hover:text-foreground hover:underline" to="/cumplimiento">
              Cumplimiento
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
