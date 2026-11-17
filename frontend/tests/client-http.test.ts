/** Cliente HTTP endurecido (C-10): tenant, errores, multipart, 401 + refresh single-flight. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  apiFetch,
  apiFetchBlob,
  onSesionExpirada,
  setAccessToken,
  setTenantSesion,
} from "@/shared/api/client";

import { type ApiMock, mockApi } from "./helpers/api";

let api: ApiMock;

beforeEach(() => {
  setAccessToken(null);
  setTenantSesion(null);
  onSesionExpirada(null);
  vi.stubEnv("VITE_CLINICA_ID", "");
});
afterEach(() => {
  api.restaurar();
  vi.unstubAllEnvs();
});

describe("X-Clinica-Id (delta platform-config)", () => {
  it("usa VITE_CLINICA_ID cuando está configurada", async () => {
    vi.stubEnv("VITE_CLINICA_ID", "5");
    setTenantSesion(1);
    api = mockApi({ "GET /api/x": { json: {} } });
    await apiFetch("/api/x");
    expect(api.llamadas[0]?.headers.get("X-Clinica-Id")).toBe("5");
  });

  it("sin env usa el tenant_id de la sesión", async () => {
    setTenantSesion(1);
    api = mockApi({ "GET /api/x": { json: {} } });
    await apiFetch("/api/x");
    expect(api.llamadas[0]?.headers.get("X-Clinica-Id")).toBe("1");
  });

  it("sin env ni sesión no manda el header (nunca vacío)", async () => {
    api = mockApi({ "POST /api/auth/login": { json: {} } });
    await apiFetch("/api/auth/login", { method: "POST", body: "{}" });
    expect(api.llamadas[0]?.headers.has("X-Clinica-Id")).toBe(false);
  });
});

describe("ApiError y cuerpo", () => {
  it("toma el detail string del JSON", async () => {
    api = mockApi({ "GET /api/x": { status: 403, json: { detail: "Rol insuficiente" } } });
    const err = await apiFetch("/api/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(403);
    expect((err as ApiError).detail).toBe("Rol insuficiente");
  });

  it("resume la lista 422 y mapea por campo", async () => {
    api = mockApi({
      "PATCH /api/x": {
        status: 422,
        json: { detail: [{ loc: ["body", "telefono"], msg: "Teléfono inválido", type: "x" }] },
      },
    });
    const err = (await apiFetch("/api/x", { method: "PATCH", body: "{}" }).catch(
      (e: unknown) => e,
    )) as ApiError;
    expect(err.detail).toBe("Teléfono inválido");
    expect(err.campos).toEqual({ telefono: "Teléfono inválido" });
  });

  it("Content-Type JSON solo con cuerpo string; nunca con FormData", async () => {
    api = mockApi({ "POST /api/x": { json: {} } });
    await apiFetch("/api/x", { method: "POST", body: "{}" });
    await apiFetch("/api/x", { method: "POST", body: new FormData() });
    expect(api.llamadas[0]?.headers.get("Content-Type")).toBe("application/json");
    expect(api.llamadas[1]?.headers.has("Content-Type")).toBe(false);
  });

  it("204 devuelve undefined", async () => {
    api = mockApi({ "POST /api/x": { status: 204 } });
    expect(await apiFetch("/api/x", { method: "POST" })).toBeUndefined();
  });

  it("apiFetchBlob descarga con Authorization y sin token en la URL", async () => {
    setAccessToken("tok");
    api = mockApi({ "GET /api/f": { text: "abc" } });
    const blob = await apiFetchBlob("/api/f");
    expect(blob.size).toBe(3);
    expect(api.llamadas[0]?.headers.get("Authorization")).toBe("Bearer tok");
    expect(api.llamadas[0]?.url).not.toContain("tok");
  });
});

describe("401 → refresh único → reintento único", () => {
  it("renueva una vez y reintenta con el access nuevo", async () => {
    setAccessToken("viejo");
    let intentos = 0;
    api = mockApi({
      "GET /api/pacientes": (c) => {
        if (c.headers.get("Authorization") === "Bearer nuevo") {
          return { json: { ok: true } };
        }
        intentos++;
        return { status: 401, json: { detail: "expirado" } };
      },
      "POST /api/auth/refresh": { json: { access_token: "nuevo", expires_in: 900 } },
    });
    expect(await apiFetch("/api/pacientes")).toEqual({ ok: true });
    expect(intentos).toBe(1);
    expect(api.de("POST /api/auth/refresh")).toHaveLength(1);
  });

  it("tres 401 simultáneos comparten UNA llamada a refresh", async () => {
    setAccessToken("viejo");
    api = mockApi({
      "GET /api/a": (c) =>
        c.headers.get("Authorization") === "Bearer nuevo" ? { json: 1 } : { status: 401 },
      "GET /api/b": (c) =>
        c.headers.get("Authorization") === "Bearer nuevo" ? { json: 2 } : { status: 401 },
      "GET /api/c": (c) =>
        c.headers.get("Authorization") === "Bearer nuevo" ? { json: 3 } : { status: 401 },
      "POST /api/auth/refresh": { json: { access_token: "nuevo", expires_in: 900 } },
    });
    const r = await Promise.all([apiFetch("/api/a"), apiFetch("/api/b"), apiFetch("/api/c")]);
    expect(r).toEqual([1, 2, 3]);
    expect(api.de("POST /api/auth/refresh")).toHaveLength(1);
  });

  it("refresh rechazado: avisa sesión expirada, no reintenta en bucle", async () => {
    const alExpirar = vi.fn();
    onSesionExpirada(alExpirar);
    api = mockApi({
      "GET /api/x": { status: 401, json: { detail: "nope" } },
      "POST /api/auth/refresh": { status: 401, json: { detail: "nope" } },
    });
    await expect(apiFetch("/api/x")).rejects.toMatchObject({ status: 401 });
    expect(alExpirar).toHaveBeenCalledOnce();
    expect(api.de("GET /api/x")).toHaveLength(1);
    expect(api.de("POST /api/auth/refresh")).toHaveLength(1);
  });

  it("un 401 de /api/auth/* (login) no dispara refresh", async () => {
    api = mockApi({ "POST /api/auth/login": { status: 401, json: { detail: "bad" } } });
    await expect(apiFetch("/api/auth/login", { method: "POST", body: "{}" })).rejects.toMatchObject(
      { status: 401 },
    );
    expect(api.llamadas).toHaveLength(1);
  });
});
