import { type FormEvent, useState } from "react";

import { ApiError, apiFetch } from "@/shared/api/client";
import { fecha, fechaHora } from "@/shared/formato";
import { Aviso } from "@/shared/ui/Aviso";
import { DialogoConfirmacion } from "@/shared/ui/DialogoConfirmacion";

import type { Paciente, PacientePatch } from "../tipos";
import { useContextoPaciente } from "./contexto";

type Campo =
  | "nombre"
  | "apellido"
  | "dni"
  | "email"
  | "telefono"
  | "obra_social_nombre"
  | "obra_social_plan"
  | "nro_afiliado";

const CAMPOS: { campo: Campo; label: string; obligatorio?: string; tipo?: string }[] = [
  { campo: "nombre", label: "Nombre", obligatorio: "El nombre es obligatorio" },
  { campo: "apellido", label: "Apellido", obligatorio: "El apellido es obligatorio" },
  { campo: "dni", label: "DNI", obligatorio: "El DNI es obligatorio" },
  { campo: "email", label: "Email", tipo: "email" },
  { campo: "telefono", label: "Teléfono", tipo: "tel" },
  { campo: "obra_social_nombre", label: "Obra social" },
  { campo: "obra_social_plan", label: "Plan" },
  { campo: "nro_afiliado", label: "N.º de afiliado" },
];

type Valores = Record<Campo, string>;

function desde(p: Paciente): Valores {
  return Object.fromEntries(CAMPOS.map(({ campo }) => [campo, p[campo] ?? ""])) as Valores;
}

export function DatosPaciente() {
  const { paciente, setPaciente } = useContextoPaciente();
  const [valores, setValores] = useState(() => desde(paciente));
  const [errores, setErrores] = useState<Partial<Record<Campo, string>>>({});
  const [mensaje, setMensaje] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  const original = desde(paciente);
  const tocados = CAMPOS.filter(({ campo }) => valores[campo].trim() !== original[campo]);

  async function patch(cuerpo: PacientePatch): Promise<Paciente> {
    return apiFetch<Paciente>(`/api/pacientes/${paciente.id}`, {
      method: "PATCH",
      body: JSON.stringify(cuerpo),
    });
  }

  async function guardar(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    setMensaje(null);
    const faltantes: Partial<Record<Campo, string>> = {};
    for (const { campo, obligatorio } of tocados) {
      if (obligatorio && valores[campo].trim() === "") {
        faltantes[campo] = obligatorio;
      }
    }
    setErrores(faltantes);
    if (Object.keys(faltantes).length > 0 || tocados.length === 0) {
      return;
    }
    const cuerpo: Record<string, string | null> = {};
    for (const { campo } of tocados) {
      cuerpo[campo] = valores[campo].trim() === "" ? null : valores[campo].trim();
    }
    setEnviando(true);
    try {
      const guardado = await patch(cuerpo as PacientePatch);
      setPaciente(guardado);
      setValores(desde(guardado));
      setMensaje({ tipo: "exito", texto: "Datos guardados" });
    } catch (e) {
      setMensaje({
        tipo: "error",
        texto: e instanceof ApiError ? e.detail : "No pudimos guardar los datos",
      });
    } finally {
      setEnviando(false);
    }
  }

  async function cambiarConsentimiento(): Promise<void> {
    setConfirmando(false);
    try {
      setPaciente(await patch({ consentimiento_datos: !paciente.consentimiento_datos }));
      setMensaje(null);
    } catch (e) {
      setMensaje({
        tipo: "error",
        texto: e instanceof ApiError ? e.detail : "No pudimos registrar el consentimiento",
      });
    }
  }

  const otorgado = paciente.consentimiento_datos;
  return (
    <section aria-labelledby="datos-titulo">
      <h2 id="datos-titulo" className="text-lg font-semibold">
        Datos del paciente
      </h2>
      <form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={guardar} noValidate>
        {CAMPOS.map(({ campo, label, tipo }) => (
          <div key={campo}>
            <label className="block text-sm font-medium" htmlFor={`dato-${campo}`}>
              {label}
            </label>
            <input
              id={`dato-${campo}`}
              type={tipo ?? "text"}
              className="mt-1 w-full rounded-md border border-border px-3 py-2"
              value={valores[campo]}
              aria-invalid={errores[campo] ? true : undefined}
              aria-describedby={errores[campo] ? `dato-${campo}-error` : undefined}
              onChange={(e) => setValores({ ...valores, [campo]: e.target.value })}
            />
            {errores[campo] && (
              <p id={`dato-${campo}-error`} className="mt-1 text-sm text-danger">
                {errores[campo]}
              </p>
            )}
          </div>
        ))}
        <div className="sm:col-span-2">
          <button
            type="submit"
            className="rounded bg-primary px-4 py-2 text-primary-foreground disabled:opacity-60"
            disabled={enviando || tocados.length === 0}
          >
            Guardar datos
          </button>
        </div>
        {mensaje && (
          <Aviso tipo={mensaje.tipo} className="sm:col-span-2">
            {mensaje.texto}
          </Aviso>
        )}
      </form>
      <dl className="mt-4 space-y-1 text-sm">
        <div>
          <dt className="sr-only">Riesgo de ausencia</dt>
          <dd>Riesgo de ausencia: {paciente.riesgo_ausencia} (solo lectura)</dd>
        </div>
        <div>
          <dt className="inline text-muted">Alta: </dt>
          <dd className="inline">{fecha(paciente.created_at)}</dd>
        </div>
        {paciente.consentimiento_datos_at && (
          <div>
            <dt className="inline text-muted">Consentimiento registrado: </dt>
            <dd className="inline">{fechaHora(paciente.consentimiento_datos_at)}</dd>
          </div>
        )}
      </dl>
      <button
        type="button"
        className="mt-3 rounded border border-border px-3 py-1"
        onClick={() => setConfirmando(true)}
      >
        {otorgado ? "Revocar consentimiento" : "Registrar consentimiento"}
      </button>
      <DialogoConfirmacion
        abierto={confirmando}
        titulo={otorgado ? "Revocar consentimiento de datos" : "Registrar consentimiento de datos"}
        confirmar={otorgado ? "Revocar consentimiento" : "Registrar consentimiento"}
        onConfirmar={cambiarConsentimiento}
        onCancelar={() => setConfirmando(false)}
      >
        {otorgado
          ? "Revocar bloquea nuevas cargas de datos de salud; la historia existente se conserva sin borrar nada."
          : "Al registrar el consentimiento se habilita la carga de datos de salud (anamnesis, odontograma, evoluciones y adjuntos) de este paciente."}
      </DialogoConfirmacion>
    </section>
  );
}
