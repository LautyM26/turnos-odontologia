/** API pública de reserva (C-06 D6): URLs, cuerpo, errores y nunca credenciales de sesión. */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  cancelarReserva,
  crearReserva,
  obtenerCatalogo,
  obtenerHuecos,
  obtenerReserva,
} from "@/features/reserva/api";
import { ApiError, setAccessToken } from "@/shared/api/client";

import { mockApi } from "./helpers/api";

afterEach(() => {
  setAccessToken(null);
  vi.unstubAllGlobals();
});

const DATOS = {
  profesional_id: 1,
  prestacion_id: 2,
  inicio: "2033-08-01T12:00:00Z",
  dni: "30111222",
  nombre: "Ana",
  apellido: "Sintetica",
  email: "ana@ejemplo.test",
  acepta_privacidad: true as const,
};

describe("api pública de reserva", () => {
  it("arma las URLs públicas y el cuerpo JSON", async () => {
    const api = mockApi({
      "GET /api/public/clinicas/clinica-piloto": { json: { clinica: "X" } },
      "GET /api/public/clinicas/clinica-piloto/huecos": { json: [] },
      "POST /api/public/clinicas/clinica-piloto/reservas": { status: 201, json: { token: "t" } },
      "GET /api/public/reservas/t%2Fx": { json: { estado: "reservado" } },
      "POST /api/public/reservas/t%2Fx/cancelar": { json: { estado: "cancelado" } },
    });
    await obtenerCatalogo("clinica-piloto");
    const desde = new Date("2033-08-01T03:00:00Z");
    await obtenerHuecos("clinica-piloto", 1, 2, desde, new Date("2033-08-08T03:00:00Z"));
    await crearReserva("clinica-piloto", DATOS);
    await obtenerReserva("t/x");
    await cancelarReserva("t/x");
    const huecos = new URL(
      api.de("GET /api/public/clinicas/clinica-piloto/huecos")[0]?.url ?? "",
      "http://x",
    );
    expect(huecos.searchParams.get("desde")).toBe("2033-08-01T03:00:00.000Z");
    expect(huecos.searchParams.get("profesional_id")).toBe("1");
    expect(api.cuerpo("POST /api/public/clinicas/clinica-piloto/reservas")).toEqual(DATOS);
    expect(api.de("POST /api/public/reservas/t%2Fx/cancelar")).toHaveLength(1);
  });

  it("nunca envía Authorization ni X-Clinica-Id aunque haya sesión de staff", async () => {
    setAccessToken("token-de-staff");
    const api = mockApi({ "GET /api/public/clinicas/c": { json: {} } });
    await obtenerCatalogo("c");
    const headers = api.llamadas[0]?.headers;
    expect(headers?.get("Authorization")).toBeNull();
    expect(headers?.get("X-Clinica-Id")).toBeNull();
  });

  it.each([404, 409, 422, 429])("propaga %i como ApiError con su detalle", async (status) => {
    mockApi({
      "POST /api/public/clinicas/c/reservas": { status, json: { detail: `error ${status}` } },
    });
    const error = await crearReserva("c", DATOS).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(status);
    expect((error as ApiError).detail).toBe(`error ${status}`);
  });
});
