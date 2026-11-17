/** Pestañas, permisos y ficha de anamnesis (spec clinical-record-web). */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { puedeCorregir, puedeEscribirClinica } from "@/features/clinica/permisos";
import { CONSENTIMIENTO_FALTANTE } from "@/shared/api/resultado";

import { renderApp, tablaPaciente } from "./helpers/app";
import {
  evolucion,
  ficha,
  historia,
  meAdmin,
  meOdontologo,
  meRecepcion,
  paciente,
} from "./helpers/fixtures";

afterEach(() => vi.unstubAllGlobals());

const fichaV1 = ficha({
  version: 1,
  anamnesis: "Sin antecedentes de relevancia (sintético)",
  alergias: "Ninguna conocida",
  antecedentes: "Control anual",
  autor_usuario_id: 10,
  created_at: "2026-11-10T15:30:00Z",
});

describe("permisos (puros)", () => {
  it("solo el odontólogo escribe en la HC", () => {
    expect(puedeEscribirClinica(meOdontologo)).toBe(true);
    expect(puedeEscribirClinica(meAdmin)).toBe(false);
    expect(puedeEscribirClinica(meRecepcion)).toBe(false);
    expect(puedeEscribirClinica({ ...meAdmin, roles: ["admin", "odontologo"] })).toBe(true);
  });

  it("puedeCorregir: autor + odontólogo + sin corregir", () => {
    const e = evolucion({ autor_usuario_id: 10 });
    expect(puedeCorregir(e, meOdontologo)).toBe(true);
    expect(puedeCorregir({ ...e, autor_usuario_id: 99 }, meOdontologo)).toBe(false);
    expect(puedeCorregir({ ...e, corregida_por_id: 5 }, meOdontologo)).toBe(false);
    expect(puedeCorregir(e, { ...meAdmin, sub: 10 })).toBe(false);
  });
});

