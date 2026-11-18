import { X } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef } from "react";

import { cx } from "./cx";

interface Props {
  abierto: boolean;
  titulo: string;
  descripcion?: ReactNode;
  onCerrar: () => void;
  children: ReactNode;
  pie?: ReactNode;
  lado?: "derecha" | "izquierda";
  ancho?: string;
}

/**
 * Panel lateral sobre `<dialog>` nativo (C-07 D4): `showModal()` atrapa el foco y Escape lo
 * cierra. Entra con un desplazamiento corto (anulado por `prefers-reduced-motion`).
 */
export function Drawer({
  abierto,
  titulo,
  descripcion,
  onCerrar,
  children,
  pie,
  lado = "derecha",
  ancho = "max-w-md",
}: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const idTitulo = useId();

  useEffect(() => {
    const el = dialogo.current;
    if (el === null) {
      return;
    }
    if (abierto && !el.open) {
      el.showModal();
    } else if (!abierto && el.open) {
      el.close();
    }
  }, [abierto]);

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: el clic en el fondo cierra; Escape lo maneja onCancel del <dialog>
    <dialog
      ref={dialogo}
      aria-labelledby={idTitulo}
      onCancel={(e) => {
        e.preventDefault();
        onCerrar();
      }}
      onClick={(e) => {
        // clic en el backdrop (fuera del panel) cierra
        if (e.target === e.currentTarget) {
          onCerrar();
        }
      }}
      className={cx(
        "m-0 h-dvh max-h-dvh w-full bg-transparent p-0 backdrop:bg-foreground/30 backdrop:backdrop-blur-[2px]",
        lado === "derecha" ? "ml-auto" : "mr-auto",
        ancho,
      )}
    >
      {abierto && (
        <div
          className={cx(
            "flex h-full flex-col bg-surface shadow-lg",
            lado === "derecha"
              ? "border-l border-border motion-safe:animate-[entrar-derecha_240ms_var(--ease-suave)]"
              : "border-r border-border motion-safe:animate-[entrar-izquierda_240ms_var(--ease-suave)]",
          )}
        >
          <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
            <div className="min-w-0">
              <h2 id={idTitulo} className="truncate text-lg font-semibold">
                {titulo}
              </h2>
              {descripcion ? <div className="mt-0.5 text-sm text-muted">{descripcion}</div> : null}
            </div>
            <button
              type="button"
              onClick={onCerrar}
              aria-label="Cerrar panel"
              className="grid size-8 shrink-0 cursor-pointer place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
            >
              <X aria-hidden className="size-4" />
            </button>
          </header>
          <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
          {pie ? (
            <footer className="flex justify-end gap-2 border-t border-border bg-surface-2/60 px-5 py-3">
              {pie}
            </footer>
          ) : null}
        </div>
      )}
    </dialog>
  );
}
