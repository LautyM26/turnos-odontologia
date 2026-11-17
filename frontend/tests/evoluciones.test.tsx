/** Timeline, alta, corrección y cadena de evoluciones (spec evolutions-web). */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CONSENTIMIENTO_FALTANTE } from "@/shared/api/resultado";

import { renderApp, tablaPaciente } from "./helpers/app";
import { evolucion, historia, meAdmin, meRecepcion, paciente } from "./helpers/fixtures";

afterEach(() => vi.unstubAllGlobals());

const RUTA = "/pacientes/7/evoluciones";
const E1 = evolucion({
  id: 1,
  texto: "Primera evolución sintética",
  fecha_hora: "2026-11-08T15:30:00Z",
});
const E2 = evolucion({
  id: 2,
  texto: "Segunda evolución sintética",
  fecha_hora: "2026-11-09T15:30:00Z",
  pieza_fdi: 16,
});
const E3 = evolucion({
  id: 3,
  texto: "Tercera evolución sintética",
  fecha_hora: "2026-11-10T15:30:00Z",
  autor_usuario_id: 20,
  profesional_id: 2,
});

const conEvos = (
  evoluciones: ReturnType<typeof evolucion>[],
  extra = {},
  next_cursor: number | null = null,
) =>
  tablaPaciente({
    "GET /api/pacientes/7/historia": { json: historia({ evoluciones, next_cursor }) },
    ...extra,
  });

const articulos = () => screen.getAllByRole("article");

describe("Historia sin edición ni borrado (auditoría del fuente)", () => {
  it("el código de evoluciones no usa PUT, PATCH ni DELETE", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const dir = path.resolve(import.meta.dirname, "../src/features/clinica/evoluciones");
    const fuente = fs
      .readdirSync(dir)
      .map((f) => fs.readFileSync(path.join(dir, f), "utf-8"))
      .join("\n");
    expect(fuente).not.toMatch(/\b(PUT|PATCH|DELETE)\b/);
    expect(fuente).toMatch(/POST/);
  });
});

