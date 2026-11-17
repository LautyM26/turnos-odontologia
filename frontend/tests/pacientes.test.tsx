/** Listado, búsqueda, encabezado, datos administrativos y consentimiento (spec patients-web). */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { interpretarBusqueda } from "@/features/clinica/pacientes/busqueda";

import { conSesion, renderApp, tablaPaciente } from "./helpers/app";
import { historia, meOdontologo, meRecepcion, paciente } from "./helpers/fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("interpretarBusqueda", () => {
  it.each([
    ["perez", { tipo: "q", param: "q", valor: "perez" }],
    ["30.123.456", { tipo: "dni", param: "dni", valor: "30.123.456" }],
    ["30123456", { tipo: "dni", param: "dni", valor: "30123456" }],
    ["+5491155550000", { tipo: "telefono", param: "telefono", valor: "+5491155550000" }],
    ["1155550000", { tipo: "telefono", param: "telefono", valor: "1155550000" }],
    ["123456", { tipo: "q", param: "q", valor: "123456" }],
  ])("%s", (texto, esperado) => {
    expect(interpretarBusqueda(texto)).toEqual(esperado);
  });

  it("vacío = todos; menos de 3 caracteres = corta", () => {
    expect(interpretarBusqueda("  ")).toEqual({ tipo: "todos" });
    expect(interpretarBusqueda("pe")).toEqual({ tipo: "corta" });
  });
});

const tres = [
  paciente({ id: 1, nombre: "Demo", apellido: "Uno" }),
  paciente({ id: 2, nombre: "Demo", apellido: "Dos" }),
  paciente({ id: 3, nombre: "Demo", apellido: "Tres" }),
];

