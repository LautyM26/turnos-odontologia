/** Mock de fetch por tabla "MÉTODO /ruta" -> respuesta, con registro de llamadas. */

import { vi } from "vitest";

export interface RespuestaFija {
  status?: number;
  json?: unknown;
  text?: string;
  blob?: Blob;
}

export type Respuesta =
  | RespuestaFija
  | ((call: LlamadaApi) => RespuestaFija | Promise<RespuestaFija>);

export interface LlamadaApi {
  metodo: string;
  ruta: string;
  url: string;
  headers: Headers;
  body: BodyInit | null | undefined;
  /** Orden de llegada (para verificar paralelismo). */
  orden: number;
}

export interface ApiMock {
  llamadas: LlamadaApi[];
  /** Llamadas cuya clave coincide ("GET /api/pacientes"). */
  de: (clave: string) => LlamadaApi[];
  /** JSON del cuerpo de la última llamada con esa clave. */
  cuerpo: (clave: string) => unknown;
  restaurar: () => void;
}

/** Instala un fetch falso. Ruta sin query en la clave; ruta no mockeada -> error explícito. */
export function mockApi(tabla: Record<string, Respuesta>): ApiMock {
  const llamadas: LlamadaApi[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const ruta = url.split("?")[0] ?? url;
    const metodo = (init?.method ?? "GET").toUpperCase();
    const llamada: LlamadaApi = {
      metodo,
      ruta,
      url,
      headers: new Headers(init?.headers),
      body: init?.body,
      orden: llamadas.length,
    };
    llamadas.push(llamada);
    const definida = tabla[`${metodo} ${ruta}`];
    if (definida === undefined) {
      throw new Error(`mockApi: ruta no mockeada ${metodo} ${url}`);
    }
    const entrada = typeof definida === "function" ? await definida(llamada) : definida;
    const status = entrada.status ?? 200;
    if (entrada.blob !== undefined) {
      return new Response(entrada.blob, { status });
    }
    if (entrada.json !== undefined) {
      return new Response(JSON.stringify(entrada.json), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(entrada.text ?? null, { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    llamadas,
    de: (clave) => llamadas.filter((l) => `${l.metodo} ${l.ruta}` === clave),
    cuerpo: (clave) => {
      const ultima = llamadas.filter((l) => `${l.metodo} ${l.ruta}` === clave).at(-1);
      return typeof ultima?.body === "string" ? JSON.parse(ultima.body) : ultima?.body;
    },
    restaurar: () => vi.unstubAllGlobals(),
  };
}
