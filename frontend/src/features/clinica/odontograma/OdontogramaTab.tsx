import { useEffect, useState } from "react";
import { useBlocker } from "react-router";

import { ApiError, apiFetch } from "@/shared/api/client";
import { fechaHora, nombreAutor } from "@/shared/formato";
import { Aviso } from "@/shared/ui/Aviso";
import { DialogoConfirmacion } from "@/shared/ui/DialogoConfirmacion";
import { EstadoSeccion, TEXTO_SIN_CONSENTIMIENTO } from "@/shared/ui/EstadoSeccion";

import { useContextoPaciente } from "../pacientes/contexto";
import { puedeEscribirClinica } from "../permisos";
import type { Cara, Denticion, Odontograma } from "../tipos";
import { aPayload, borradorDesde, cambiarDenticion, hallazgos, hayCambios } from "./borrador";
import { ETIQUETA_REGISTRO } from "./fdi";
import { OdontogramaGrafico } from "./OdontogramaGrafico";
import { PanelPieza } from "./PanelPieza";

const DENTICIONES: { valor: Denticion; etiqueta: string }[] = [
  { valor: "permanente", etiqueta: "Permanente" },
  { valor: "temporal", etiqueta: "Temporal" },
  { valor: "mixta", etiqueta: "Mixta" },
];

const MENSAJE_409 =
  "Hay una versión más nueva del odontograma. Recargá para ver los cambios antes de volver a marcar";

function Leyenda() {
  return (
    <fieldset className="flex flex-wrap gap-4 border-0 p-0 text-sm">
      <legend className="sr-only">Leyenda</legend>
      <span className="flex items-center gap-1">
        <svg width="16" height="16" aria-hidden="true" focusable="false">
          <rect width="16" height="16" style={{ fill: "var(--odo-existente)" }} />
        </svg>
        Relleno sólido: {ETIQUETA_REGISTRO.existente.toLowerCase()}
      </span>
      <span className="flex items-center gap-1">
        <svg width="16" height="16" aria-hidden="true" focusable="false">
          <rect width="16" height="16" fill="url(#odo-trama)" stroke="currentColor" />
        </svg>
        Rayado: {ETIQUETA_REGISTRO.a_realizar.toLowerCase()}
      </span>
      <span>X = ausente / extraída · círculo = corona · línea = endodoncia · I = implante</span>
    </fieldset>
  );
}

