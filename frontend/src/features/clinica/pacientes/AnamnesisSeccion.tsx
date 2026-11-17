import { useState } from "react";

import { ApiError, apiFetch } from "@/shared/api/client";
import { fechaHora, nombreAutor } from "@/shared/formato";
import { Aviso } from "@/shared/ui/Aviso";
import { EstadoSeccion, TEXTO_SIN_CONSENTIMIENTO } from "@/shared/ui/EstadoSeccion";

import { puedeEscribirClinica } from "../permisos";
import type { Ficha } from "../tipos";
import { useContextoPaciente } from "./contexto";

const CAMPOS = [
  ["anamnesis", "Anamnesis"],
  ["alergias", "Alergias"],
  ["antecedentes", "Antecedentes"],
] as const;

type Valores = Record<(typeof CAMPOS)[number][0], string>;

const desde = (f: Ficha): Valores => ({
  anamnesis: f.anamnesis ?? "",
  alergias: f.alergias ?? "",
  antecedentes: f.antecedentes ?? "",
});

type Mensaje = { tipo: "exito" | "error" | "conflicto" | "consentimiento"; texto: string };

function Editor({ ficha }: { ficha: Ficha }) {
  const { paciente, actualizarHistoria, profesionales, yo } = useContextoPaciente();
  const puedeEscribir = puedeEscribirClinica(yo);
  const [valores, setValores] = useState(() => desde(ficha));
  const [mensaje, setMensaje] = useState<Mensaje | null>(null);
  const [enviando, setEnviando] = useState(false);
  const sinConsentimiento = !paciente.consentimiento_datos || mensaje?.tipo === "consentimiento";

  function aplicar(nueva: Ficha): void {
    actualizarHistoria((h) => ({ ...h, ficha: nueva }));
    setValores(desde(nueva));
  }

  async function guardar(): Promise<void> {
    setEnviando(true);
    setMensaje(null);
    try {
      const nueva = await apiFetch<Ficha>(`/api/pacientes/${paciente.id}/ficha`, {
        method: "PUT",
        body: JSON.stringify({
          version_esperada: ficha.version,
          anamnesis: valores.anamnesis || null,
          alergias: valores.alergias || null,
          antecedentes: valores.antecedentes || null,
        }),
      });
      aplicar(nueva);
      setMensaje({ tipo: "exito", texto: `Ficha guardada: versión ${nueva.version}` });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setMensaje({ tipo: "conflicto", texto: "La ficha cambió mientras la editabas" });
      } else if (e instanceof ApiError && e.status === 403 && e.detail.includes("consentimiento")) {
        setMensaje({ tipo: "consentimiento", texto: TEXTO_SIN_CONSENTIMIENTO });
      } else {
        setMensaje({
          tipo: "error",
          texto: e instanceof ApiError ? e.detail : "No pudimos guardar",
        });
      }
    } finally {
      setEnviando(false);
    }
  }

  async function recargar(): Promise<void> {
    try {
      aplicar(await apiFetch<Ficha>(`/api/pacientes/${paciente.id}/ficha`));
      setMensaje(null);
    } catch (e) {
      setMensaje({
        tipo: "error",
        texto: e instanceof ApiError ? e.detail : "No pudimos recargar",
      });
    }
  }

  if (ficha.version === 0 && !puedeEscribir) {
    return <p className="text-muted">Sin anamnesis registrada</p>;
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        {ficha.version === 0
          ? "Sin versiones todavía"
          : `Versión ${ficha.version} · ${nombreAutor(ficha.autor_usuario_id, yo, profesionales)} · ${
              ficha.created_at ? fechaHora(ficha.created_at) : ""
            }`}
      </p>
      {sinConsentimiento && puedeEscribir && (
        <Aviso tipo="alerta">{TEXTO_SIN_CONSENTIMIENTO}</Aviso>
      )}
      {CAMPOS.map(([campo, label]) => (
        <div key={campo}>
          <label className="block text-sm font-medium" htmlFor={`ficha-${campo}`}>
            {label}
          </label>
          <textarea
            id={`ficha-${campo}`}
            rows={3}
            maxLength={10000}
            className="mt-1 w-full rounded-md border border-border px-3 py-2 disabled:bg-surface"
            value={valores[campo]}
            readOnly={!puedeEscribir}
            disabled={puedeEscribir && sinConsentimiento}
            onChange={(e) => setValores({ ...valores, [campo]: e.target.value })}
          />
        </div>
      ))}
      {mensaje?.tipo === "conflicto" && (
        <Aviso tipo="error">
          {mensaje.texto}{" "}
          <button type="button" className="underline" onClick={recargar}>
            Recargar versión vigente
          </button>
        </Aviso>
      )}
      {(mensaje?.tipo === "exito" || mensaje?.tipo === "error") && (
        <Aviso tipo={mensaje.tipo}>{mensaje.texto}</Aviso>
      )}
      {puedeEscribir && (
        <button
          type="button"
          className="rounded bg-primary px-4 py-2 text-primary-foreground disabled:opacity-60"
          disabled={enviando || sinConsentimiento}
          onClick={guardar}
        >
          Guardar ficha
        </button>
      )}
    </div>
  );
}

function Versiones() {
  const { paciente, profesionales, yo } = useContextoPaciente();
  const [versiones, setVersiones] = useState<Ficha[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function cargar(): Promise<void> {
    setError(null);
    try {
      setVersiones(await apiFetch<Ficha[]>(`/api/pacientes/${paciente.id}/ficha/versiones`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "No pudimos cargar las versiones");
    }
  }

  return (
    <div className="mt-4">
      <button type="button" className="rounded border border-border px-3 py-1" onClick={cargar}>
        Ver versiones anteriores
      </button>
      {error && (
        <Aviso tipo="error" className="mt-2">
          {error}
        </Aviso>
      )}
      {versiones && (
        <ul aria-label="Versiones de la ficha" className="mt-2 space-y-2">
          {versiones.map((v) => (
            <li key={v.version} className="rounded border border-border p-3 text-sm">
              <p className="font-medium">
                Versión {v.version} · {nombreAutor(v.autor_usuario_id, yo, profesionales)} ·{" "}
                {v.created_at ? fechaHora(v.created_at) : ""}
              </p>
              <p>Anamnesis: {v.anamnesis ?? "—"}</p>
              <p>Alergias: {v.alergias ?? "—"}</p>
              <p>Antecedentes: {v.antecedentes ?? "—"}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AnamnesisSeccion() {
  const { historia, reintentar } = useContextoPaciente();
  return (
    <section aria-labelledby="anamnesis-titulo" className="mt-8">
      <h2 id="anamnesis-titulo" className="text-lg font-semibold">
        Anamnesis
      </h2>
      <div className="mt-3">
        {historia.tipo === "ok" ? (
          <>
            <Editor key={historia.datos.ficha.version} ficha={historia.datos.ficha} />
            {historia.datos.ficha.version > 0 && <Versiones />}
          </>
        ) : historia.tipo === "sin-acceso" || historia.tipo === "sin-consentimiento" ? (
          <EstadoSeccion estado={{ tipo: historia.tipo }} />
        ) : (
          <EstadoSeccion
            estado={{
              tipo: "error",
              mensaje:
                historia.tipo === "error" ? historia.mensaje : "No pudimos cargar la historia",
              onReintentar: reintentar,
            }}
          />
        )}
      </div>
    </section>
  );
}
