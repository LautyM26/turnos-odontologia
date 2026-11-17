/** Render de la app completa con router en memoria y fetch simulado. */

import { render } from "@testing-library/react";
import { RouterProvider } from "react-router";

import { limpiarSesion } from "@/features/auth/session";
import type { Me } from "@/features/clinica/tipos";
import { crearRouter } from "@/router";

import { type ApiMock, mockApi, type Respuesta } from "./api";
import { historia, meOdontologo, paciente, profesionales } from "./fixtures";

/** Mocks mínimos para abrir /pacientes/7 (paciente, historia vacía, profesionales). */
export function tablaPaciente(
  extra: Record<string, Respuesta> = {},
  me: Me = meOdontologo,
): Record<string, Respuesta> {
  return {
    ...conSesion(me),
    "GET /api/pacientes/7": { json: paciente() },
    "GET /api/pacientes/7/historia": { json: historia() },
    "GET /api/catalogo/profesionales": { json: { items: profesionales, next_cursor: null } },
    ...extra,
  };
}

/** Tabla de mocks: con refresh válido el usuario "tiene sesión" (cookie vigente). */
export function conSesion(me: Me): Record<string, Respuesta> {
  return {
    "POST /api/auth/refresh": { json: { access_token: "tok", expires_in: 900 } },
    "GET /api/auth/me": { json: me },
    "POST /api/auth/logout": { status: 200, json: { ok: true } },
  };
}

export const sinSesion: Record<string, Respuesta> = {
  "POST /api/auth/refresh": { status: 401, json: { detail: "Sesión inválida" } },
};

export function renderApp(
  ruta: string,
  tabla: Record<string, Respuesta>,
): { api: ApiMock; router: ReturnType<typeof crearRouter> } {
  limpiarSesion();
  const api = mockApi(tabla);
  const router = crearRouter([ruta]);
  render(<RouterProvider router={router} />);
  return { api, router };
}
