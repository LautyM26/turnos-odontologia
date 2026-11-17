import { Link } from "react-router";
import { AVISO_LEGAL, PRIVACIDAD } from "@/features/legal/textos";
import { Aviso } from "@/shared/ui/Aviso";

/** Política de privacidad pública (RN-CU-01): ubicación declarada, sin datos reales. */
export function PrivacidadPage() {
  return (
    <section className="mx-auto max-w-3xl space-y-6 p-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Política de privacidad</h1>
        <Aviso tipo="alerta">{AVISO_LEGAL}</Aviso>
        <p className="text-sm text-muted">
          Versión {PRIVACIDAD.version} · {PRIVACIDAD.fecha}
        </p>
      </header>
      {PRIVACIDAD.secciones.map((seccion) => (
        <article key={seccion.titulo} className="space-y-2">
          <h2 className="text-lg font-medium">{seccion.titulo}</h2>
          {seccion.parrafos.map((parrafo) => (
            <p key={parrafo}>{parrafo}</p>
          ))}
        </article>
      ))}
      <p>
        Mirá cómo cumplimos la normativa en <Link to="/cumplimiento">cumplimiento</Link>.
      </p>
    </section>
  );
}