describe("PacientesPage", () => {
  it("lista 3 pacientes y cada nombre lleva al detalle", async () => {
    renderApp("/pacientes", {
      ...conSesion(meOdontologo),
      "GET /api/pacientes": { json: { items: tres, next_cursor: null } },
    });
    const enlace = await screen.findByRole("link", { name: /Uno, Demo/ });
    expect(enlace).toHaveAttribute("href", "/pacientes/1");
    expect(screen.getAllByRole("link", { name: /Demo/ })).toHaveLength(3);
  });

  it("Cargar más pide after_id y no repite pacientes", async () => {
    const { api } = renderApp("/pacientes", {
      ...conSesion(meOdontologo),
      "GET /api/pacientes": (c) =>
        c.url.includes("after_id=2")
          ? { json: { items: [tres[1], tres[2]], next_cursor: null } }
          : { json: { items: [tres[0], tres[1]], next_cursor: 2 } },
    });
    await screen.findByRole("link", { name: /Uno, Demo/ });
    await userEvent.click(screen.getByRole("button", { name: "Cargar más" }));
    await screen.findByRole("link", { name: /Tres, Demo/ });
    expect(screen.getAllByRole("link", { name: /Demo/ })).toHaveLength(3);
    expect(api.llamadas.at(-1)?.url).toContain("after_id=2");
    expect(screen.queryByRole("button", { name: "Cargar más" })).not.toBeInTheDocument();
  });

  it("clínica sin pacientes: estado vacío", async () => {
    renderApp("/pacientes", {
      ...conSesion(meOdontologo),
      "GET /api/pacientes": { json: { items: [], next_cursor: null } },
    });
    expect(await screen.findByText(/Todavía no hay pacientes cargados/)).toBeInTheDocument();
  });

  it("error 500: mensaje con Reintentar, que vuelve a pedir", async () => {
    let n = 0;
    const { api } = renderApp("/pacientes", {
      ...conSesion(meOdontologo),
      "GET /api/pacientes": () => {
        n++;
        return n === 1
          ? { status: 500, json: { detail: "Error interno" } }
          : { json: { items: tres, next_cursor: null } };
      },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Error interno");
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    await screen.findByRole("link", { name: /Uno, Demo/ });
    expect(api.de("GET /api/pacientes")).toHaveLength(2);
  });

  it("búsqueda por apellido envía q y se refleja en la URL", async () => {
    const { api, router } = renderApp("/pacientes", {
      ...conSesion(meOdontologo),
      "GET /api/pacientes": { json: { items: tres, next_cursor: null } },
    });
    await screen.findByRole("link", { name: /Uno, Demo/ });
    await userEvent.type(screen.getByLabelText("Buscar paciente"), "perez{Enter}");
    await waitFor(() => expect(api.llamadas.at(-1)?.url).toContain("q=perez"));
    expect(router.state.location.search).toBe("?buscar=perez");
  });

  it("búsqueda por DNI con puntos envía dni", async () => {
    const { api } = renderApp("/pacientes", {
      ...conSesion(meOdontologo),
      "GET /api/pacientes": { json: { items: tres, next_cursor: null } },
    });
    await screen.findByRole("link", { name: /Uno, Demo/ });
    await userEvent.type(screen.getByLabelText("Buscar paciente"), "30.123.456{Enter}");
    await waitFor(() => expect(api.llamadas.at(-1)?.url).toContain("dni=30.123.456"));
  });

  it("texto demasiado corto no envía y explica", async () => {
    const { api } = renderApp("/pacientes?buscar=pe", {
      ...conSesion(meOdontologo),
      "GET /api/pacientes": { json: { items: tres, next_cursor: null } },
    });
    expect(await screen.findByText(/al menos 3 caracteres/)).toBeInTheDocument();
    expect(api.de("GET /api/pacientes")).toHaveLength(0);
  });

  it("sin resultados: mensaje con el texto y forma de limpiar", async () => {
    renderApp("/pacientes?buscar=zzz", {
      ...conSesion(meOdontologo),
      "GET /api/pacientes": { json: { items: [], next_cursor: null } },
    });
    expect(await screen.findByText("No hay pacientes que coincidan con «zzz»")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Limpiar búsqueda" })).toHaveAttribute(
      "href",
      "/pacientes",
    );
  });
});

describe("PacienteLayout", () => {
  it("las 3 requests salen antes de que termine cualquiera (paralelo)", async () => {
    let liberar: () => void = () => undefined;
    const puerta = new Promise<void>((r) => {
      liberar = r;
    });
    const { api } = renderApp(
      "/pacientes/7",
      tablaPaciente({
        "GET /api/pacientes/7": async () => {
          await puerta;
          return { json: paciente() };
        },
        "GET /api/pacientes/7/historia": async () => {
          await puerta;
          return { json: historia() };
        },
        "GET /api/catalogo/profesionales": async () => {
          await puerta;
          return { json: { items: [], next_cursor: null } };
        },
      }),
    );
    await waitFor(() => {
      expect(api.de("GET /api/pacientes/7")).toHaveLength(1);
      expect(api.de("GET /api/pacientes/7/historia")).toHaveLength(1);
      expect(api.de("GET /api/catalogo/profesionales")).toHaveLength(1);
    });
    liberar();
    expect(await screen.findByRole("heading", { name: /Sintético Uno, Demo/ })).toBeInTheDocument();
  });

  it("historia 500: el encabezado se muestra y la sección clínica ofrece Reintentar", async () => {
    renderApp(
      "/pacientes/7",
      tablaPaciente({ "GET /api/pacientes/7/historia": { status: 500, json: { detail: "boom" } } }),
    );
    expect(await screen.findByRole("heading", { name: /Sintético Uno, Demo/ })).toBeInTheDocument();
    expect(await screen.findByLabelText("Teléfono")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("paciente 404: Paciente no encontrado, sin pestañas, con enlace de vuelta", async () => {
    renderApp(
      "/pacientes/7",
      tablaPaciente({ "GET /api/pacientes/7": { status: 404, json: { detail: "no" } } }),
    );
    expect(await screen.findByText("Paciente no encontrado")).toBeInTheDocument();
    expect(
      screen.queryByRole("navigation", { name: "Secciones del paciente" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver a pacientes" })).toHaveAttribute(
      "href",
      "/pacientes",
    );
  });

  it("encabezado: datos y consentimiento otorgado con fecha", async () => {
    renderApp("/pacientes/7", tablaPaciente());
    const cab = await screen.findByRole("region", { name: "Paciente" });
    expect(within(cab).getByText(/99000001/)).toBeInTheDocument();
    expect(within(cab).getByText(/OS Ficticia/)).toBeInTheDocument();
    expect(within(cab).getByText(/Consentimiento de datos: otorgado/)).toHaveTextContent(
      "01/11/2026",
    );
  });

  it("encabezado: sin consentimiento muestra el aviso visible", async () => {
    renderApp(
      "/pacientes/7",
      tablaPaciente({
        "GET /api/pacientes/7": {
          json: paciente({ consentimiento_datos: false, consentimiento_datos_at: null }),
        },
      }),
    );
    const cab = await screen.findByRole("region", { name: "Paciente" });
    expect(within(cab).getByText(/Consentimiento de datos: no otorgado/)).toBeInTheDocument();
    expect(
      within(cab).getByText("Sin consentimiento de datos: no se pueden cargar datos de salud"),
    ).toBeInTheDocument();
  });
});

describe("Datos del paciente", () => {
  it("cambia solo el teléfono: PATCH parcial, valor normalizado y Datos guardados", async () => {
    const { api } = renderApp(
      "/pacientes/7",
      tablaPaciente(
        { "PATCH /api/pacientes/7": { json: paciente({ telefono: "+5491199998888" }) } },
        meRecepcion,
      ),
    );
    const tel = await screen.findByLabelText("Teléfono");
    await userEvent.clear(tel);
    await userEvent.type(tel, "1199998888");
    await userEvent.click(screen.getByRole("button", { name: "Guardar datos" }));
    expect(await screen.findByText("Datos guardados")).toBeInTheDocument();
    expect(api.cuerpo("PATCH /api/pacientes/7")).toEqual({ telefono: "1199998888" });
    expect(screen.getByLabelText("Teléfono")).toHaveValue("+5491199998888");
  });

  it("409 muestra el mensaje junto al formulario y conserva lo escrito", async () => {
    renderApp(
      "/pacientes/7",
      tablaPaciente({
        "PATCH /api/pacientes/7": { status: 409, json: { detail: "DNI duplicado" } },
      }),
    );
    const dni = await screen.findByLabelText("DNI");
    await userEvent.clear(dni);
    await userEvent.type(dni, "99000002");
    await userEvent.click(screen.getByRole("button", { name: "Guardar datos" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("DNI duplicado");
    expect(screen.getByLabelText("DNI")).toHaveValue("99000002");
    expect(screen.queryByText("Datos guardados")).not.toBeInTheDocument();
  });

  it("nombre vacío: indica obligatorio y no envía", async () => {
    const { api } = renderApp("/pacientes/7", tablaPaciente());
    const nombre = await screen.findByLabelText("Nombre");
    await userEvent.clear(nombre);
    await userEvent.click(screen.getByRole("button", { name: "Guardar datos" }));
    expect(await screen.findByText("El nombre es obligatorio")).toBeInTheDocument();
    expect(api.de("PATCH /api/pacientes/7")).toHaveLength(0);
  });

  it("riesgo de ausencia solo lectura y nunca enviado", async () => {
    const { api } = renderApp(
      "/pacientes/7",
      tablaPaciente({
        "PATCH /api/pacientes/7": { json: paciente({ email: "otro@ejemplo.test" }) },
      }),
    );
    expect(await screen.findByText(/Riesgo de ausencia: 20/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/riesgo/i)).not.toBeInTheDocument();
    const email = screen.getByLabelText("Email");
    await userEvent.clear(email);
    await userEvent.type(email, "otro@ejemplo.test");
    await userEvent.click(screen.getByRole("button", { name: "Guardar datos" }));
    await screen.findByText("Datos guardados");
    expect(Object.keys(api.cuerpo("PATCH /api/pacientes/7") as object)).toEqual(["email"]);
  });
});

describe("Consentimiento de datos", () => {
  const sinConsent = paciente({ consentimiento_datos: false, consentimiento_datos_at: null });
  const AVISO = "Sin consentimiento de datos: no se pueden cargar datos de salud";

  it("otorgar con confirmación actualiza el encabezado", async () => {
    const { api } = renderApp(
      "/pacientes/7",
      tablaPaciente({
        "GET /api/pacientes/7": { json: sinConsent },
        "PATCH /api/pacientes/7": { json: paciente() },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: "Registrar consentimiento" }));
    const dialogo = screen.getByRole("dialog");
    expect(dialogo).toHaveTextContent(/datos de salud/);
    await userEvent.click(
      within(dialogo).getByRole("button", { name: "Registrar consentimiento" }),
    );
    await waitFor(() =>
      expect(api.cuerpo("PATCH /api/pacientes/7")).toEqual({ consentimiento_datos: true }),
    );
    await waitFor(() => expect(screen.queryByText(AVISO)).not.toBeInTheDocument());
  });

  it("cancelar no envía nada", async () => {
    const { api } = renderApp(
      "/pacientes/7",
      tablaPaciente({ "GET /api/pacientes/7": { json: sinConsent } }),
    );
    await userEvent.click(await screen.findByRole("button", { name: "Registrar consentimiento" }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Cancelar" }),
    );
    expect(api.de("PATCH /api/pacientes/7")).toHaveLength(0);
    expect(screen.getAllByText(AVISO).length).toBeGreaterThan(0);
  });

  it("revocar explica que no borra lo existente", async () => {
    renderApp("/pacientes/7", tablaPaciente());
    await userEvent.click(await screen.findByRole("button", { name: "Revocar consentimiento" }));
    expect(screen.getByRole("dialog")).toHaveTextContent(/sin borrar/);
  });
});
