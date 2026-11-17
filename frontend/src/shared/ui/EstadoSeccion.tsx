import { Aviso } from "./Aviso";

export type Estado =
  | { tipo: "cargando" }
  | { tipo: "vacio"; mensaje: string }
  | { tipo: "error"; mensaje: string; onReintentar: () => void }
  | { tipo: "sin-acceso" }
  | { tipo: "sin-consentimiento" };

export const TEXTO_SIN_ACCESO = "Sin acceso clínico: tu rol no permite ver la historia clínica";
export const TEXTO_SIN_CONSENTIMIENTO =
  "Sin consentimiento de datos: no se pueden cargar datos de salud";

/** Estados no felices de una sección (cargando, vacío, error, sin acceso, sin consentimiento). */
export function EstadoSeccion({ estado }: { estado: Estado }) {
  switch (estado.tipo) {
    case "cargando":
      return (
        <p aria-busy="true" className="text-muted">
          Cargando…
        </p>
      );
    case "vacio":
      return <p className="text-muted">{estado.mensaje}</p>;
    case "error":
      return (
        <div className="space-y-2">
          <Aviso tipo="error">{estado.mensaje}</Aviso>
          <button
            className="rounded border border-border px-3 py-1"
            type="button"
            onClick={estado.onReintentar}
          >
            Reintentar
          </button>
        </div>
      );
    case "sin-acceso":
      return <Aviso tipo="alerta">{TEXTO_SIN_ACCESO}</Aviso>;
    case "sin-consentimiento":
      return <Aviso tipo="alerta">{TEXTO_SIN_CONSENTIMIENTO}</Aviso>;
  }
}
