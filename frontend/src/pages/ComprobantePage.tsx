import { FileText } from "lucide-react";
import { useParams } from "react-router";

/** Comprobante público (ruta reservada; la factura ARCA llega con C-13). */
export function ComprobantePage() {
  const params = useParams();
  return (
    <section className="mx-auto max-w-xl px-4 py-14">
      <span
        aria-hidden
        className="grid size-11 place-items-center rounded-xl bg-primary-soft text-primary"
      >
        <FileText className="size-5" />
      </span>
      <h1 className="mt-4 text-3xl font-bold tracking-tight">Comprobante</h1>
      <p className="mt-2 text-muted">Comprobante: {params.id}</p>
    </section>
  );
}
