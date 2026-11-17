/** Resultado por sección: un 403 o un 500 de una parte no tira abajo toda la pantalla. */

import { ApiError } from "./client";

/** Texto exacto del backend (backend/app/api/pacientes.py); hay un test que los compara. */
export const CONSENTIMIENTO_FALTANTE = "Falta el consentimiento de datos del paciente";

export type Fallo =
  | { tipo: "sin-acceso" }
  | { tipo: "sin-consentimiento" }
  | { tipo: "no-encontrado" }
  | { tipo: "error"; mensaje: string };

export type Resultado<T> = { tipo: "ok"; datos: T } | Fallo;

export function clasificarError(error: unknown): Fallo {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return error.detail === CONSENTIMIENTO_FALTANTE
        ? { tipo: "sin-consentimiento" }
        : { tipo: "sin-acceso" };
    }
    if (error.status === 404) {
      return { tipo: "no-encontrado" };
    }
    return { tipo: "error", mensaje: error.detail };
  }
  return { tipo: "error", mensaje: "No pudimos conectar con el servidor" };
}

export async function cargarSeguro<T>(promesa: Promise<T>): Promise<Resultado<T>> {
  try {
    return { tipo: "ok", datos: await promesa };
  } catch (e) {
    return clasificarError(e);
  }
}