describe("Pestañas del paciente", () => {
  it("/pacientes/7 abre Ficha y las pestañas son enlaces con aria-current", async () => {
    const { router, api } = renderApp("/pacientes/7", tablaPaciente());
    await screen.findByRole("navigation", { name: "Secciones del paciente" });
    await waitFor(() => expect(router.state.location.pathname).toBe("/pacientes/7/ficha"));
    // la redirección a /ficha no vuelve a pedir la historia (un solo evento de auditoría)
    expect(api.de("GET /api/pacientes/7/historia")).toHaveLength(1);
    await waitFor(() =>
      expect(
        within(screen.getByRole("navigation", { name: "Secciones del paciente" })).getByRole(
          "link",
          { name: "Ficha" },
        ),
      ).toHaveAttribute("aria-current", "page"),
    );
    expect(
      within(screen.getByRole("navigation", { name: "Secciones del paciente" })).getByRole("link", {
        name: "Odontograma",
      }),
    ).toHaveAttribute("href", "/pacientes/7/odontograma");
    expect(
      within(screen.getByRole("navigation", { name: "Secciones del paciente" }))
        .getAllByRole("link")
        .map((l) => l.textContent),
    ).toEqual(["Ficha", "Odontograma", "Evoluciones", "Adjuntos"]);
  });

  it("navegar cambia la URL y la pestaña actual; Atrás vuelve", async () => {
    const { router, api } = renderApp("/pacientes/7/ficha", tablaPaciente());
    await userEvent.click(await screen.findByRole("link", { name: "Odontograma" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/pacientes/7/odontograma"));
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Odontograma" })).toHaveAttribute(
        "aria-current",
        "page",
      ),
    );
    await router.navigate(-1);
    expect(router.state.location.pathname).toBe("/pacientes/7/ficha");
    // cambiar de pestaña no vuelve a pedir la historia (un solo evento de auditoría)
    expect(api.de("GET /api/pacientes/7/historia")).toHaveLength(1);
  });
});

describe("Sin acceso clínico para recepción", () => {
  const tabla = tablaPaciente(
    { "GET /api/pacientes/7/historia": { status: 403, json: { detail: "Rol insuficiente" } } },
    meRecepcion,
  );

  it("la sección de anamnesis muestra Sin acceso clínico sin datos clínicos", async () => {
    renderApp("/pacientes/7/ficha", tabla);
    expect(
      await screen.findByText("Sin acceso clínico: tu rol no permite ver la historia clínica"),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Alergias")).not.toBeInTheDocument();
  });

  it("puede editar el teléfono aunque la anamnesis no sea visible", async () => {
    const { api } = renderApp("/pacientes/7/ficha", {
      ...tabla,
      "PATCH /api/pacientes/7": { json: paciente({ telefono: "+5491100000009" }) },
    });
    const tel = await screen.findByLabelText("Teléfono");
    await userEvent.clear(tel);
    await userEvent.type(tel, "1100000009");
    await userEvent.click(screen.getByRole("button", { name: "Guardar datos" }));
    expect(await screen.findByText("Datos guardados")).toBeInTheDocument();
    expect(api.cuerpo("PATCH /api/pacientes/7")).toEqual({ telefono: "1100000009" });
  });
});

describe("Anamnesis versionada", () => {
  it("versión vigente con número, autor y fecha", async () => {
    renderApp(
      "/pacientes/7/ficha",
      tablaPaciente({ "GET /api/pacientes/7/historia": { json: historia({ ficha: fichaV1 }) } }),
    );
    expect(await screen.findByText(/Versión 1 · Vos · 10\/11\/2026/)).toBeInTheDocument();
    expect(screen.getByLabelText("Alergias")).toHaveValue("Ninguna conocida");
  });

  it("versión 0: el odontólogo guarda con version_esperada 0 y ve Versión 1", async () => {
    const { api } = renderApp(
      "/pacientes/7/ficha",
      tablaPaciente({ "PUT /api/pacientes/7/ficha": { json: { ...fichaV1, version: 1 } } }),
    );
    await userEvent.type(await screen.findByLabelText("Alergias"), "Ninguna conocida");
    await userEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
    expect(await screen.findByText(/Versión 1 · Vos/)).toBeInTheDocument();
    expect(api.cuerpo("PUT /api/pacientes/7/ficha")).toMatchObject({
      version_esperada: 0,
      alergias: "Ninguna conocida",
    });
  });

  it("versión 0 sin poder editar: Sin anamnesis registrada", async () => {
    renderApp("/pacientes/7/ficha", tablaPaciente({}, meAdmin));
    expect(await screen.findByText("Sin anamnesis registrada")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Guardar ficha" })).not.toBeInTheDocument();
  });

  it("409: avisa, conserva lo escrito y recarga solo a pedido", async () => {
    const { api } = renderApp(
      "/pacientes/7/ficha",
      tablaPaciente({
        "PUT /api/pacientes/7/ficha": { status: 409, json: { detail: "Versión desfasada" } },
        "GET /api/pacientes/7/ficha": { json: { ...fichaV1, version: 2, alergias: "Penicilina" } },
      }),
    );
    await userEvent.type(await screen.findByLabelText("Alergias"), "Mi texto");
    await userEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
    expect(await screen.findByText("La ficha cambió mientras la editabas")).toBeInTheDocument();
    expect(screen.getByLabelText("Alergias")).toHaveValue("Mi texto");
    expect(api.de("GET /api/pacientes/7/ficha")).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Recargar versión vigente" }));
    expect(await screen.findByDisplayValue("Penicilina")).toBeInTheDocument();
    expect(screen.queryByText("La ficha cambió mientras la editabas")).not.toBeInTheDocument();
  });

  it("sin consentimiento: escritura deshabilitada con aviso y datos existentes visibles", async () => {
    renderApp(
      "/pacientes/7/ficha",
      tablaPaciente({
        "GET /api/pacientes/7": {
          json: paciente({ consentimiento_datos: false, consentimiento_datos_at: null }),
        },
        "GET /api/pacientes/7/historia": { json: historia({ ficha: fichaV1 }) },
      }),
    );
    expect(await screen.findByLabelText("Alergias")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Guardar ficha" })).toBeDisabled();
    expect(screen.getByLabelText("Alergias")).toHaveValue("Ninguna conocida");
  });

  it("403 de consentimiento al guardar: aviso, conserva y deshabilita", async () => {
    renderApp(
      "/pacientes/7/ficha",
      tablaPaciente({
        "PUT /api/pacientes/7/ficha": { status: 403, json: { detail: CONSENTIMIENTO_FALTANTE } },
      }),
    );
    await userEvent.type(await screen.findByLabelText("Alergias"), "Texto");
    await userEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
    expect(
      (
        await screen.findAllByText(
          "Sin consentimiento de datos: no se pueden cargar datos de salud",
        )
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByLabelText("Alergias")).toHaveValue("Texto");
    expect(screen.getByRole("button", { name: "Guardar ficha" })).toBeDisabled();
  });

  it("otro 403 de escritura muestra el detail del servidor", async () => {
    renderApp(
      "/pacientes/7/ficha",
      tablaPaciente({
        "PUT /api/pacientes/7/ficha": {
          status: 403,
          json: { detail: "Paciente no vinculado al profesional" },
        },
      }),
    );
    await userEvent.type(await screen.findByLabelText("Alergias"), "Texto");
    await userEvent.click(screen.getByRole("button", { name: "Guardar ficha" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Paciente no vinculado al profesional",
    );
  });
});

describe("Historial de versiones de la ficha", () => {
  it("lista 3, 2 y 1 en solo lectura", async () => {
    renderApp(
      "/pacientes/7/ficha",
      tablaPaciente({
        "GET /api/pacientes/7/historia": {
          json: historia({ ficha: { ...fichaV1, version: 3 } }),
        },
        "GET /api/pacientes/7/ficha/versiones": {
          json: [
            { ...fichaV1, version: 3 },
            { ...fichaV1, version: 2, alergias: "Segunda" },
            { ...fichaV1, version: 1, alergias: "Primera" },
          ],
        },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: "Ver versiones anteriores" }));
    const lista = await screen.findByRole("list", { name: "Versiones de la ficha" });
    const items = within(lista).getAllByRole("listitem");
    expect(items.map((i) => /Versión (\d)/.exec(i.textContent ?? "")?.[1])).toEqual([
      "3",
      "2",
      "1",
    ]);
    expect(within(lista).queryByRole("textbox")).not.toBeInTheDocument();
    expect(within(lista).getByText(/Primera/)).toBeInTheDocument();
  });
});