describe("Timeline", () => {
  it("más reciente primero, con profesional, fecha AR y pieza", async () => {
    renderApp(RUTA, conEvos([E1, E2, E3]));
    await screen.findByText("Tercera evolución sintética");
    const textos = articulos().map((a) => a.textContent ?? "");
    expect(textos[0]).toContain("Tercera");
    expect(textos[1]).toContain("Segunda");
    expect(textos[2]).toContain("Primera");
    expect(textos[0]).toContain("Profesional Demo Dos");
    expect(textos[0]).toContain("10/11/2026");
    expect(textos[1]).toContain("Pieza 16");
  });

  it("Cargar anteriores pide after_id y no repite", async () => {
    const { api } = renderApp(
      RUTA,
      conEvos(
        [E3, E2],
        {
          "GET /api/pacientes/7/evoluciones": {
            json: { items: [E2, E1], next_cursor: null },
          },
        },
        2,
      ),
    );
    await userEvent.click(await screen.findByRole("button", { name: "Cargar anteriores" }));
    await screen.findByText("Primera evolución sintética");
    expect(articulos()).toHaveLength(3);
    expect(api.llamadas.at(-1)?.url).toContain("after_id=2");
    expect(screen.queryByRole("button", { name: "Cargar anteriores" })).not.toBeInTheDocument();
  });

  it("sin evoluciones", async () => {
    renderApp(RUTA, conEvos([]));
    expect(await screen.findByText("Todavía no hay evoluciones registradas")).toBeInTheDocument();
  });

  it("solo Corregir sobre evoluciones propias: nunca Editar ni Eliminar", async () => {
    renderApp(RUTA, conEvos([E3, E1]));
    await screen.findByText("Primera evolución sintética");
    expect(screen.getAllByRole("button", { name: "Corregir" })).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: /editar|eliminar|borrar/i }),
    ).not.toBeInTheDocument();
  });

  it("deep link a la pestaña", async () => {
    const { router } = renderApp(RUTA, conEvos([E1]));
    expect(await screen.findByRole("heading", { name: "Evoluciones" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(RUTA);
  });
});

describe("Alta de evolución", () => {
  const nueva = evolucion({ id: 9, texto: "Control sintético, sin hallazgos", pieza_fdi: 16 });

  it("envía solo texto y pieza_fdi; la nueva aparece primera y el formulario se vacía", async () => {
    const { api } = renderApp(
      RUTA,
      conEvos([E1], { "POST /api/pacientes/7/evoluciones": { status: 201, json: nueva } }),
    );
    await userEvent.type(
      await screen.findByLabelText("Texto de la evolución"),
      "Control sintético, sin hallazgos",
    );
    await userEvent.selectOptions(screen.getByLabelText("Pieza FDI (opcional)"), "16");
    await userEvent.click(screen.getByRole("button", { name: "Guardar evolución" }));
    await waitFor(() =>
      expect(articulos()[0]).toHaveTextContent("Control sintético, sin hallazgos"),
    );
    expect(api.cuerpo("POST /api/pacientes/7/evoluciones")).toEqual({
      texto: "Control sintético, sin hallazgos",
      pieza_fdi: 16,
    });
    expect(screen.getByLabelText("Texto de la evolución")).toHaveValue("");
    expect(articulos()).toHaveLength(2);
  });

  it("contador de caracteres", async () => {
    renderApp(RUTA, conEvos([]));
    await userEvent.type(await screen.findByLabelText("Texto de la evolución"), "abc");
    expect(screen.getByText("3 / 10000")).toBeInTheDocument();
  });

  it("texto vacío o solo espacios: Escribí la evolución, sin request", async () => {
    const { api } = renderApp(RUTA, conEvos([]));
    await userEvent.type(await screen.findByLabelText("Texto de la evolución"), "   ");
    await userEvent.click(screen.getByRole("button", { name: "Guardar evolución" }));
    expect(await screen.findByText("Escribí la evolución")).toBeInTheDocument();
    expect(api.de("POST /api/pacientes/7/evoluciones")).toHaveLength(0);
  });

  it("422 (sin profesional vinculado): muestra el motivo y conserva el texto", async () => {
    renderApp(
      RUTA,
      conEvos([], {
        "POST /api/pacientes/7/evoluciones": {
          status: 422,
          json: { detail: "El odontólogo no tiene un profesional vinculado" },
        },
      }),
    );
    await userEvent.type(await screen.findByLabelText("Texto de la evolución"), "Mi texto");
    await userEvent.click(screen.getByRole("button", { name: "Guardar evolución" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("no tiene un profesional vinculado");
    expect(screen.getByLabelText("Texto de la evolución")).toHaveValue("Mi texto");
  });

  it("doble clic envía una sola request", async () => {
    const { api } = renderApp(
      RUTA,
      conEvos([], {
        "POST /api/pacientes/7/evoluciones": async () => {
          await new Promise((r) => setTimeout(r, 30));
          return { status: 201, json: nueva };
        },
      }),
    );
    await userEvent.type(await screen.findByLabelText("Texto de la evolución"), "Algo");
    await userEvent.dblClick(screen.getByRole("button", { name: "Guardar evolución" }));
    await waitFor(() => expect(articulos()).toHaveLength(1));
    expect(api.de("POST /api/pacientes/7/evoluciones")).toHaveLength(1);
  });

  it("403 de consentimiento: aviso, conserva el texto y deshabilita", async () => {
    renderApp(
      RUTA,
      conEvos([], {
        "POST /api/pacientes/7/evoluciones": {
          status: 403,
          json: { detail: CONSENTIMIENTO_FALTANTE },
        },
      }),
    );
    await userEvent.type(await screen.findByLabelText("Texto de la evolución"), "Texto");
    await userEvent.click(screen.getByRole("button", { name: "Guardar evolución" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Guardar evolución" })).toBeDisabled(),
    );
    expect(screen.getByLabelText("Texto de la evolución")).toHaveValue("Texto");
    expect(
      screen.getAllByText("Sin consentimiento de datos: no se pueden cargar datos de salud").length,
    ).toBeGreaterThan(0);
  });

  it("sin consentimiento: formulario deshabilitado y evoluciones existentes visibles", async () => {
    renderApp(
      RUTA,
      conEvos([E1], {
        "GET /api/pacientes/7": {
          json: paciente({ consentimiento_datos: false, consentimiento_datos_at: null }),
        },
      }),
    );
    expect(await screen.findByText("Primera evolución sintética")).toBeInTheDocument();
    expect(screen.getByLabelText("Texto de la evolución")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Guardar evolución" })).toBeDisabled();
  });
});

describe("Lectura sin escritura", () => {
  it("admin: timeline sin formulario ni Corregir", async () => {
    renderApp(
      RUTA,
      tablaPaciente(
        { "GET /api/pacientes/7/historia": { json: historia({ evoluciones: [E1] }) } },
        meAdmin,
      ),
    );
    await screen.findByText("Primera evolución sintética");
    expect(screen.queryByLabelText("Texto de la evolución")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Corregir" })).not.toBeInTheDocument();
  });

  it("recepción: Sin acceso clínico y ninguna evolución", async () => {
    renderApp(
      RUTA,
      tablaPaciente(
        { "GET /api/pacientes/7/historia": { status: 403, json: { detail: "Rol insuficiente" } } },
        meRecepcion,
      ),
    );
    expect(
      await screen.findByText("Sin acceso clínico: tu rol no permite ver la historia clínica"),
    ).toBeInTheDocument();
    expect(screen.queryAllByRole("article")).toHaveLength(0);
  });
});

describe("Corrección como evolución nueva", () => {
  const correccion = evolucion({
    id: 10,
    texto: "Texto corregido sintético",
    corrige_a_id: 1,
    motivo_correccion: "Pieza mal indicada",
    fecha_hora: "2026-11-12T15:30:00Z",
  });

  async function abrirCorreccion() {
    await userEvent.click(await screen.findByRole("button", { name: "Corregir" }));
    return screen.getByRole("form", { name: "Corregir evolución" });
  }

  it("parte del texto original; el autor corrige y la timeline tiene una entrada más", async () => {
    const { api } = renderApp(
      RUTA,
      conEvos([E1], { "POST /api/pacientes/7/evoluciones": { status: 201, json: correccion } }),
    );
    const form = await abrirCorreccion();
    const texto = within(form).getByLabelText("Texto de la evolución");
    expect(texto).toHaveValue("Primera evolución sintética");
    await userEvent.clear(texto);
    await userEvent.type(texto, "Texto corregido sintético");
    await userEvent.type(
      within(form).getByLabelText("Motivo de la corrección"),
      "Pieza mal indicada",
    );
    await userEvent.click(within(form).getByRole("button", { name: "Guardar corrección" }));
    await waitFor(() => expect(articulos()).toHaveLength(2));
    expect(api.cuerpo("POST /api/pacientes/7/evoluciones")).toEqual({
      texto: "Texto corregido sintético",
      corrige_a_id: 1,
      motivo_correccion: "Pieza mal indicada",
    });
    const [nueva, original] = articulos();
    expect(nueva).toHaveTextContent(/Corrige a la evolución del 08\/11\/2026/);
    expect(nueva).toHaveTextContent("Pieza mal indicada");
    expect(original).toHaveTextContent("Primera evolución sintética");
    expect(original).toHaveTextContent("Corregida");
    expect(
      within(original as HTMLElement).queryByRole("button", { name: "Corregir" }),
    ).not.toBeInTheDocument();
    expect(
      within(nueva as HTMLElement).getByRole("button", { name: "Corregir" }),
    ).toBeInTheDocument();
  });

  it("sin motivo: Indicá el motivo de la corrección, sin request", async () => {
    const { api } = renderApp(RUTA, conEvos([E1]));
    const form = await abrirCorreccion();
    await userEvent.click(within(form).getByRole("button", { name: "Guardar corrección" }));
    expect(await screen.findByText("Indicá el motivo de la corrección")).toBeInTheDocument();
    expect(api.de("POST /api/pacientes/7/evoluciones")).toHaveLength(0);
  });

  it("409: avisa que ya fue corregida, recarga la timeline y ofrece corregir la vigente", async () => {
    const { api } = renderApp(
      RUTA,
      conEvos([E1], {
        "POST /api/pacientes/7/evoluciones": { status: 409, json: { detail: "ya corregida" } },
        "GET /api/pacientes/7/evoluciones": {
          json: {
            items: [
              { ...correccion, id: 10 },
              { ...E1, corregida_por_id: 10 },
            ],
            next_cursor: null,
          },
        },
      }),
    );
    const form = await abrirCorreccion();
    await userEvent.type(within(form).getByLabelText("Motivo de la corrección"), "Motivo");
    await userEvent.click(within(form).getByRole("button", { name: "Guardar corrección" }));
    expect(await screen.findByText(/Esa evolución ya fue corregida/)).toBeInTheDocument();
    await waitFor(() => expect(articulos()).toHaveLength(2));
    expect(api.llamadas.at(-1)?.url).toContain("/evoluciones");
    expect(screen.getAllByRole("button", { name: "Corregir" })).toHaveLength(1);
  });

  it("evolución de otro profesional o ya corregida no tiene Corregir", async () => {
    renderApp(RUTA, conEvos([correccion, { ...E1, corregida_por_id: 10 }, E3]));
    await screen.findByText("Tercera evolución sintética");
    expect(screen.getAllByRole("button", { name: "Corregir" })).toHaveLength(1);
    const e3 = articulos().find((a) => a.textContent?.includes("Tercera")) as HTMLElement;
    expect(within(e3).queryByRole("button", { name: "Corregir" })).not.toBeInTheDocument();
  });
});

describe("Cadena de correcciones", () => {
  it("Ver corrección lleva el foco a la evolución destino", async () => {
    const e3corr = evolucion({
      id: 3,
      texto: "Corrección",
      corrige_a_id: 1,
      motivo_correccion: "m",
    });
    renderApp(RUTA, conEvos([e3corr, { ...E1, corregida_por_id: 3 }]));
    await userEvent.click(await screen.findByRole("button", { name: "Ver corrección" }));
    expect(document.getElementById("evolucion-3")).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: /Corrige a la evolución/ }));
    expect(document.getElementById("evolucion-1")).toHaveFocus();
  });
});
