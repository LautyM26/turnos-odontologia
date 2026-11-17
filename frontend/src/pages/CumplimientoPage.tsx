import { Link } from "react-router";
import { AVISO_LEGAL, CUMPLIMIENTO } from "@/features/legal/textos";
import { Aviso } from "@/shared/ui/Aviso";

/** Página pública de cumplimiento (RN-CU-05): textos estáticos, no depende de la API. */
export function CumplimientoPage() {
  return (
    <section className="mx-auto max-w-3xl space-y-6 p-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Cumplimiento y privacidad</h1>
        <Aviso tipo="alerta">{AVISO_LEGAL}</Aviso>
        <p className="text-sm text-muted">
          Versión {CUMPLIMIENTO.version} · {CUMPLIMIENTO.fecha}
        </p>
      </header>
      {CUMPLIMIENTO.secciones.map((seccion) => (
        <article key={seccion.titulo} className="space-y-2">
          <h2 className="text-lg font-medium">{seccion.titulo}</h2>
          {seccion.parrafos.map((parrafo) => (
            <p key={parrafo}>{parrafo}</p>
          ))}
        </article>
      ))}
      <p>
        Leé también la <Link to="/privacidad">política de privacidad</Link>.
      </p>
    </section>
  );
}
