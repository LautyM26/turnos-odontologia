import { Download, FileText, Image as ImageIcon } from "lucide-react";
import { type FormEvent, useRef, useState } from "react";
import { useLoaderData, useRevalidator } from "react-router";

import { requireSession } from "@/features/auth/session";
import { ApiError, apiFetch, apiFetchBlob } from "@/shared/api/client";
import { cargarSeguro, type Resultado } from "@/shared/api/resultado";
import { fechaHora, nombreAutor, tamano } from "@/shared/formato";
import { Aviso } from "@/shared/ui/Aviso";
import { EstadoSeccion, TEXTO_SIN_CONSENTIMIENTO } from "@/shared/ui/EstadoSeccion";
import { useEstadoDesde } from "@/shared/useEstadoDesde";

import { useContextoPaciente } from "../pacientes/contexto";
import { puedeEscribirClinica } from "../permisos";
import type { Adjunto } from "../tipos";
import { MENSAJE_TAMANO, validarArchivo } from "./validar";

export async function loader({
  params,
  request,
}: {
  params: { pacienteId?: string };
  request: Request;
}): Promise<Resultado<Adjunto[]>> {
  await requireSession(new URL(request.url));
  return cargarSeguro(apiFetch<Adjunto[]>(`/api/pacientes/${params.pacienteId}/adjuntos`));
}

const ACEPTADOS = "JPG, PNG o PDF";

function mensajeDeSubida(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 415) return "El contenido del archivo no es una foto ni un PDF válido";
    if (e.status === 413) return MENSAJE_TAMANO;
    if (e.status === 422) return "El archivo está vacío o no es válido";
    return e.detail;
  }
  return "No pudimos subir el archivo";
}

async function descargar(pacienteId: number, adjunto: Adjunto): Promise<void> {
  const blob = await apiFetchBlob(`/api/pacientes/${pacienteId}/adjuntos/${adjunto.id}/contenido`);
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = `adjunto-${adjunto.id}.${adjunto.tipo === "pdf" ? "pdf" : adjunto.mime === "image/png" ? "png" : "jpg"}`;
  enlace.click();
  URL.revokeObjectURL(url);
}

