/** Reprogramación pública por enlace (C-20, spec reschedule-web) con fetch simulado. */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Respuesta } from "./helpers/api";
import { renderApp } from "./helpers/app";

afterEach(() => vi.unstubAllGlobals());

// 2033-08-01 es lunes; 12:00Z = 09:00 en Buenos Aires
const RESERVA = {
  clinica: "Clínica Piloto",
  zona_horaria: "America/Argentina/Buenos_Aires",
  profesional: "Dra. Sintética",
  prestacion: "Consulta",
  inicio: "2033-08-01T12:00:00Z",
  fin: "2033-08-01T12:30:00Z",
  estado: "reservado",
  cancelable: true,
};
// jueves 4 a las 10:30 y viernes 5 a las 11:00 (hora de la clínica)
const OPCIONES = [
  { inicio: "2033-08-04T13:30:00Z", fin: "2033-08-04T14:00:00Z" },
  { inicio: "2033-08-05T14:00:00Z", fin: "2033-08-05T14:30:00Z" },
];
const BASE = "/api/public/reservas/tok-1";

function tabla(extra: Record<string, Respuesta> = {}): Record<string, Respuesta> {
  return {
    [`GET ${BASE}`]: { json: RESERVA },
    [`GET ${BASE}/opciones`]: { json: OPCIONES },
    ...extra,
  };
}

describe("/reprogramar/:token", () => {
  it("pide turno y opciones en paralelo (regla dura 13)", async () => {
    let liberar: () => void = () => undefined;
    const puerta = new Promise<void>((r) => {
      liberar = r;
    });
    const { api } = renderApp(
      "/reprogramar/tok-1",
      tabla({
        [`GET ${BASE}`]: async () => {
          await puerta;
          return { json: RESERVA };
        },
        [`GET ${BASE}/opciones`]: async () => {
          await puerta;
          return { json: OPCIONES };
        },
      }),
    );
    await waitFor(() => {
      expect(api.de(`GET ${BASE}`)).toHaveLength(1);
      expect(api.de(`GET ${BASE}/opciones`)).toHaveLength(1);
    });
    liberar();
    expect(await screen.findByText("Dra. Sintética")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { pressed: false })).toHaveLength(2);
  });

  it("elige el jueves 10:30, confirma y ve Turno reprogramado", async () => {
    const nueva = { ...RESERVA, inicio: OPCIONES[0]?.inicio, fin: OPCIONES[0]?.fin };
    const { api } = renderApp(
      "/reprogramar/tok-1",
      tabla({ [`POST ${BASE}/reprogramar`]: { json: nueva } }),
    );
    await userEvent.click(await screen.findByRole("button", { name: /jueves.*10:30 hs/i }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar nuevo horario" }));
    expect(await screen.findByRole("heading", { name: "Turno reprogramado" })).toBeInTheDocument();
    expect(screen.getByText("10:30 a 11:00 hs")).toBeInTheDocument();
    expect(api.cuerpo(`POST ${BASE}/reprogramar`)).toEqual({ inicio: OPCIONES[0]?.inicio });
    expect(screen.getByRole("link", { name: "Ver comprobante" })).toHaveAttribute(
      "href",
      "/reserva/tok-1",
    );
  });

  it("409: avisa y muestra las alternativas de la respuesta, sin perder el turno", async () => {
    const alternativa = { inicio: "2033-08-08T15:00:00Z", fin: "2033-08-08T15:30:00Z" };
    renderApp(
      "/reprogramar/tok-1",
      tabla({
        [`POST ${BASE}/reprogramar`]: {
          status: 409,
          json: { detail: "Horario no disponible", alternativas: [alternativa] },
        },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: /jueves.*10:30 hs/i }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar nuevo horario" }));
    expect(await screen.findByText(/se acaba de ocupar/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /lunes.*12:00 hs/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /jueves/i })).not.toBeInTheDocument();
    expect(screen.getByText("Dra. Sintética")).toBeInTheDocument();
  });

  it("422: el turno ya no se puede reprogramar online", async () => {
    renderApp(
      "/reprogramar/tok-1",
      tabla({
        [`GET ${BASE}/opciones`]: {
          status: 422,
          json: { detail: "El turno no se puede reprogramar" },
        },
      }),
    );
    expect(await screen.findByText(/ya no se puede reprogramar online/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Confirmar nuevo horario" }),
    ).not.toBeInTheDocument();
  });

  it("404: Reserva no encontrada", async () => {
    renderApp("/reprogramar/nada", {
      "GET /api/public/reservas/nada": { status: 404, json: { detail: "No encontrado" } },
      "GET /api/public/reservas/nada/opciones": { status: 404, json: { detail: "No encontrado" } },
    });
    expect(
      await screen.findByRole("heading", { name: "Reserva no encontrada" }),
    ).toBeInTheDocument();
  });

  it("429 al confirmar: pide esperar un minuto", async () => {
    renderApp(
      "/reprogramar/tok-1",
      tabla({
        [`POST ${BASE}/reprogramar`]: { status: 429, json: { detail: "Rate limit exceeded" } },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: /jueves.*10:30 hs/i }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar nuevo horario" }));
    expect(await screen.findByText(/Esperá un minuto/)).toBeInTheDocument();
  });
});

describe("comprobante: enlace a reprogramar", () => {
  it("visible en un turno futuro cancelable", async () => {
    renderApp("/reserva/tok-1", tabla());
    expect(await screen.findByRole("link", { name: "Reprogramar" })).toHaveAttribute(
      "href",
      "/reprogramar/tok-1",
    );
  });

  it("oculto en un turno cancelado", async () => {
    renderApp(
      "/reserva/tok-1",
      tabla({ [`GET ${BASE}`]: { json: { ...RESERVA, estado: "cancelado", cancelable: false } } }),
    );
    expect(await screen.findByText("Dra. Sintética")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Reprogramar" })).not.toBeInTheDocument();
  });
});
