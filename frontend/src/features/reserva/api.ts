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

async function publico<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers();
  if (typeof init?.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(buildUrl(path), { ...init, headers, credentials: "omit" });
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
