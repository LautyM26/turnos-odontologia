/** Formato de fechas (America/Argentina/Buenos_Aires, DF-15), tamaños y autores (DF-14). */

import type { Me, Profesional } from "@/features/clinica/tipos";

const ZONA = "America/Argentina/Buenos_Aires";

const FECHA_HORA = new Intl.DateTimeFormat("es-AR", {
  timeZone: ZONA,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const FECHA = new Intl.DateTimeFormat("es-AR", {
  timeZone: ZONA,
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function fechaHora(iso: string): string {
  return FECHA_HORA.format(new Date(iso));
}

export function fecha(iso: string): string {
  return FECHA.format(new Date(iso));
}

export function tamano(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const unidad =
    bytes < 1024 * 1024 ? { div: 1024, sufijo: "KB" } : { div: 1024 * 1024, sufijo: "MB" };
  return `${(bytes / unidad.div).toLocaleString("es-AR", { maximumFractionDigits: 1 })} ${unidad.sufijo}`;
}

export function nombreProfesional(id: number, profesionales: Profesional[]): string {
  return profesionales.find((p) => p.id === id)?.nombre ?? `Profesional #${id}`;
}

/** Autor a partir de un `usuario_id`: "Vos", el profesional vinculado o "Usuario #id". */
export function nombreAutor(
  usuarioId: number | null,
  yo: Me | null,
  profesionales: Profesional[],
): string {
  if (usuarioId === null) {
    return "—";
  }
  if (yo?.sub === usuarioId) {
    return "Vos";
  }
  return profesionales.find((p) => p.usuario_id === usuarioId)?.nombre ?? `Usuario #${usuarioId}`;
}
