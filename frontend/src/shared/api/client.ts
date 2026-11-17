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

/** tenant_id de la sesión autenticada (lo fija features/auth/session.ts). */
let tenantSesion: number | null = null;

export function setTenantSesion(tenantId: number | null): void {
  tenantSesion = tenantId;
}

let alExpirarSesion: (() => void) | null = null;

/** Registra el callback que navega a /login cuando el refresh falla. */
export function onSesionExpirada(callback: (() => void) | null): void {
  alExpirarSesion = callback;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  /** Mensajes por campo (`loc` de la validación 422 de FastAPI). */
  readonly campos: Record<string, string> | undefined;

  constructor(status: number, detail: string, campos?: Record<string, string>) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.campos = campos;
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

interface ErrorValidacion {
  loc?: unknown[];
  msg?: string;
}

async function leerError(response: Response): Promise<ApiError> {
  let detail = response.statusText || `HTTP ${response.status}`;
  let campos: Record<string, string> | undefined;
  try {
    const cuerpo = (await response.json()) as { detail?: unknown };
    if (typeof cuerpo.detail === "string") {
      detail = cuerpo.detail;
    } else if (Array.isArray(cuerpo.detail)) {
      const lista = cuerpo.detail as ErrorValidacion[];
      detail = lista[0]?.msg ?? detail;
      campos = {};
      for (const e of lista) {
        const campo = e.loc?.at(-1);
        if (typeof campo === "string" && e.msg !== undefined) {
          campos[campo] = e.msg;
        }
      }
    }
  } catch {
    // cuerpo no JSON: se conserva statusText
  }
  return new ApiError(response.status, detail, campos);
}

function headersDe(init: RequestInit | undefined): Headers {
  const headers = new Headers(init?.headers);
  if (typeof init?.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  const tenant = getClinicaId() || (tenantSesion === null ? "" : String(tenantSesion));
  if (tenant !== "") {
    headers.set(TENANT_HEADER, tenant);
  }
  const token = getAccessToken();
  if (token !== null) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

function enviar(path: string, init?: RequestInit): Promise<Response> {
  // "include": envía la cookie HttpOnly de refresh en /api/auth/refresh|logout.
  return fetch(buildUrl(path), { ...init, headers: headersDe(init), credentials: "include" });
}

let renovacion: Promise<boolean> | null = null;

/**
 * Renueva el access con la cookie de refresh. Single-flight: el backend rota y
 * blacklistea el refresh, así que dos llamadas paralelas harían un replay (401).
 */
export function renovarAccess(): Promise<boolean> {
  renovacion ??= (async () => {
    try {
      const response = await enviar("/api/auth/refresh", { method: "POST" });
      if (!response.ok) {
        return false;
      }
      const { access_token } = (await response.json()) as { access_token: string };
      setAccessToken(access_token);
      return true;
    } catch {
      return false;
    } finally {
      renovacion = null;
    }
  })();
  return renovacion;
}

async function pedir(path: string, init?: RequestInit): Promise<Response> {
  let response = await enviar(path, init);
  if (response.status === 401 && !path.startsWith("/api/auth/")) {
    if (await renovarAccess()) {
      response = await enviar(path, init);
    } else {
      setAccessToken(null);
      alExpirarSesion?.();
    }
  }
  if (!response.ok) {
    throw await leerError(response);
  }
  return response;
}

/** Fetch tipado contra /api/* con tenant header, Bearer, refresh único y ApiError. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await pedir(path, init);
  const texto = response.status === 204 ? "" : await response.text();
  return (texto === "" ? undefined : JSON.parse(texto)) as T;
}

/** Descarga binaria autenticada (el token va en el header, nunca en la URL). */
export async function apiFetchBlob(path: string): Promise<Blob> {
  return (await pedir(path)).blob();
}

/** Carga recursos independientes en paralelo (regla dura 13: nunca secuencial). */
export async function fetchAll<T>(paths: string[]): Promise<T[]> {
  return Promise.all(paths.map((path) => apiFetch<T>(path)));
}
