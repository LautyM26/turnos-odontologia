/** Router, login y layout (spec web-session): rutas protegidas/públicas, ingreso, identidad, logout. */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/shared/api/client";

import { conSesion, renderApp, sinSesion } from "./helpers/app";
import { meAdmin, meOdontologo, meRecepcion } from "./helpers/fixtures";

const listaVacia = { "GET /api/pacientes": { json: { items: [], next_cursor: null } } };

afterEach(() => vi.unstubAllGlobals());

describe("rutas protegidas y públicas", () => {
  it("/pacientes sin sesión redirige a /login recordando la ruta", async () => {
    const { router } = renderApp("/pacientes", { ...sinSesion, ...listaVacia });
    expect(await screen.findByRole("heading", { name: "Ingresar" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toContain("redirectTo=%2Fpacientes");
    expect(screen.queryByRole("link", { name: "Cerrar sesión" })).not.toBeInTheDocument();
  });

  it.each([
    ["/", "Turnos Odontología"],
    ["/cumplimiento", "Cumplimiento y privacidad"],
    ["/comprobantes/1", "Comprobante"],
  ])("%s se muestra sin sesión y sin pedir nada", async (ruta, titulo) => {
    const { api } = renderApp(ruta, {});
    expect(await screen.findByRole("heading", { name: titulo })).toBeInTheDocument();
    expect(api.llamadas).toHaveLength(0);
  });

  it("con sesión vigente /login lleva a /pacientes", async () => {
    const { router } = renderApp("/pacientes", { ...conSesion(meOdontologo), ...listaVacia });
    await screen.findByRole("heading", { name: "Pacientes" });
    await router.navigate("/login");
    await waitFor(() => expect(router.state.location.pathname).toBe("/pacientes"));
  });

  it("recarga en una ruta protegida recupera la sesión por refresh", async () => {
    const { router, api } = renderApp("/pacientes", { ...conSesion(meOdontologo), ...listaVacia });
    expect(await screen.findByRole("heading", { name: "Pacientes" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/pacientes");
    expect(api.de("POST /api/auth/refresh")).toHaveLength(1);
  });

  it("sesión expirada en medio del uso lleva a /login?expirada=1", async () => {
    const { router } = renderApp("/pacientes", {
      ...conSesion(meOdontologo),
      ...listaVacia,
      "GET /api/otro": { status: 401, json: { detail: "x" } },
    });
    await screen.findByRole("heading", { name: "Pacientes" });
    // a partir de acá el refresh deja de funcionar
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "x" }), { status: 401 })),
    );
    await apiFetch("/api/otro").catch(() => undefined);
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.search).toContain("expirada=1");
    expect(await screen.findByText("Tu sesión expiró, volvé a ingresar")).toBeInTheDocument();
  });
});

