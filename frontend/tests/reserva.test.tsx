/** Pantallas públicas de reserva (C-06, spec public-booking-web) con fetch simulado. */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Respuesta } from "./helpers/api";
import { renderApp } from "./helpers/app";

afterEach(() => vi.unstubAllGlobals());

const CATALOGO = {
  clinica: "Clínica Piloto",
  zona_horaria: "America/Argentina/Buenos_Aires",
  prestaciones: [{ id: 2, nombre: "Consulta", duracion_min: 30 }],
  profesionales: [{ id: 1, nombre: "Dra. Sintética", especialidad: null }],
};
// 2033-08-01 es lunes; 12:00Z = 09:00 en Buenos Aires
const HUECOS = [
  { inicio: "2033-08-01T12:00:00Z", fin: "2033-08-01T12:30:00Z" },
  { inicio: "2033-08-01T12:15:00Z", fin: "2033-08-01T12:45:00Z" },
];
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
const BASE = "/api/public/clinicas/clinica-piloto";

function tabla(extra: Record<string, Respuesta> = {}): Record<string, Respuesta> {
  return {
    [`GET ${BASE}`]: { json: CATALOGO },
    [`GET ${BASE}/huecos`]: { json: HUECOS },
    [`POST ${BASE}/reservas`]: { status: 201, json: { ...RESERVA, token: "tok-123" } },
    "GET /api/public/reservas/tok-123": { json: RESERVA },
    ...extra,
  };
}

async function elegirYCompletar(): Promise<void> {
  await userEvent.selectOptions(await screen.findByLabelText("Prestación"), "2");
  await userEvent.selectOptions(screen.getByLabelText("Profesional"), "1");
  await userEvent.click(await screen.findByRole("button", { name: "09:00" }));
  await userEvent.type(screen.getByLabelText("Nombre"), "Ana");
  await userEvent.type(screen.getByLabelText("Apellido"), "Sintetica");
  await userEvent.type(screen.getByLabelText("DNI"), "30111222");
  await userEvent.type(screen.getByLabelText("Email"), "ana@ejemplo.test");
  await userEvent.click(screen.getByRole("checkbox"));
}

describe("/reservar/:slug", () => {
  it("flujo completo: elige hueco, completa datos y navega al comprobante", async () => {
    const { api, router } = renderApp("/reservar/clinica-piloto", tabla());
    expect(await screen.findByRole("heading", { name: "Reservar turno" })).toBeInTheDocument();
    await elegirYCompletar();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar reserva" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/reserva/tok-123"));
    expect(api.cuerpo(`POST ${BASE}/reservas`)).toMatchObject({
      profesional_id: 1,
      prestacion_id: 2,
      inicio: "2033-08-01T12:00:00Z",
      dni: "30111222",
      acepta_privacidad: true,
    });
    expect(await screen.findByRole("heading", { name: "Tu turno" })).toBeInTheDocument();
  });

  it("409: avisa, recarga los huecos y conserva los datos cargados", async () => {
    const { api } = renderApp(
      "/reservar/clinica-piloto",
      tabla({
        [`POST ${BASE}/reservas`]: { status: 409, json: { detail: "Horario no disponible" } },
      }),
    );
    await elegirYCompletar();
    const pedidosAntes = api.de(`GET ${BASE}/huecos`).length;
    await userEvent.click(screen.getByRole("button", { name: "Confirmar reserva" }));
    expect(await screen.findByText(/se acaba de ocupar/)).toBeInTheDocument();
    await waitFor(() => expect(api.de(`GET ${BASE}/huecos`).length).toBe(pedidosAntes + 1));
    await userEvent.click(await screen.findByRole("button", { name: "09:15" }));
    expect(screen.getByLabelText("Nombre")).toHaveValue("Ana");
    expect(screen.getByLabelText("DNI")).toHaveValue("30111222");
  });

  it("422: muestra el error asociado al campo sin perder lo cargado", async () => {
    renderApp(
      "/reservar/clinica-piloto",
      tabla({
        [`POST ${BASE}/reservas`]: {
          status: 422,
          json: { detail: [{ loc: ["body", "dni"], msg: "DNI inválido" }] },
        },
      }),
    );
    await elegirYCompletar();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar reserva" }));
    const dni = screen.getByLabelText("DNI");
    await waitFor(() => expect(dni).toHaveAttribute("aria-invalid", "true"));
    expect(dni).toHaveAccessibleDescription("DNI inválido");
    expect(screen.getByLabelText("Apellido")).toHaveValue("Sintetica");
  });

  it("slug inexistente: Enlace no encontrado", async () => {
    renderApp("/reservar/no-existe", {
      "GET /api/public/clinicas/no-existe": { status: 404, json: { detail: "No encontrado" } },
    });
    expect(
      await screen.findByRole("heading", { name: "Enlace no encontrado" }),
    ).toBeInTheDocument();
  });

  it("agrupa los huecos por día en hora de la clínica", async () => {
    renderApp("/reservar/clinica-piloto", tabla());
    await userEvent.selectOptions(await screen.findByLabelText("Prestación"), "2");
    await userEvent.selectOptions(screen.getByLabelText("Profesional"), "1");
    expect(await screen.findByText(/lunes, 1 de agosto/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "09:15" })).toHaveAttribute("aria-pressed", "false");
  });

  it("no escribe nada en localStorage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const { router } = renderApp("/reservar/clinica-piloto", tabla());
    await elegirYCompletar();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar reserva" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/reserva/tok-123"));
    expect(setItem).not.toHaveBeenCalled();
    setItem.mockRestore();
  });
});

describe("/reserva/:token", () => {
  it("muestra el comprobante y cancela con confirmación", async () => {
    const { api } = renderApp(
      "/reserva/tok-123",
      tabla({
        "POST /api/public/reservas/tok-123/cancelar": {
          json: { ...RESERVA, estado: "cancelado", cancelable: false },
        },
      }),
    );
    expect(await screen.findByText("Dra. Sintética")).toBeInTheDocument();
    expect(screen.getByText("09:00 a 09:30 hs")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancelar turno" }));
    const dialogo = await screen.findByRole("dialog");
    await userEvent.click(within(dialogo).getByRole("button", { name: "Sí, cancelar" }));
    expect(await screen.findByText(/Turno cancelado/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancelar turno" })).not.toBeInTheDocument();
    expect(api.de("POST /api/public/reservas/tok-123/cancelar")).toHaveLength(1);
  });

  it("token inexistente: Reserva no encontrada", async () => {
    renderApp("/reserva/nada", {
      "GET /api/public/reservas/nada": { status: 404, json: { detail: "No encontrado" } },
    });
    expect(
      await screen.findByRole("heading", { name: "Reserva no encontrada" }),
    ).toBeInTheDocument();
  });
});
