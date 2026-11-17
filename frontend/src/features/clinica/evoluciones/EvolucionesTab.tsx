import { useState } from "react";

import { ApiError } from "@/shared/api/client";
import { fechaHora, nombreProfesional } from "@/shared/formato";
import { Aviso } from "@/shared/ui/Aviso";
import { EstadoSeccion } from "@/shared/ui/EstadoSeccion";

import { useContextoPaciente } from "../pacientes/contexto";
import { puedeCorregir, puedeEscribirClinica } from "../permisos";
import type { Evolucion, Historia } from "../tipos";
import { listar } from "./api";
import { FormularioEvolucion } from "./FormularioEvolucion";

function irA(id: number): void {
  const destino = document.getElementById(`evolucion-${id}`);
  destino?.scrollIntoView({ block: "center" });
  destino?.focus();
}

function Timeline({ historia }: { historia: Historia }) {
  const { paciente, actualizarHistoria, profesionales, yo } = useContextoPaciente();
  const [corrigiendo, setCorrigiendo] = useState<number | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [falla, setFalla] = useState<string | null>(null);
  const evoluciones = [...historia.evoluciones].sort((a, b) => b.id - a.id);
  const porId = new Map(historia.evoluciones.map((e) => [e.id, e]));

  function agregar(nueva: Evolucion): void {
    actualizarHistoria((h) => ({
      ...h,
      evoluciones: [
        nueva,
        ...h.evoluciones.map((e) =>
          e.id === nueva.corrige_a_id ? { ...e, corregida_por_id: nueva.id } : e,
        ),
      ],
    }));
    setCorrigiendo(null);
  }

  async function cargarAnteriores(): Promise<void> {
    setFalla(null);
    try {
      const pagina = await listar(paciente.id, historia.next_cursor ?? undefined);
      actualizarHistoria((h) => {
        const ya = new Set(h.evoluciones.map((e) => e.id));
        return {
          ...h,
          evoluciones: [...h.evoluciones, ...pagina.items.filter((e) => !ya.has(e.id))],
          next_cursor: pagina.next_cursor,
        };
      });
    } catch (e) {
      setFalla(e instanceof ApiError ? e.detail : "No pudimos cargar las evoluciones anteriores");
    }
  }

  async function yaCorregida(): Promise<void> {
    setCorrigiendo(null);
    setAviso(
      "Esa evolución ya fue corregida por otra corrección. Actualizamos la lista: corregí la versión vigente.",
    );
    try {
      const pagina = await listar(paciente.id);
      actualizarHistoria((h) => ({
        ...h,
        evoluciones: pagina.items,
        next_cursor: pagina.next_cursor,
      }));
    } catch {
      setFalla("No pudimos actualizar la lista");
    }
  }

  return (
    <div className="space-y-4">
      {puedeEscribirClinica(yo) && <FormularioEvolucion onCreada={agregar} />}
      {aviso && <Aviso tipo="alerta">{aviso}</Aviso>}
      {evoluciones.length === 0 ? (
        <p className="text-muted">Todavía no hay evoluciones registradas</p>
      ) : (
        <ol className="space-y-3">
          {evoluciones.map((e) => {
            const original = e.corrige_a_id === null ? undefined : porId.get(e.corrige_a_id);
            return (
              <li key={e.id}>
                <article
                  id={`evolucion-${e.id}`}
                  tabIndex={-1}
                  className={`rounded-md border border-border p-3 ${e.corregida_por_id === null ? "" : "opacity-70"}`}
                >
                  <p className="text-sm text-muted">
                    {fechaHora(e.fecha_hora)} · {nombreProfesional(e.profesional_id, profesionales)}
                    {e.pieza_fdi !== null && ` · Pieza ${e.pieza_fdi}`}
                    {e.corregida_por_id !== null && (
                      <span className="ml-2 rounded bg-surface px-2 py-0.5 font-medium">
                        Corregida
                      </span>
                    )}
                  </p>
                  {e.corrige_a_id !== null && (
                    <p className="mt-1 text-sm">
                      <button
                        type="button"
                        className="underline"
                        onClick={() => irA(e.corrige_a_id as number)}
                      >
                        Corrige a la evolución del{" "}
                        {original ? fechaHora(original.fecha_hora) : `#${e.corrige_a_id}`}
                      </button>
                      {e.motivo_correccion && <> · Motivo: {e.motivo_correccion}</>}
                    </p>
                  )}
                  <p className="mt-2 whitespace-pre-wrap break-words">{e.texto}</p>
                  <div className="mt-2 flex gap-3 text-sm">
                    {e.corregida_por_id !== null && (
                      <button
                        type="button"
                        className="underline"
                        onClick={() => irA(e.corregida_por_id as number)}
                      >
                        Ver corrección
                      </button>
                    )}
                    {puedeCorregir(e, yo) && corrigiendo !== e.id && (
                      <button
                        type="button"
                        className="underline"
                        onClick={() => setCorrigiendo(e.id)}
                      >
                        Corregir
                      </button>
                    )}
                  </div>
                  {corrigiendo === e.id && (
                    <div className="mt-3">
                      <FormularioEvolucion
                        original={e}
                        onCreada={agregar}
                        onYaCorregida={yaCorregida}
                        onCancelar={() => setCorrigiendo(null)}
                      />
                    </div>
                  )}
                </article>
              </li>
            );
          })}
        </ol>
      )}
      {falla && <Aviso tipo="error">{falla}</Aviso>}
      {historia.next_cursor !== null && (
        <button
          type="button"
          className="rounded border border-border px-3 py-1"
          onClick={cargarAnteriores}
        >
          Cargar anteriores
        </button>
      )}
    </div>
  );
}

export function Component() {
  const { historia, reintentar } = useContextoPaciente();
  return (
    <section aria-labelledby="evo-titulo">
      <h2 id="evo-titulo" className="mb-3 text-lg font-semibold">
        Evoluciones
      </h2>
      {historia.tipo === "ok" ? (
        <Timeline historia={historia.datos} />
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
