/**
 * Acceso HTTP a evoluciones. La historia clínica es append-only (Ley 26.529):
 * este módulo solo expone lectura (GET) y alta (POST); no hay edición ni borrado.
 */

import { apiFetch } from "@/shared/api/client";

import type { Evolucion, EvolucionIn, Pagina } from "../tipos";

export const LIMITE_EVOLUCIONES = 50;

export function listar(pacienteId: number, afterId?: number): Promise<Pagina<Evolucion>> {
  const params = new URLSearchParams({ limit: String(LIMITE_EVOLUCIONES) });
  if (afterId !== undefined) {
    params.set("after_id", String(afterId));
  }
  return apiFetch(`/api/pacientes/${pacienteId}/evoluciones?${params}`);
}

export function obtener(pacienteId: number, id: number): Promise<Evolucion> {
  return apiFetch(`/api/pacientes/${pacienteId}/evoluciones/${id}`);
}

export function crear(pacienteId: number, cuerpo: EvolucionIn): Promise<Evolucion> {
  return apiFetch(`/api/pacientes/${pacienteId}/evoluciones`, {
    method: "POST",
    body: JSON.stringify(cuerpo),
  });
}
