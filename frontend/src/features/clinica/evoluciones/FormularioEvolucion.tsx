import { type FormEvent, useRef, useState } from "react";

import { ApiError } from "@/shared/api/client";
import { Aviso } from "@/shared/ui/Aviso";
import { TEXTO_SIN_CONSENTIMIENTO } from "@/shared/ui/EstadoSeccion";
import { piezasDe } from "../odontograma/fdi";
import { useContextoPaciente } from "../pacientes/contexto";
import type { Evolucion } from "../tipos";
import { crear } from "./api";

const MAX_TEXTO = 10_000;
const MAX_MOTIVO = 500;
const PIEZAS = [...piezasDe("mixta")].sort((a, b) => a - b);

interface Props {
  /** Si se pasa, el formulario corrige esa evolución (DF-11: parte de su texto). */
  original?: Evolucion;
  onCreada: (e: Evolucion) => void;
  onYaCorregida?: () => void;
  onCancelar?: () => void;
}

export function FormularioEvolucion({ original, onCreada, onYaCorregida, onCancelar }: Props) {
  const { paciente } = useContextoPaciente();
  const [texto, setTexto] = useState(original?.texto ?? "");
  const [pieza, setPieza] = useState(original?.pieza_fdi ? String(original.pieza_fdi) : "");
  const [motivo, setMotivo] = useState("");
  const [errores, setErrores] = useState<{ texto?: string; motivo?: string }>({});
  const [falla, setFalla] = useState<string | null>(null);
  const [consentimiento, setConsentimiento] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const enCurso = useRef(false);
  const bloqueado = !paciente.consentimiento_datos || consentimiento;
  const idForm = original ? `corr-${original.id}` : "alta";

  async function enviar(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    if (enCurso.current) return;
    const limpio = texto.trim();
    const errs: { texto?: string; motivo?: string } = {};
    if (limpio === "") errs.texto = "Escribí la evolución";
    if (original && motivo.trim() === "") errs.motivo = "Indicá el motivo de la corrección";
    setErrores(errs);
    setFalla(null);
    if (errs.texto || errs.motivo) return;
    enCurso.current = true;
    setEnviando(true);
    try {
      const nueva = await crear(paciente.id, {
        texto: limpio,
        ...(pieza ? { pieza_fdi: Number(pieza) } : {}),
        ...(original ? { corrige_a_id: original.id, motivo_correccion: motivo.trim() } : {}),
      });
      if (!original) {
        setTexto("");
        setPieza("");
      }
      onCreada(nueva);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && original) {
        onYaCorregida?.();
      } else if (e instanceof ApiError && e.status === 403 && e.detail.includes("consentimiento")) {
        setConsentimiento(true);
      } else {
        setFalla(e instanceof ApiError ? e.detail : "No pudimos guardar la evolución");
      }
    } finally {
      enCurso.current = false;
      setEnviando(false);
    }
  }

  return (
    <form
      aria-label={original ? "Corregir evolución" : "Nueva evolución"}
      className="space-y-3 rounded-md border border-border p-4"
      onSubmit={enviar}
      noValidate
    >
      {bloqueado && <Aviso tipo="alerta">{TEXTO_SIN_CONSENTIMIENTO}</Aviso>}
      <div>
        <label className="block text-sm font-medium" htmlFor={`${idForm}-texto`}>
          Texto de la evolución
        </label>
        <textarea
          id={`${idForm}-texto`}
          rows={4}
          maxLength={MAX_TEXTO}
          className="mt-1 w-full rounded-md border border-border px-3 py-2"
          value={texto}
          disabled={bloqueado}
          aria-invalid={errores.texto ? true : undefined}
          aria-describedby={`${idForm}-contador`}
          onChange={(e) => setTexto(e.target.value)}
        />
        <p id={`${idForm}-contador`} className="text-xs text-muted">
          {texto.length} / {MAX_TEXTO}
        </p>
        {errores.texto && <p className="text-sm text-danger">{errores.texto}</p>}
      </div>
      <div>
        <label className="block text-sm font-medium" htmlFor={`${idForm}-pieza`}>
          Pieza FDI (opcional)
        </label>
        <select
          id={`${idForm}-pieza`}
          className="mt-1 rounded border border-border px-2 py-1"
          value={pieza}
          disabled={bloqueado}
          onChange={(e) => setPieza(e.target.value)}
        >
          <option value="">Sin pieza</option>
          {PIEZAS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </div>
      {original && (
        <div>
          <label className="block text-sm font-medium" htmlFor={`${idForm}-motivo`}>
            Motivo de la corrección
          </label>
          <input
            id={`${idForm}-motivo`}
            maxLength={MAX_MOTIVO}
            className="mt-1 w-full rounded-md border border-border px-3 py-2"
            value={motivo}
            disabled={bloqueado}
            onChange={(e) => setMotivo(e.target.value)}
          />
          {errores.motivo && <p className="text-sm text-danger">{errores.motivo}</p>}
        </div>
      )}
      {falla && <Aviso tipo="error">{falla}</Aviso>}
      <div className="flex gap-2">
        <button
          type="submit"
          className="rounded bg-primary px-4 py-2 text-primary-foreground disabled:opacity-60"
          disabled={enviando || bloqueado}
        >
          {original ? "Guardar corrección" : "Guardar evolución"}
        </button>
        {onCancelar && (
          <button
            type="button"
            className="rounded border border-border px-4 py-2"
            onClick={onCancelar}
          >
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}
