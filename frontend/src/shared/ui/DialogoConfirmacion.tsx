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
      className="m-auto max-w-md rounded-lg border border-border p-5 backdrop:bg-black/40"
      onCancel={(e) => {
        e.preventDefault();
        onCancelar();
      }}
    >
      <h2 id="dialogo-titulo" className="text-lg font-semibold">
        {titulo}
      </h2>
      <div className="mt-2 text-sm">{children}</div>
      <div className="mt-4 flex justify-end gap-2">
        <button
          ref={botonCancelar}
          className="rounded border border-border px-3 py-1"
          type="button"
          onClick={onCancelar}
        >
          {cancelar}
        </button>
        <button
          className="rounded bg-primary px-3 py-1 text-primary-foreground"
          type="button"
          onClick={onConfirmar}
        >
          {confirmar}
        </button>
      </div>
    </dialog>
  );
}
