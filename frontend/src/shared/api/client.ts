/**
 * Cliente HTTP tipado: inyecta X-Clinica-Id y fomenta Promise.all para cargas paralelas.
 *
 * Contrato auth (C-03, BREAKING): todo endpoint scoped exige
 * `Authorization: Bearer <access>` + `X-Clinica-Id` (cross-chequeado contra
 * el claim `tenant_id` del JWT; mismatch → 403).
 *
 * - El access vive SOLO en memoria (nunca `localStorage`: XSS lo robaría).
 * - El refresh vive SOLO en cookie HttpOnly (`Path=/api/auth`); el browser
 *   la envía sola con `credentials: "include"`. Nunca en JSON ni storage.
 * - Solo lee env VITE_-prefixed vía import.meta.env (regla dura 12): ningún
 *   secreto de backend llega al browser.
 */

/** Access token en memoria (se pierde al recargar: se recupera vía /api/auth/refresh). */
let accessToken: string | null = null;

/** Guarda el access recibido de POST /api/auth/login|refresh (memoria, nunca storage). */
export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/** Devuelve el access en memoria (null si no hay sesión). */
export function getAccessToken(): string | null {
  return accessToken;
}

export const TENANT_HEADER = "X-Clinica-Id";

interface ApiErrorPayload {
  status: number;
  detail: string;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(payload: ApiErrorPayload) {
    super(`API ${payload.status}: ${payload.detail}`);
    this.name = "ApiError";
    this.status = payload.status;
  }
}

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "";
}

export function getClinicaId(): string {
  return import.meta.env.VITE_CLINICA_ID ?? "";
}

function buildUrl(path: string): string {
  const base = getApiBaseUrl().replace(/\/$/, "");
  return `${base}${path}`;
}

/** Fetch tipado contra /api/* con tenant header, Bearer y errores propagados como ApiError. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  headers.set(TENANT_HEADER, getClinicaId());
  const token = getAccessToken();
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  // "include": envía la cookie HttpOnly de refresh en /api/auth/refresh|logout.
  const response = await fetch(buildUrl(path), { ...init, headers, credentials: "include" });
  if (!response.ok) {
    throw new ApiError({ status: response.status, detail: response.statusText });
  }
  return (await response.json()) as T;
}

/** Carga recursos independientes en paralelo (regla dura 13: nunca secuencial). */
export async function fetchAll<T>(paths: string[]): Promise<T[]> {
  return Promise.all(paths.map((path) => apiFetch<T>(path)));
}