function Lista({ inicial }: { inicial: Adjunto[] }) {
  const { paciente, profesionales, yo } = useContextoPaciente();
  const [adjuntos, setAdjuntos] = useState(inicial);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);
  const [sinConsentimiento, setSinConsentimiento] = useState(false);
  const entrada = useRef<HTMLInputElement>(null);
  const bloqueado = !paciente.consentimiento_datos || sinConsentimiento;

  async function subir(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    if (archivo === null) {
      setMensaje({ tipo: "error", texto: "Elegí un archivo" });
      return;
    }
    const motivo = validarArchivo(archivo);
    if (motivo !== null) {
      setMensaje({ tipo: "error", texto: motivo });
      return;
    }
    setSubiendo(true);
    setMensaje(null);
    try {
      const datos = new FormData();
      datos.append("file", archivo);
      const nuevo = await apiFetch<Adjunto>(`/api/pacientes/${paciente.id}/adjuntos`, {
        method: "POST",
        body: datos,
      });
      setAdjuntos([nuevo, ...adjuntos]);
      setArchivo(null);
      if (entrada.current) entrada.current.value = "";
      setMensaje({ tipo: "exito", texto: "Adjunto subido" });
    } catch (e) {
      if (e instanceof ApiError && e.status === 403 && e.detail.includes("consentimiento")) {
        setSinConsentimiento(true);
      } else {
        setMensaje({ tipo: "error", texto: mensajeDeSubida(e) });
      }
    } finally {
      setSubiendo(false);
    }
  }

  async function bajar(adjunto: Adjunto): Promise<void> {
    try {
      await descargar(paciente.id, adjunto);
    } catch (e) {
      setMensaje({
        tipo: "error",
        texto: e instanceof ApiError ? e.detail : "No pudimos descargar",
      });
    }
  }

  return (
    <div className="space-y-4">
      {puedeEscribirClinica(yo) && (
        <form
          className="space-y-3 rounded-[14px] border border-dashed border-border-strong bg-surface-2/60 p-4"
          onSubmit={subir}
          noValidate
        >
          {bloqueado && <Aviso tipo="alerta">{TEXTO_SIN_CONSENTIMIENTO}</Aviso>}
          <label className="block text-[13px] font-medium" htmlFor="adjunto-archivo">
            Archivo
          </label>
          <input
            ref={entrada}
            id="adjunto-archivo"
            type="file"
            accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
            disabled={bloqueado}
            className="block w-full cursor-pointer text-sm text-muted file:mr-3 file:h-9 file:cursor-pointer file:rounded-lg file:border file:border-border file:bg-surface file:px-3 file:text-sm file:font-medium file:text-foreground file:shadow-xs hover:file:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60"
            onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
          />
          <p className="text-xs text-muted">Se aceptan {ACEPTADOS}, hasta 10 MB.</p>
          <button
            type="submit"
            className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-[10px] bg-primary px-4 text-sm font-medium text-primary-foreground shadow-xs transition-[background-color,transform] duration-150 hover:bg-primary-hover active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
            disabled={subiendo || bloqueado}
          >
            {subiendo ? "Subiendo…" : "Subir adjunto"}
          </button>
        </form>
      )}
      {mensaje && <Aviso tipo={mensaje.tipo}>{mensaje.texto}</Aviso>}
      {adjuntos.length === 0 ? (
        <p className="text-muted">Todavía no hay adjuntos. Se aceptan {ACEPTADOS}.</p>
      ) : (
        <ul aria-label="Adjuntos del paciente" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {adjuntos.map((a) => (
            <li
              key={a.id}
              className="flex items-start gap-3 rounded-[14px] border border-border bg-surface p-4 text-sm shadow-xs"
            >
              <span
                aria-hidden
                className="grid size-10 shrink-0 place-items-center rounded-[10px] bg-primary-soft text-primary"
              >
                {a.tipo === "pdf" ? (
                  <FileText className="size-5" />
                ) : (
                  <ImageIcon className="size-5" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {a.tipo === "pdf" ? "PDF" : "Foto"}{" "}
                  <span className="font-normal text-muted">· {tamano(a.tamano_bytes)}</span>
                </p>
                <p className="truncate text-muted">
                  {nombreAutor(a.subido_por, yo, profesionales)}
                </p>
                <p className="text-muted">{fechaHora(a.created_at)}</p>
              </div>
              <button
                type="button"
                className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg px-2 font-medium text-primary transition-colors hover:bg-primary-soft"
                aria-label={`Descargar adjunto ${a.id}`}
                onClick={() => bajar(a)}
              >
                <Download aria-hidden className="size-4" />
                Descargar
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Component() {
  const datos = useLoaderData() as Resultado<Adjunto[]>;
  const revalidator = useRevalidator();
  const [resultado] = useEstadoDesde(datos);
  return (
    <section
      aria-labelledby="adj-titulo"
      className="rounded-[18px] border border-border bg-surface p-5 shadow-xs sm:p-6"
    >
      <h2 id="adj-titulo" className="mb-4 text-lg font-semibold">
        Adjuntos
      </h2>
      {resultado.tipo === "ok" ? (
        <Lista inicial={resultado.datos} />
      ) : resultado.tipo === "sin-acceso" || resultado.tipo === "sin-consentimiento" ? (
        <EstadoSeccion estado={{ tipo: resultado.tipo }} />
      ) : (
        <EstadoSeccion
          estado={{
            tipo: "error",
            mensaje:
              resultado.tipo === "error" ? resultado.mensaje : "No pudimos cargar los adjuntos",
            onReintentar: () => void revalidator.revalidate(),
          }}
        />
      )}
    </section>
  );
}