describe("LoginPage", () => {
  const loginOk = {
    "POST /api/auth/login": { json: { access_token: "tok", expires_in: 900 } },
    "GET /api/auth/me": { json: meOdontologo },
    ...listaVacia,
  };

  async function completar(email: string, pass: string): Promise<void> {
    await userEvent.type(await screen.findByLabelText("Email"), email);
    await userEvent.type(screen.getByLabelText("Contraseña"), pass);
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
  }

  it("campos con label y autocomplete", async () => {
    renderApp("/login", sinSesion);
    expect(await screen.findByLabelText("Email")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Contraseña")).toHaveAttribute("autocomplete", "current-password");
  });

  it("login correcto navega a /pacientes y muestra email y rol", async () => {
    const { router } = renderApp("/login", { ...sinSesion, ...loginOk });
    await completar("odontologo@clinica-piloto.test", "pw-sintetica");
    await waitFor(() => expect(router.state.location.pathname).toBe("/pacientes"));
    expect(await screen.findByText("odontologo@clinica-piloto.test")).toBeInTheDocument();
    expect(screen.getByText("Odontólogo")).toBeInTheDocument();
  });

  it("vuelve a la ruta pedida originalmente", async () => {
    const { router } = renderApp("/login?redirectTo=%2Fpacientes%2F7%2Fodontograma", {
      ...sinSesion,
      ...loginOk,
    });
    await completar("o@clinica-piloto.test", "x");
    await waitFor(() => expect(router.state.location.pathname).toBe("/pacientes/7/odontograma"));
  });

  it("redirectTo externo cae en /pacientes", async () => {
    const { router } = renderApp("/login?redirectTo=https%3A%2F%2Fevil.test", {
      ...sinSesion,
      ...loginOk,
    });
    await completar("o@clinica-piloto.test", "x");
    await waitFor(() => expect(router.state.location.pathname).toBe("/pacientes"));
  });

  it("401: mensaje asociado, conserva email, limpia contraseña, no navega", async () => {
    const { router } = renderApp("/login", {
      ...sinSesion,
      "POST /api/auth/login": { status: 401, json: { detail: "Credenciales inválidas" } },
    });
    await completar("o@clinica-piloto.test", "mala");
    expect(await screen.findByRole("alert")).toHaveTextContent("Email o contraseña incorrectos");
    expect(screen.getByLabelText("Email")).toHaveValue("o@clinica-piloto.test");
    expect(screen.getByLabelText("Contraseña")).toHaveValue("");
    expect(router.state.location.pathname).toBe("/login");
  });

  it("429: pide esperar un minuto", async () => {
    renderApp("/login", {
      ...sinSesion,
      "POST /api/auth/login": { status: 429, json: { detail: "rate" } },
    });
    await completar("o@clinica-piloto.test", "x");
    expect(await screen.findByRole("alert")).toHaveTextContent("Esperá un minuto");
  });

  it("deshabilita el botón mientras envía (sin doble envío)", async () => {
    let liberar: () => void = () => undefined;
    const espera = new Promise<void>((r) => {
      liberar = r;
    });
    const { api } = renderApp("/login", {
      ...sinSesion,
      ...loginOk,
      "POST /api/auth/login": async () => {
        await espera;
        return { json: { access_token: "tok", expires_in: 900 } };
      },
    });
    await userEvent.type(await screen.findByLabelText("Email"), "o@clinica-piloto.test");
    await userEvent.type(screen.getByLabelText("Contraseña"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(screen.getByRole("button", { name: "Ingresando…" })).toBeDisabled();
    liberar();
    await screen.findByRole("heading", { name: "Pacientes" });
    expect(api.de("POST /api/auth/login")).toHaveLength(1);
  });

  it("aviso de sesión expirada con ?expirada=1", async () => {
    renderApp("/login?expirada=1", sinSesion);
    expect(await screen.findByText("Tu sesión expiró, volvé a ingresar")).toBeInTheDocument();
  });
});

describe("AppLayout", () => {
  it("enlace Saltar al contenido y navegación con aria-current", async () => {
    renderApp("/pacientes", { ...conSesion(meOdontologo), ...listaVacia });
    expect(await screen.findByRole("link", { name: "Saltar al contenido" })).toHaveAttribute(
      "href",
      "#contenido",
    );
    expect(screen.getByRole("link", { name: "Pacientes" })).toHaveAttribute("aria-current", "page");
  });

  it.each([
    [meRecepcion, "Recepcionista"],
    [meOdontologo, "Odontólogo"],
    [
      { ...meAdmin, roles: ["admin", "odontologo"] as typeof meAdmin.roles },
      "Administrador, Odontólogo",
    ],
  ])("muestra email y roles legibles (%#)", async (me, rol) => {
    renderApp("/pacientes", { ...conSesion(me), ...listaVacia });
    expect(await screen.findByText(me.email)).toBeInTheDocument();
    expect(screen.getByText(rol)).toBeInTheDocument();
  });

  it("Cerrar sesión llama a logout y navega a /login", async () => {
    const { router, api } = renderApp("/pacientes", { ...conSesion(meOdontologo), ...listaVacia });
    await userEvent.click(await screen.findByRole("button", { name: "Cerrar sesión" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(api.de("POST /api/auth/logout")).toHaveLength(1);
  });

  it("Cerrar sesión con el backend caído igual muestra /login", async () => {
    const { router } = renderApp("/pacientes", {
      ...conSesion(meOdontologo),
      ...listaVacia,
      "POST /api/auth/logout": () => {
        throw new Error("sin red");
      },
    });
    await userEvent.click(await screen.findByRole("button", { name: "Cerrar sesión" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(await screen.findByRole("heading", { name: "Ingresar" })).toBeInTheDocument();
  });
});

describe("Título del documento", () => {
  it("cada pantalla tiene su título (a11y)", async () => {
    renderApp("/login", sinSesion);
    await screen.findByRole("heading", { name: "Ingresar" });
    await waitFor(() => expect(document.title).toBe("Ingresar · Turnos Odontología"));
  });
});
