/** Landing de producto (C-20, spec product-landing). */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp } from "./helpers/app";

afterEach(() => vi.unstubAllGlobals());

describe("/", () => {
  it("muestra el producto, la captura con alt y los diferenciales sin pedir nada a la API", async () => {
    const { api } = renderApp("/", {});
    expect(
      await screen.findByRole("heading", { level: 1, name: "Turnos Odontología" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Agenda del día con una columna por sillón/ }),
    ).toBeInTheDocument();
    for (const titulo of [
      "Agenda por sillón, sin superposiciones",
      "Reserva online sin cuenta",
      "Historia clínica con odontograma",
      "Recordatorios por WhatsApp",
      "Cumplimiento legal",
    ]) {
      expect(screen.getByRole("heading", { name: titulo })).toBeInTheDocument();
    }
    expect(api.llamadas).toHaveLength(0);
  });

  it("todas las imágenes tienen texto alternativo", async () => {
    renderApp("/", {});
    await screen.findByRole("heading", { level: 1 });
    for (const img of document.querySelectorAll("img")) {
      expect(img.getAttribute("alt")?.length ?? 0).toBeGreaterThan(10);
    }
  });

  it("Reservar turno lleva a la reserva de la clínica de demo", async () => {
    const { router } = renderApp("/", {
      "GET /api/public/clinicas/clinica-piloto": { status: 404, json: { detail: "x" } },
    });
    const [primero] = await screen.findAllByRole("link", { name: /Reservar turno/ });
    await userEvent.click(primero as HTMLElement);
    await waitFor(() => expect(router.state.location.pathname).toBe("/reservar/clinica-piloto"));
  });

  it("Ingresar lleva a /login y el pie enlaza a privacidad y cumplimiento", async () => {
    const { router } = renderApp("/", {
      "POST /api/auth/refresh": { status: 401, json: { detail: "x" } },
    });
    const legales = await screen.findByRole("navigation", { name: "Legales" });
    expect(within(legales).getByRole("link", { name: "Privacidad" })).toHaveAttribute(
      "href",
      "/privacidad",
    );
    expect(within(legales).getByRole("link", { name: "Cumplimiento" })).toHaveAttribute(
      "href",
      "/cumplimiento",
    );
    const [ingresar] = screen.getAllByRole("link", { name: "Ingresar" });
    await userEvent.click(ingresar as HTMLElement);
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });
});
