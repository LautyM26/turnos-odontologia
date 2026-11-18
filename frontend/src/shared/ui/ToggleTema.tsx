import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { cx } from "./cx";
import { type Tema, useTema } from "./tema";

const OPCIONES: { tema: Tema; etiqueta: string; Icono: typeof Sun }[] = [
  { tema: "claro", etiqueta: "Claro", Icono: Sun },
  { tema: "oscuro", etiqueta: "Oscuro", Icono: Moon },
  { tema: "sistema", etiqueta: "Sistema", Icono: Monitor },
];

/** Control de tema (C-20 D1): botón con menú Claro / Oscuro / Sistema; Escape lo cierra. */
export function ToggleTema({ className }: { className?: string }) {
  const [tema, setTema] = useTema();
  const [abierto, setAbierto] = useState(false);
  const idMenu = useId();
  const caja = useRef<HTMLDivElement>(null);
  const actual = OPCIONES.find((o) => o.tema === tema) ?? OPCIONES[2];
  const IconoActual = actual?.Icono ?? Monitor;

  useEffect(() => {
    if (!abierto) {
      return;
    }
    const alTeclear = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        setAbierto(false);
      }
    };
    const alClic = (e: MouseEvent): void => {
      if (caja.current && !caja.current.contains(e.target as Node)) {
        setAbierto(false);
      }
    };
    document.addEventListener("keydown", alTeclear);
    document.addEventListener("mousedown", alClic);
    return () => {
      document.removeEventListener("keydown", alTeclear);
      document.removeEventListener("mousedown", alClic);
    };
  }, [abierto]);

  return (
    <div ref={caja} className={cx("relative", className)}>
      <button
        type="button"
        aria-label={`Tema: ${actual?.etiqueta ?? "Sistema"}`}
        aria-haspopup="true"
        aria-expanded={abierto}
        aria-controls={idMenu}
        onClick={() => setAbierto((v) => !v)}
        className="grid size-9 cursor-pointer place-items-center rounded-lg border border-border bg-surface text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
      >
        <IconoActual aria-hidden className="size-[18px]" />
      </button>
      {abierto && (
        <fieldset
          id={idMenu}
          aria-label="Tema de color"
          className="absolute right-0 top-11 z-50 w-40 rounded-xl border border-border bg-surface p-1 shadow-md motion-safe:animate-[aparecer_140ms_var(--ease-suave)]"
        >
          {OPCIONES.map(({ tema: opcion, etiqueta, Icono }) => (
            <button
              key={opcion}
              type="button"
              aria-pressed={tema === opcion}
              onClick={() => {
                setTema(opcion);
                setAbierto(false);
              }}
              className={cx(
                "flex h-9 w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 text-sm transition-colors",
                tema === opcion
                  ? "bg-primary-soft font-medium text-primary-hover"
                  : "text-foreground hover:bg-surface-2",
              )}
            >
              <Icono aria-hidden className="size-4" />
              {etiqueta}
            </button>
          ))}
        </fieldset>
      )}
    </div>
  );
}
