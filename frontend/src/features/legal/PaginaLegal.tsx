/** Página legal pública (C-18 RN-CU-01/05, diseño C-20): índice lateral + secciones numeradas. */

import type { ReactNode } from "react";

import { Aviso } from "@/shared/ui/Aviso";

import { AVISO_LEGAL, type TextoLegal } from "./textos";

export function PaginaLegal({
  titulo,
  texto,
  pie,
}: {
  titulo: string;
  texto: TextoLegal;
  pie: ReactNode;
}) {
  return (
    <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <header className="max-w-3xl space-y-3">
        <p className="text-sm text-muted">
          Versión {texto.version} · {texto.fecha}
        </p>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{titulo}</h1>
        <Aviso tipo="alerta">{AVISO_LEGAL}</Aviso>
      </header>
      <div className="mt-10 grid gap-10 lg:grid-cols-[220px_1fr]">
        <nav aria-label="En esta página" className="hidden lg:block">
          <ol className="sticky top-24 space-y-2 border-l border-border text-sm">
            {texto.secciones.map((s, i) => (
              <li key={s.titulo}>
                <a
                  href={`#seccion-${i + 1}`}
                  className="-ml-px block border-l border-transparent pl-4 text-muted transition-colors hover:border-primary hover:text-foreground"
                >
                  {s.titulo}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <div className="max-w-[68ch] space-y-8">
          {texto.secciones.map((seccion, i) => (
            <article
              key={seccion.titulo}
              id={`seccion-${i + 1}`}
              className="scroll-mt-24 space-y-2"
            >
              <h2 className="text-lg font-semibold">{seccion.titulo}</h2>
              {seccion.parrafos.map((parrafo) => (
                <p key={parrafo} className="leading-relaxed text-foreground/90">
                  {parrafo}
                </p>
              ))}
            </article>
          ))}
          <p className="border-t border-border pt-6 text-muted">{pie}</p>
        </div>
      </div>
    </section>
  );
}
