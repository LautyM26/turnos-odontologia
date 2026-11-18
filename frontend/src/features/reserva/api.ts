/**
 * API pública de reserva online (C-06 D6): fetch SIN credenciales, sin `Authorization` ni
 * `X-Clinica-Id`, aunque el staff tenga sesión abierta. El tenant sale del slug o del token.
 */

import { buildUrl, leerError } from "@/shared/api/client";

export interface PrestacionPublica {
  id: number;
  nombre: string;
  duracion_min: number;
}

export interface ProfesionalPublico {
  id: number;
  nombre: string;
  especialidad: string | null;
}

export interface CatalogoPublico {
  clinica: string;
  zona_horaria: string;
  prestaciones: PrestacionPublica[];
  profesionales: ProfesionalPublico[];
}

export interface HuecoPublico {
  inicio: string;
  fin: string;
}

export interface ReservaPublica {
  clinica: string;
  zona_horaria: string;
  profesional: string;
  prestacion: string;
  inicio: string;
  fin: string;
  estado: string;
  cancelable: boolean;
}

export interface ReservaCreada extends ReservaPublica {
  token: string;
}

export interface DatosReserva {
  profesional_id: number;
  prestacion_id: number;
  inicio: string;
  dni: string;
  nombre: string;
  apellido: string;
  email?: string;
  telefono?: string;
  acepta_privacidad: true;
}

function pedir(path: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers();
  if (typeof init?.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  return fetch(buildUrl(path), { ...init, headers, credentials: "omit" });
}

async function publico<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await pedir(path, init);
  if (!response.ok) {
    throw await leerError(response);
  }
  return (await response.json()) as T;
}

const enc = encodeURIComponent;

export function obtenerCatalogo(slug: string): Promise<CatalogoPublico> {
  return publico(`/api/public/clinicas/${enc(slug)}`);
}

export function obtenerHuecos(
  slug: string,
  profesionalId: number,
  prestacionId: number,
  desde: Date,
  hasta: Date,
): Promise<HuecoPublico[]> {
  const q = new URLSearchParams({
    profesional_id: String(profesionalId),
    prestacion_id: String(prestacionId),
    desde: desde.toISOString(),
    hasta: hasta.toISOString(),
  });
  return publico(`/api/public/clinicas/${enc(slug)}/huecos?${q.toString()}`);
}

export function crearReserva(slug: string, datos: DatosReserva): Promise<ReservaCreada> {
  return publico(`/api/public/clinicas/${enc(slug)}/reservas`, {
    method: "POST",
    body: JSON.stringify(datos),
  });
}

export function obtenerReserva(token: string): Promise<ReservaPublica> {
  return publico(`/api/public/reservas/${enc(token)}`);
}

export function cancelarReserva(token: string): Promise<ReservaPublica> {
  return publico(`/api/public/reservas/${enc(token)}/cancelar`, { method: "POST" });
}

/** 409 de la reprogramación (C-17): el horario se ocupó; trae otras opciones para elegir. */
export class HorarioOcupado extends Error {
  readonly alternativas: HuecoPublico[];

  constructor(alternativas: HuecoPublico[]) {
    super("Horario ocupado");
    this.name = "HorarioOcupado";
    this.alternativas = alternativas;
  }
}

export function opcionesReprogramacion(token: string): Promise<HuecoPublico[]> {
  return publico(`/api/public/reservas/${enc(token)}/opciones`);
}

export async function reprogramar(token: string, inicio: string): Promise<ReservaPublica> {
  const response = await pedir(`/api/public/reservas/${enc(token)}/reprogramar`, {
    method: "POST",
    body: JSON.stringify({ inicio }),
  });
  if (response.status === 409) {
    const cuerpo = (await response.json().catch(() => ({}))) as { alternativas?: HuecoPublico[] };
    throw new HorarioOcupado(cuerpo.alternativas ?? []);
  }
  if (!response.ok) {
    throw await leerError(response);
  }
  return (await response.json()) as ReservaPublica;
}
