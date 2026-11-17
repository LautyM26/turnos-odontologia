/** Sesión en memoria (web-session): login, refresh single-flight, loader y redirectTo seguro. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cerrarSesion,
  getIdentidad,
  iniciarSesion,
  limpiarSesion,
  renovarSesion,
  requireSession,
  rutaSegura,
} from "@/features/auth/session";
import { getAccessToken } from "@/shared/api/client";

import { type ApiMock, mockApi } from "./helpers/api";
import { meOdontologo } from "./helpers/fixtures";

let api: ApiMock;
beforeEach(() => limpiarSesion());
afterEach(() => vi.unstubAllGlobals());

describe("rutaSegura (anti open-redirect)", () => {
  it("acepta rutas internas", () => {
    expect(rutaSegura("/pacientes/7/odontograma")).toBe("/pacientes/7/odontograma");
    expect(rutaSegura("/pacientes?buscar=perez")).toBe("/pacientes?buscar=perez");
  });

  it("rechaza externas y vacías", () => {
    expect(rutaSegura("//evil.test")).toBe("/pacientes");
    expect(rutaSegura("https://evil.test/x")).toBe("/pacientes");
    expect(rutaSegura(null)).toBe("/pacientes");
    expect(rutaSegura("pacientes")).toBe("/pacientes");
  });
});

describe("iniciarSesion", () => {
  it("guarda el access en memoria y carga la identidad", async () => {
    api = mockApi({
      "POST /api/auth/login": { json: { access_token: "tok", expires_in: 900 } },
      "GET /api/auth/me": { json: meOdontologo },
    });
    await iniciarSesion("odontologo@clinica-piloto.test", "x");
    expect(getAccessToken()).toBe("tok");
    expect(getIdentidad()).toEqual(meOdontologo);
    expect(api.cuerpo("POST /api/auth/login")).toEqual({
      email: "odontologo@clinica-piloto.test",
      password: "x",
    });
  });

  it("credenciales inválidas propagan el 401 sin identidad", async () => {
    api = mockApi({ "POST /api/auth/login": { status: 401, json: { detail: "x" } } });
    await expect(iniciarSesion("a@b.test", "mal")).rejects.toMatchObject({ status: 401 });
    expect(getIdentidad()).toBeNull();
  });
});

describe("renovarSesion", () => {
  it("dos llamadas simultáneas hacen UN refresh", async () => {
    api = mockApi({
      "POST /api/auth/refresh": { json: { access_token: "n", expires_in: 900 } },
      "GET /api/auth/me": { json: meOdontologo },
    });
    const [a, b] = await Promise.all([renovarSesion(), renovarSesion()]);
    expect(a).toEqual(meOdontologo);
    expect(b).toEqual(meOdontologo);
    expect(api.de("POST /api/auth/refresh")).toHaveLength(1);
  });

  it("refresh rechazado devuelve null", async () => {
    api = mockApi({ "POST /api/auth/refresh": { status: 401, json: { detail: "x" } } });
    expect(await renovarSesion()).toBeNull();
  });
});

describe("requireSession (loader)", () => {
  it("con identidad en memoria no pide nada", async () => {
    api = mockApi({
      "POST /api/auth/login": { json: { access_token: "t", expires_in: 900 } },
      "GET /api/auth/me": { json: meOdontologo },
    });
    await iniciarSesion("a@b.test", "x");
    expect(await requireSession(new URL("http://x/pacientes"))).toEqual(meOdontologo);
    expect(api.de("POST /api/auth/refresh")).toHaveLength(0);
  });

  it("recarga: recupera la sesión por refresh", async () => {
    api = mockApi({
      "POST /api/auth/refresh": { json: { access_token: "n", expires_in: 900 } },
      "GET /api/auth/me": { json: meOdontologo },
    });
    expect(await requireSession(new URL("http://x/pacientes/7"))).toEqual(meOdontologo);
  });

  it("sin sesión redirige a /login recordando la ruta", async () => {
    api = mockApi({ "POST /api/auth/refresh": { status: 401, json: { detail: "x" } } });
    const resp = await requireSession(new URL("http://x/pacientes/7/odontograma?a=1")).catch(
      (e: unknown) => e,
    );
    expect(resp).toBeInstanceOf(Response);
    expect((resp as Response).headers.get("Location")).toBe(
      "/login?redirectTo=%2Fpacientes%2F7%2Fodontograma%3Fa%3D1",
    );
  });
});

describe("cerrarSesion", () => {
  it("descarta la sesión local aunque el backend falle", async () => {
    api = mockApi({
      "POST /api/auth/login": { json: { access_token: "t", expires_in: 900 } },
      "GET /api/auth/me": { json: meOdontologo },
      "POST /api/auth/logout": () => {
        throw new Error("red caída");
      },
    });
    await iniciarSesion("a@b.test", "x");
    await cerrarSesion();
    expect(getIdentidad()).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(api.de("POST /api/auth/logout")).toHaveLength(1);
  });
});
