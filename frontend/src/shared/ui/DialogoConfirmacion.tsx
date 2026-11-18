import { type ReactNode, useEffect, useRef } from "react";

interface Props {
  abierto: boolean;
  titulo: string;
  confirmar: string;
  cancelar?: string;
  onConfirmar: () => void;
  onCancelar: () => void;
  children: ReactNode;
}

/** Confirmación modal con `<dialog>` nativo (trampa de foco y Escape nativos). */
export function DialogoConfirmacion({
  abierto,
  titulo,
  confirmar,
  cancelar = "Cancelar",
  onConfirmar,
  onCancelar,
  children,
}: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const botonCancelar = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const el = dialogo.current;
    if (el === null) {
      return;
    }
    if (abierto && !el.open) {
      el.showModal();
      botonCancelar.current?.focus();
    } else if (!abierto && el.open) {
      el.close();
    }
  }, [abierto]);

  if (!abierto) {
    return <dialog ref={dialogo} />;
  }
  return (
    <dialog
      ref={dialogo}
      aria-labelledby="dialogo-titulo"
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-[20px] border border-border bg-surface p-6 text-foreground shadow-lg backdrop:bg-foreground/35 backdrop:backdrop-blur-[3px] motion-safe:animate-[aparecer_200ms_var(--ease-suave)]"
      onCancel={(e) => {
        e.preventDefault();
        onCancelar();
      }}
    >
      <h2 id="dialogo-titulo" className="text-lg font-semibold">
        {titulo}
      </h2>
      <div className="mt-2 text-sm text-muted">{children}</div>
      <div className="mt-6 flex justify-end gap-2">
        <button
          ref={botonCancelar}
          className="h-10 cursor-pointer rounded-[10px] border border-border bg-surface px-4 text-sm font-medium transition-colors hover:bg-surface-2"
          type="button"
          onClick={onCancelar}
        >
          {cancelar}
        </button>
        <button
          className="h-10 cursor-pointer rounded-[10px] bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover"
          type="button"
          onClick={onConfirmar}
        >
          {confirmar}
        </button>
      </div>
    </dialog>
  );
}