function Editor({ vigente }: { vigente: Odontograma }) {
  const { paciente, actualizarHistoria, profesionales, yo } = useContextoPaciente();
  const [borrador, setBorrador] = useState(() => borradorDesde(vigente));
  const [panel, setPanel] = useState<{ pieza: number; cara: Cara | null } | null>(null);
  const [cambioDenticion, setCambioDenticion] = useState<{
    valor: Denticion;
    descartadas: number[];
  } | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflicto, setConflicto] = useState(false);
  const [confirmaRecarga, setConfirmaRecarga] = useState(false);
  const [versiones, setVersiones] = useState<Odontograma[] | null>(null);
  const [vista, setVista] = useState<Odontograma | null>(null);

  const cambios = hayCambios(borrador, vigente);
  const sinConsentimiento = !paciente.consentimiento_datos;
  const soloLectura = !puedeEscribirClinica(yo) || vista !== null;
  const bloqueado = soloLectura || sinConsentimiento;

  const bloqueo = useBlocker(
    ({ currentLocation, nextLocation }) =>
      cambios && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (!cambios) return;
    const avisar = (e: BeforeUnloadEvent): void => e.preventDefault();
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [cambios]);

  const mostrado = vista ? borradorDesde(vista) : borrador;

  function pedirDenticion(valor: Denticion): void {
    const { descartadas } = cambiarDenticion(borrador, valor);
    if (descartadas.length > 0) {
      setCambioDenticion({ valor, descartadas });
    } else {
      setBorrador({ ...borrador, denticion: valor });
    }
  }

  async function guardar(): Promise<void> {
    setGuardando(true);
    setError(null);
    try {
      const nuevo = await apiFetch<Odontograma>(`/api/pacientes/${paciente.id}/odontograma`, {
        method: "POST",
        body: JSON.stringify(aPayload(borrador, vigente.version)),
      });
      actualizarHistoria((h) => ({ ...h, odontograma: nuevo }));
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setConflicto(true);
      } else {
        setError(e instanceof ApiError ? e.detail : "No pudimos guardar el odontograma");
      }
      setGuardando(false);
    }
  }

  async function recargar(): Promise<void> {
    setConfirmaRecarga(false);
    try {
      const actual = await apiFetch<Odontograma>(
        `/api/pacientes/${paciente.id}/odontograma/actual`,
      );
      actualizarHistoria((h) => ({ ...h, odontograma: actual }));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "No pudimos recargar el odontograma");
    }
  }

  async function verVersiones(): Promise<void> {
    try {
      setVersiones(await apiFetch<Odontograma[]>(`/api/pacientes/${paciente.id}/odontograma`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "No pudimos cargar las versiones");
    }
  }

  const quien = (o: Odontograma) =>
    `Versión ${o.version} · guardada por ${nombreAutor(o.autor_usuario_id, yo, profesionales)} el ${
      o.created_at ? fechaHora(o.created_at) : ""
    }`;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p role="status" className="text-sm">
          {vista
            ? `Versión ${vista.version} (anterior) · solo lectura`
            : vigente.version === 0
              ? "Sin odontograma registrado todavía"
              : quien(vigente)}
        </p>
        {cambios && !vista && (
          <p role="status" className="text-sm font-medium text-warning">
            Cambios sin guardar
          </p>
        )}
        {vista && (
          <button
            type="button"
            className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-sm font-medium shadow-xs transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-55"
            onClick={() => setVista(null)}
          >
            Volver a la versión vigente
          </button>
        )}
        {puedeEscribirClinica(yo) && !vista && (
          <div className="ml-auto flex items-center gap-2">
            <label className="text-sm font-medium" htmlFor="denticion">
              Dentición
            </label>
            <select
              id="denticion"
              className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-[13px] font-medium shadow-xs transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-55"
              value={borrador.denticion}
              disabled={sinConsentimiento}
              onChange={(e) => pedirDenticion(e.target.value as Denticion)}
            >
              {DENTICIONES.map((d) => (
                <option key={d.valor} value={d.valor}>
                  {d.etiqueta}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {sinConsentimiento && puedeEscribirClinica(yo) && (
        <Aviso tipo="alerta">{TEXTO_SIN_CONSENTIMIENTO}</Aviso>
      )}
      <OdontogramaGrafico
        denticion={mostrado.denticion}
        piezas={mostrado.piezas}
        onAbrir={(pieza, cara) => setPanel({ pieza, cara })}
      />
      <Leyenda />
      {panel && (
        <PanelPieza
          pieza={panel.pieza}
          caraInicial={panel.cara}
          borrador={mostrado}
          soloLectura={bloqueado}
          onCambiar={setBorrador}
          onCerrar={() => setPanel(null)}
        />
      )}
      {conflicto && (
        <Aviso tipo="error">
          {MENSAJE_409}{" "}
          <button
            type="button"
            className="font-medium text-primary hover:underline"
            onClick={() => setConfirmaRecarga(true)}
          >
            Recargar versión vigente
          </button>
        </Aviso>
      )}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {puedeEscribirClinica(yo) && !vista && (
        <button
          type="button"
          className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-[10px] bg-primary px-4 text-sm font-medium text-primary-foreground shadow-xs transition-[background-color,transform] duration-150 hover:bg-primary-hover active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
          disabled={!cambios || guardando || sinConsentimiento}
          onClick={guardar}
        >
          Guardar odontograma
        </button>
      )}
      <table className="w-full max-w-xl text-sm">
        <caption className="mb-1 text-left font-medium">Hallazgos</caption>
        <tbody>
          {hallazgos(mostrado.piezas).map((h) => (
            <tr key={h.texto} className="border-t border-border">
              <td className="py-1">{h.texto}</td>
            </tr>
          ))}
          {hallazgos(mostrado.piezas).length === 0 && (
            <tr>
              <td className="py-1 text-muted">Sin hallazgos marcados</td>
            </tr>
          )}
        </tbody>
      </table>
      <div>
        <button
          type="button"
          className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-sm font-medium shadow-xs transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-55"
          onClick={verVersiones}
        >
          Ver versiones
        </button>
        {versiones && (
          <ul aria-label="Versiones del odontograma" className="mt-2 space-y-1 text-sm">
            {versiones.map((o) => (
              <li key={o.version} className="flex flex-wrap items-center gap-2">
                <span>{quien(o)}</span>
                {o.version !== vigente.version && (
                  <button
                    type="button"
                    className="font-medium text-primary hover:underline"
                    onClick={() => setVista(o)}
                  >
                    Ver versión {o.version}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <DialogoConfirmacion
        abierto={cambioDenticion !== null}
        titulo="Cambiar la dentición"
        confirmar="Cambiar dentición"
        onConfirmar={() => {
          if (cambioDenticion)
            setBorrador(cambiarDenticion(borrador, cambioDenticion.valor).borrador);
          setCambioDenticion(null);
        }}
        onCancelar={() => setCambioDenticion(null)}
      >
        {cambioDenticion?.descartadas.length === 1
          ? `Se quitará la marca de la pieza ${cambioDenticion.descartadas[0]}.`
          : `Se quitarán las marcas de las piezas ${cambioDenticion?.descartadas.join(", ")}.`}
      </DialogoConfirmacion>
      <DialogoConfirmacion
        abierto={confirmaRecarga}
        titulo="Recargar versión vigente"
        confirmar="Descartar y recargar"
        onConfirmar={recargar}
        onCancelar={() => setConfirmaRecarga(false)}
      >
        Se descartarán tus marcas sin guardar y se cargará la versión más nueva.
      </DialogoConfirmacion>
      <DialogoConfirmacion
        abierto={bloqueo.state === "blocked"}
        titulo="Cambios sin guardar"
        confirmar="Descartar y salir"
        cancelar="Seguir editando"
        onConfirmar={() => bloqueo.proceed?.()}
        onCancelar={() => bloqueo.reset?.()}
      >
        Tenés marcas del odontograma sin guardar. Si salís ahora se pierden.
      </DialogoConfirmacion>
    </div>
  );
}

export function Component() {
  const { historia, reintentar } = useContextoPaciente();
  return (
    <section
      aria-labelledby="odonto-titulo"
      className="rounded-[18px] border border-border bg-surface p-5 shadow-xs sm:p-6"
    >
      <h2 id="odonto-titulo" className="mb-4 text-lg font-semibold">
        Odontograma
      </h2>
      {historia.tipo === "ok" ? (
        <Editor key={historia.datos.odontograma.version} vigente={historia.datos.odontograma} />
      ) : historia.tipo === "sin-acceso" || historia.tipo === "sin-consentimiento" ? (
        <EstadoSeccion estado={{ tipo: historia.tipo }} />
      ) : (
        <EstadoSeccion
          estado={{
            tipo: "error",
            mensaje: historia.tipo === "error" ? historia.mensaje : "No pudimos cargar la historia",
            onReintentar: reintentar,
          }}
        />
      )}
    </section>
  );
}
