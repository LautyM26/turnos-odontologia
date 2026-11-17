/**
 * Sesión del staff: identidad en memoria (store externo) + access en client.ts.
 * Nada en localStorage/sessionStorage: el refresh vive en la cookie HttpOnly.
 */

import { useSyncExternalStore } from "react";
import { redirect } from "react-router";

import type { Me } from "@/features/clinica/tipos";
import { apiFetch, renovarAccess, setAccessToken, setTenantSesion } from "@/shared/api/client";

const RUTA_POR_DEFECTO = "/pacientes";

let identidad: Me | null = null;
const oyentes = new Set<() => void>();

function fijarIdentidad(me: Me | null): void {
  identidad = me;
  setTenantSesion(me?.tenant_id ?? null);
  for (const oyente of oyentes) {
    oyente();
  }
}

export function getIdentidad(): Me | null {
  return identidad;
}

/** Identidad actual como estado reactivo (sin Context). */
export function useSesion(): Me | null {
  return useSyncExternalStore(
    (oyente) => {
      oyentes.add(oyente);
      return () => oyentes.delete(oyente);
    },
    () => identidad,
  );
}

/** Descarta access e identidad de la memoria. */
export function limpiarSesion(): void {
  setAccessToken(null);
  fijarIdentidad(null);
}

/** Solo rutas internas: `//evil` o `https://…` caen en la ruta por defecto. */
export function rutaSegura(redirectTo: string | null): string {
  return redirectTo?.startsWith("/") && !redirectTo.startsWith("//")
    ? redirectTo
    : RUTA_POR_DEFECTO;
}

async function cargarIdentidad(): Promise<Me> {
  const me = await apiFetch<Me>("/api/auth/me");
  fijarIdentidad(me);
  return me;
}

export async function iniciarSesion(email: string, password: string): Promise<Me> {
  const { access_token } = await apiFetch<{ access_token: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(access_token);
  return cargarIdentidad();
}

let renovando: Promise<Me | null> | null = null;

/** Recupera la sesión con la cookie de refresh. Single-flight (ver renovarAccess). */
export function renovarSesion(): Promise<Me | null> {
  renovando ??= (async () => {
    try {
      return (await renovarAccess()) ? await cargarIdentidad() : null;
    } catch {
      return null;
    } finally {
      renovando = null;
    }
  })();
  return renovando;
}

/** Loader de rutas protegidas: identidad o redirect a /login recordando la ruta. */
export async function requireSession(url: URL): Promise<Me> {
  const me = identidad ?? (await renovarSesion());
  if (me === null) {
    throw redirect(`/login?redirectTo=${encodeURIComponent(url.pathname + url.search)}`);
  }
  return me;
}

export async function cerrarSesion(): Promise<void> {
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } catch {
    // best effort: la sesión local se descarta igual
  }
  limpiarSesion();
}
