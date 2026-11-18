/**
 * Contrato HTTP de la agenda (C-07). Fuente: backend/app/domain/agenda/schemas.py.
 * Todo pasa por `apiFetch` (Bearer + X-Clinica-Id + refresh único).
 */

import type { Paciente, Pagina } from "@/features/clinica/tipos";
import { apiFetch } from "@/shared/api/client";

export interface AgendaTurno {
  id: number;
  profesional_id: number;
  sillon_id: number;
  paciente_id: number;
  paciente_nombre: string;
  prestacion_id: number;
  prestacion_nombre: string;
  inicio: string;
  fin: string;
  estado: string;
  origen: string;
  es_sobreturno: boolean;
  motivo_sobreturno: string | null;
}

export interface AgendaBloqueo {
  id: number;
  alcance: "clinica" | "profesional" | "sillon";
  profesional_id: number | null;
  sillon_id: number | null;
  inicio: string;
  fin: string;
  motivo: string;
}

export interface ProfesionalAgenda {
  id: number;
  nombre: string;
  especialidad?: string | null;
  usuario_id: number | null;
  agenda_activa: boolean;
}

export interface SillonAgenda {
  id: number;
  nombre: string;
  tipo: string;
}

export interface PrestacionAgenda {
  id: number;
  nombre: string;
  duracion_min: number;
}

export interface Franja {
  dia_semana: number;
  inicio: string;
  fin: string;
}

export interface Horario {
  profesional_id: number;
  zona_horaria: string;
  franjas: Franja[];
}

export interface Hueco {
  inicio: string;
  fin: string;
  sillon_ids: number[];
}

export interface Catalogo {
  profesionales: ProfesionalAgenda[];
  sillones: SillonAgenda[];
  prestaciones: PrestacionAgenda[];
}

export interface NuevoTurno {
  profesional_id: number;
  sillon_id: number;
  paciente_id: number;
  prestacion_id: number;
  inicio: string;
  sobreturno?: boolean;
  motivo_sobreturno?: string;
}

export interface NuevoPaciente {
  nombre: string;
  apellido: string;
  dni: string;
  email?: string;
  telefono?: string;
}

function q(params: Record<string, string | number | null | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") {
      usp.set(k, String(v));
    }
  }
  return usp.toString();
}

export async function cargarCatalogo(signal?: AbortSignal): Promise<Catalogo> {
  const init = signal ? { signal } : undefined;
  const [profesionales, sillones, prestaciones] = await Promise.all([
    apiFetch<Pagina<ProfesionalAgenda>>("/api/catalogo/profesionales?limit=200", init),
    apiFetch<Pagina<SillonAgenda>>("/api/catalogo/sillones?limit=200", init),
    apiFetch<Pagina<PrestacionAgenda>>("/api/catalogo/prestaciones?limit=200", init),
  ]);
  return {
    profesionales: profesionales.items,
    sillones: sillones.items,
    prestaciones: prestaciones.items,
  };
}

export function listarTurnos(
  desde: Date,
  hasta: Date,
  profesionalId: number | null,
  signal?: AbortSignal,
): Promise<AgendaTurno[]> {
  const params = q({
    desde: desde.toISOString(),
    hasta: hasta.toISOString(),
    profesional_id: profesionalId,
  });
  return apiFetch(`/api/agenda/turnos?${params}`, signal ? { signal } : undefined);
}

export function listarBloqueos(
  desde: Date,
  hasta: Date,
  profesionalId: number | null,
  signal?: AbortSignal,
): Promise<AgendaBloqueo[]> {
  const params = q({
    desde: desde.toISOString(),
    hasta: hasta.toISOString(),
    profesional_id: profesionalId,
  });
  return apiFetch(`/api/agenda/bloqueos?${params}`, signal ? { signal } : undefined);
}

export function obtenerHorario(profesionalId: number, signal?: AbortSignal): Promise<Horario> {
  return apiFetch(
    `/api/catalogo/profesionales/${profesionalId}/horario`,
    signal ? { signal } : undefined,
  );
}

export function buscarHuecos(
  profesionalId: number,
  prestacionId: number,
  desde: Date,
  hasta: Date,
): Promise<Hueco[]> {
  const params = q({
    profesional_id: profesionalId,
    prestacion_id: prestacionId,
    desde: desde.toISOString(),
    hasta: hasta.toISOString(),
  });
  return apiFetch(`/api/agenda/huecos?${params}`);
}

export async function buscarPacientes(texto: string): Promise<Paciente[]> {
  const limpio = texto.trim();
  const esDni = /^[\d.\s-]+$/.test(limpio);
  const params = esDni
    ? q({ dni: limpio.replace(/\D/g, ""), limit: 8 })
    : q({ q: limpio, limit: 8 });
  const pagina = await apiFetch<Pagina<Paciente>>(`/api/pacientes?${params}`);
  return pagina.items;
}

export function crearPaciente(datos: NuevoPaciente): Promise<Paciente> {
  return apiFetch("/api/pacientes", { method: "POST", body: JSON.stringify(datos) });
}

export function crearTurno(datos: NuevoTurno): Promise<{ id: number }> {
  return apiFetch("/api/turnos", { method: "POST", body: JSON.stringify(datos) });
}

export function transicionar(turnoId: number, estado: string, motivo?: string): Promise<unknown> {
  return apiFetch(`/api/turnos/${turnoId}/transicion`, {
    method: "POST",
    body: JSON.stringify(motivo ? { estado, motivo } : { estado }),
  });
}
