/**
 * Qué botones de estado mostrar (C-07 D8). Espejo de `TRANSICIONES` del backend (C-05b) SOLO
 * para la UI: la API decide (422/403) y su respuesta se muestra tal cual.
 */

import type { Rol } from "@/features/clinica/tipos";

const TRANSICIONES: Record<string, readonly string[]> = {
  reservado: ["confirmado", "cancelado", "asistido", "ausente"],
  confirmado: ["asistido", "ausente", "cancelado"],
};

const DESDE_INICIO = new Set(["asistido", "ausente"]);

export interface Accion {
  estado: string;
  etiqueta: string;
}

const ETIQUETA: Record<string, string> = {
  confirmado: "Confirmar",
  asistido: "Marcar asistido",
  ausente: "Marcar ausente",
  cancelado: "Cancelar turno",
};

export function puedeGestionar(roles: readonly Rol[]): boolean {
  return roles.includes("admin") || roles.includes("recepcionista");
}

/** Acciones visibles para el estado, el rol y si el turno ya empezó. */
export function accionesPermitidas(
  estado: string,
  roles: readonly Rol[],
  yaEmpezo: boolean,
): Accion[] {
  const gestion = puedeGestionar(roles);
  const odontologo = roles.includes("odontologo");
  return (TRANSICIONES[estado] ?? [])
    .filter((destino) => (DESDE_INICIO.has(destino) ? yaEmpezo : true))
    .filter((destino) => gestion || (odontologo && DESDE_INICIO.has(destino)))
    .map((destino) => ({ estado: destino, etiqueta: ETIQUETA[destino] ?? destino }));
}
