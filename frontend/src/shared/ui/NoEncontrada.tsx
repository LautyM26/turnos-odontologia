import { ArrowLeft } from "lucide-react";
import { Link } from "react-router";

export function Component() {
  return (
    <section className="mx-auto max-w-md py-16 text-center">
      <p className="font-heading text-6xl font-bold tracking-tight text-primary">404</p>
      <h1 className="mt-3 text-xl font-semibold">Página no encontrada</h1>
      <p className="mt-2 text-muted">La dirección no existe o cambió de lugar.</p>
      <Link
        className="mt-6 inline-flex h-10 items-center gap-2 rounded-[10px] border border-border bg-surface px-4 text-sm font-medium shadow-xs transition-colors hover:bg-surface-2"
        to="/pacientes"
      >
        <ArrowLeft aria-hidden className="size-4" />
        Volver a pacientes
      </Link>
    </section>
  );
}
