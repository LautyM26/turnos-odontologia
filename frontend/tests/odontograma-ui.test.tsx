/** Odontograma en el navegador (spec odontogram-web + acceso clínico). */

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Odontograma } from "@/features/clinica/tipos";

import { renderApp, tablaPaciente } from "./helpers/app";
import { historia, meAdmin, meRecepcion, odontograma, paciente } from "./helpers/fixtures";

afterEach(() => vi.unstubAllGlobals());

const RUTA = "/pacientes/7/odontograma";
const piezasBtn = () => screen.getAllByRole("button", { name: /^Pieza \d{2}\b/ });
const cara = (pieza: number, c: string) =>
  document.querySelector(`#pieza-${pieza} [data-cara="${c}"]`) as Element;

const v1: Odontograma = odontograma({
  id: 5,
  version: 1,
  denticion: "permanente",
  piezas: {
    "36": {
      caras: {
        M: { codigo: "caries", registro: "a_realizar" },
        O: { codigo: "obturacion", registro: "existente" },
      },
    },
  },
  autor_usuario_id: 10,
  created_at: "2026-11-10T15:30:00Z",
});

const conOdonto = (o: Odontograma, extra = {}) =>
  tablaPaciente({
    "GET /api/pacientes/7/historia": { json: historia({ odontograma: o }) },
    ...extra,
  });

describe("Piezas según la dentición", () => {
  it("permanente: 32 piezas, de la 18 a la 28 arriba y de la 48 a la 38 abajo", async () => {
    renderApp(RUTA, conOdonto(v1));
    await screen.findByRole("button", { name: /^Pieza 18/ });
    const botones = piezasBtn();
    expect(botones).toHaveLength(32);
    expect(botones[0]).toHaveAccessibleName(/^Pieza 18/);
    expect(botones[15]).toHaveAccessibleName(/^Pieza 28/);
    expect(botones[16]).toHaveAccessibleName(/^Pieza 48/);
    expect(botones[31]).toHaveAccessibleName(/^Pieza 38/);
  });

  it("temporal: 20 piezas", async () => {
    renderApp(RUTA, conOdonto({ ...v1, denticion: "temporal", piezas: {} }));
    await screen.findByRole("button", { name: /^Pieza 55/ });
    expect(piezasBtn()).toHaveLength(20);
  });

  it("mixta: 52 piezas", async () => {
    renderApp(RUTA, conOdonto({ ...v1, denticion: "mixta", piezas: {} }));
    await screen.findByRole("button", { name: /^Pieza 55/ });
    expect(piezasBtn()).toHaveLength(52);
  });

  it("versión 0: permanente vacía y el texto de sin odontograma", async () => {
    renderApp(RUTA, conOdonto(odontograma()));
    expect(await screen.findByText("Sin odontograma registrado todavía")).toBeInTheDocument();
    expect(piezasBtn()).toHaveLength(32);
  });
});

describe("Accesibilidad y lectura sin color", () => {
  it("nombre accesible con número y marcas; leyenda y tabla de hallazgos", async () => {
    renderApp(RUTA, conOdonto(v1));
    const p36 = await screen.findByRole("button", { name: /^Pieza 36/ });
    expect(p36).toHaveAccessibleName("Pieza 36: caries a realizar en M, obturación existente en O");
    expect(screen.getByRole("group", { name: "Leyenda" })).toBeInTheDocument();
    const tabla = screen.getByRole("table", { name: "Hallazgos" });
    expect(within(tabla).getByText("36 · M · Caries · A realizar")).toBeInTheDocument();
    expect(within(tabla).getByText("36 · O · Obturación · Existente")).toBeInTheDocument();
  });

  it("Enter en la pieza abre el panel con foco en su primer control; Escape devuelve el foco", async () => {
    renderApp(RUTA, conOdonto(v1));
    const p36 = await screen.findByRole("button", { name: /^Pieza 36/ });
    p36.focus();
    await userEvent.keyboard("{Enter}");
    const panel = await screen.findByRole("dialog", { name: "Pieza 36" });
    expect(within(panel).getByLabelText("Estado de la pieza")).toHaveFocus();
    fireEvent(panel, new Event("cancel", { cancelable: true }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: /^Pieza 36/ })).toHaveFocus();
  });
});

describe("Marcado por pieza y por cara", () => {
  it("clic en la cara oclusal abre el panel con esa cara; caries a realizar queda en el borrador", async () => {
    renderApp(RUTA, conOdonto(odontograma()));
    await screen.findByRole("button", { name: /^Pieza 16/ });
    await userEvent.click(cara(16, "O"));
    const panel = await screen.findByRole("dialog", { name: "Pieza 16" });
    expect(within(panel).getByLabelText("Cara O")).toHaveFocus();
    await userEvent.selectOptions(within(panel).getByLabelText("Cara O"), "caries");
    await userEvent.selectOptions(
      within(panel).getByLabelText("Registro de la cara O"),
      "a_realizar",
    );
    await userEvent.click(within(panel).getByRole("button", { name: "Listo" }));
    expect(screen.getByRole("button", { name: /^Pieza 16/ })).toHaveAccessibleName(
      "Pieza 16: caries a realizar en O",
    );
    expect(screen.getByText("Cambios sin guardar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar odontograma" })).toBeEnabled();
  });

  it("pieza ausente con caras marcadas pide confirmación y las quita", async () => {
    renderApp(
      RUTA,
      conOdonto({
        ...v1,
        piezas: { "26": { caras: { O: { codigo: "obturacion", registro: "existente" } } } },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: /^Pieza 26/ }));
    const panel = await screen.findByRole("dialog", { name: "Pieza 26" });
    await userEvent.selectOptions(within(panel).getByLabelText("Estado de la pieza"), "ausente");
    const confirmar = await screen.findByRole("dialog", { name: "Quitar marcas de las caras" });
    expect(confirmar).toHaveTextContent(/Se quitarán las marcas de las caras/);
    await userEvent.click(within(confirmar).getByRole("button", { name: "Marcar ausente" }));
    await userEvent.click(within(panel).getByRole("button", { name: "Listo" }));
    expect(screen.getByRole("button", { name: /^Pieza 26/ })).toHaveAccessibleName(
      "Pieza 26: ausente",
    );
  });

  it("cancelar la confirmación deja la pieza como estaba", async () => {
    renderApp(
      RUTA,
      conOdonto({
        ...v1,
        piezas: { "26": { caras: { O: { codigo: "obturacion", registro: "existente" } } } },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: /^Pieza 26/ }));
    const panel = await screen.findByRole("dialog", { name: "Pieza 26" });
    await userEvent.selectOptions(within(panel).getByLabelText("Estado de la pieza"), "ausente");
    const confirmar = await screen.findByRole("dialog", { name: "Quitar marcas de las caras" });
    await userEvent.click(within(confirmar).getByRole("button", { name: "Cancelar" }));
    expect(within(panel).getByLabelText("Estado de la pieza")).toHaveValue("");
    expect(within(panel).getByLabelText("Cara O")).toHaveValue("obturacion");
  });

  it("Sin marca quita la marca y la pieza vacía deja de enviarse", async () => {
    const { api } = renderApp(
      RUTA,
      conOdonto(
        { ...v1, piezas: { "16": { caras: { O: { codigo: "caries", registro: "existente" } } } } },
        {
          "POST /api/pacientes/7/odontograma": {
            status: 201,
            json: { ...v1, version: 2, piezas: {} },
          },
        },
      ),
    );
    await userEvent.click(await screen.findByRole("button", { name: /^Pieza 16/ }));
    const panel = await screen.findByRole("dialog", { name: "Pieza 16" });
    await userEvent.selectOptions(within(panel).getByLabelText("Cara O"), "");
    await userEvent.click(within(panel).getByRole("button", { name: "Listo" }));
    expect(screen.getByRole("button", { name: /^Pieza 16/ })).toHaveAccessibleName("Pieza 16");
    await userEvent.click(screen.getByRole("button", { name: "Guardar odontograma" }));
    await screen.findByText(/Versión 2/);
    expect((api.cuerpo("POST /api/pacientes/7/odontograma") as { piezas: object }).piezas).toEqual(
      {},
    );
  });
});

describe("Selector de dentición", () => {
  it("sin marcas afectadas cambia sin confirmar", async () => {
    renderApp(RUTA, conOdonto(odontograma()));
    await screen.findByRole("button", { name: /^Pieza 16/ });
    await userEvent.selectOptions(screen.getByLabelText("Dentición"), "temporal");
    expect(piezasBtn()).toHaveLength(20);
  });

  it("descarta marcas solo si confirma y conserva las demás", async () => {
    renderApp(
      RUTA,
      conOdonto({
        ...v1,
        denticion: "mixta",
        piezas: {
          "16": { caras: { O: { codigo: "caries", registro: "existente" } } },
          "55": { caras: { O: { codigo: "caries", registro: "existente" } } },
        },
      }),
    );
    await screen.findByRole("button", { name: /^Pieza 55/ });
    await userEvent.selectOptions(screen.getByLabelText("Dentición"), "permanente");
    const dialogo = await screen.findByRole("dialog", { name: "Cambiar la dentición" });
    expect(dialogo).toHaveTextContent("la marca de la pieza 55");
    await userEvent.click(within(dialogo).getByRole("button", { name: "Cambiar dentición" }));
    expect(piezasBtn()).toHaveLength(32);
    expect(screen.getByRole("button", { name: /^Pieza 16/ })).toHaveAccessibleName(
      "Pieza 16: caries existente en O",
    );
  });
});

describe("Guardado como versión nueva", () => {
  const marcar16 = async () => {
    await userEvent.click(await screen.findByRole("button", { name: /^Pieza 16/ }));
    const panel = await screen.findByRole("dialog", { name: "Pieza 16" });
    await userEvent.selectOptions(within(panel).getByLabelText("Cara O"), "caries");
    await userEvent.click(within(panel).getByRole("button", { name: "Listo" }));
  };

  it("envía version_esperada y muestra la versión nueva sin cambios pendientes", async () => {
    const guardada = {
      ...v1,
      id: 6,
      version: 2,
      piezas: { ...v1.piezas, "16": { caras: { O: { codigo: "caries", registro: "existente" } } } },
      created_at: "2026-11-11T15:00:00Z",
    };
    const { api } = renderApp(
      RUTA,
      conOdonto(v1, { "POST /api/pacientes/7/odontograma": { status: 201, json: guardada } }),
    );
    await marcar16();
    await userEvent.click(screen.getByRole("button", { name: "Guardar odontograma" }));
    expect(
      await screen.findByText(/Versión 2 · guardada por Vos el 11\/11\/2026/),
    ).toBeInTheDocument();
    expect(api.cuerpo("POST /api/pacientes/7/odontograma")).toMatchObject({
      version_esperada: 1,
      denticion: "permanente",
    });
    expect(screen.getByRole("button", { name: "Guardar odontograma" })).toBeDisabled();
  });

  it("sin cambios Guardar está deshabilitado", async () => {
    renderApp(RUTA, conOdonto(v1));
    await screen.findByRole("button", { name: /^Pieza 16/ });
    expect(screen.getByRole("button", { name: "Guardar odontograma" })).toBeDisabled();
  });

  it("422 muestra el motivo y conserva el borrador", async () => {
    renderApp(
      RUTA,
      conOdonto(v1, {
        "POST /api/pacientes/7/odontograma": { status: 422, json: { detail: "Pieza 99 inválida" } },
      }),
    );
    await marcar16();
    await userEvent.click(screen.getByRole("button", { name: "Guardar odontograma" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Pieza 99 inválida");
    expect(screen.getByRole("button", { name: /^Pieza 16/ })).toHaveAccessibleName(
      "Pieza 16: caries existente en O",
    );
  });

  it("doble clic en Guardar envía una sola request", async () => {
    const { api } = renderApp(
      RUTA,
      conOdonto(v1, {
        "POST /api/pacientes/7/odontograma": async () => {
          await new Promise((r) => setTimeout(r, 30));
          return { status: 201, json: { ...v1, version: 2 } };
        },
      }),
    );
    await marcar16();
    await userEvent.dblClick(screen.getByRole("button", { name: "Guardar odontograma" }));
    await screen.findByText(/Versión 2/);
    expect(api.de("POST /api/pacientes/7/odontograma")).toHaveLength(1);
  });
});

describe("Conflicto de versión", () => {
  it("409 conserva el borrador; Recargar versión vigente (con confirmación) carga la 2", async () => {
    const v2 = { ...v1, id: 6, version: 2, piezas: {} };
    const { api } = renderApp(
      RUTA,
      conOdonto(v1, {
        "POST /api/pacientes/7/odontograma": { status: 409, json: { detail: "desfasada" } },
        "GET /api/pacientes/7/odontograma/actual": { json: v2 },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: /^Pieza 16/ }));
    const panel = await screen.findByRole("dialog", { name: "Pieza 16" });
    await userEvent.selectOptions(within(panel).getByLabelText("Cara O"), "caries");
    await userEvent.click(within(panel).getByRole("button", { name: "Listo" }));
    await userEvent.click(screen.getByRole("button", { name: "Guardar odontograma" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Hay una versión más nueva del odontograma. Recargá para ver los cambios antes de volver a marcar",
    );
    expect(screen.getByRole("button", { name: /^Pieza 16/ })).toHaveAccessibleName(
      "Pieza 16: caries existente en O",
    );
    expect(api.de("POST /api/pacientes/7/odontograma")).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Recargar versión vigente" }));
    const confirmar = await screen.findByRole("dialog", { name: "Recargar versión vigente" });
    await userEvent.click(within(confirmar).getByRole("button", { name: "Descartar y recargar" }));
    expect(await screen.findByText(/Versión 2 · guardada por/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Pieza 16/ })).toHaveAccessibleName("Pieza 16");
    expect(screen.getByRole("button", { name: "Guardar odontograma" })).toBeDisabled();
    expect(api.de("POST /api/pacientes/7/odontograma")).toHaveLength(1);
  });
});

describe("Aviso de cambios sin guardar", () => {
  it("cambiar de pestaña con borrador pregunta; cancelar se queda", async () => {
    const { router } = renderApp(RUTA, conOdonto(odontograma()));
    await userEvent.click(await screen.findByRole("button", { name: /^Pieza 16/ }));
    const panel = await screen.findByRole("dialog", { name: "Pieza 16" });
    await userEvent.selectOptions(within(panel).getByLabelText("Cara O"), "caries");
    await userEvent.click(within(panel).getByRole("button", { name: "Listo" }));
    await userEvent.click(screen.getByRole("link", { name: "Evoluciones" }));
    const dialogo = await screen.findByRole("dialog", { name: "Cambios sin guardar" });
    await userEvent.click(within(dialogo).getByRole("button", { name: "Seguir editando" }));
    expect(router.state.location.pathname).toBe(RUTA);
    expect(screen.getByRole("button", { name: /^Pieza 16/ })).toHaveAccessibleName(
      "Pieza 16: caries existente en O",
    );
    await userEvent.click(screen.getByRole("link", { name: "Evoluciones" }));
    await userEvent.click(
      within(await screen.findByRole("dialog", { name: "Cambios sin guardar" })).getByRole(
        "button",
        {
          name: "Descartar y salir",
        },
      ),
    );
    await waitFor(() => expect(router.state.location.pathname).toBe("/pacientes/7/evoluciones"));
  });

  it("sin cambios navega sin preguntar", async () => {
    const { router } = renderApp(RUTA, conOdonto(odontograma()));
    await userEvent.click(await screen.findByRole("link", { name: "Evoluciones" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/pacientes/7/evoluciones"));
  });
});

describe("Historial de versiones", () => {
  it("ver una versión anterior: solo lectura rotulada, sin Guardar", async () => {
    const v2 = { ...v1, id: 6, version: 2, piezas: {} };
    renderApp(
      RUTA,
      conOdonto(v2, {
        "GET /api/pacientes/7/odontograma": { json: [v2, v1] },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: "Ver versiones" }));
    const lista = await screen.findByRole("list", { name: "Versiones del odontograma" });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(2);
    await userEvent.click(within(lista).getByRole("button", { name: "Ver versión 1" }));
    expect(screen.getByText("Versión 1 (anterior) · solo lectura")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Guardar odontograma" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Pieza 36/ })).toHaveAccessibleName(
      "Pieza 36: caries a realizar en M, obturación existente en O",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volver a la versión vigente" }));
    expect(screen.getByRole("button", { name: /^Pieza 36/ })).toHaveAccessibleName("Pieza 36");
  });
});

describe("Acceso clínico y consentimiento", () => {
  it("recepción: Sin acceso clínico, sin SVG ni piezas, encabezado visible", async () => {
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
    expect(screen.queryAllByRole("button", { name: /^Pieza \d{2}/ })).toHaveLength(0);
    expect(document.querySelector("svg")).toBeNull();
    expect(screen.getByRole("heading", { name: /Sintético Uno, Demo/ })).toBeInTheDocument();
  });

  it("admin sin rol odontólogo: lectura, sin Guardar ni selector de dentición", async () => {
    renderApp(
      RUTA,
      tablaPaciente(
        { "GET /api/pacientes/7/historia": { json: historia({ odontograma: v1 }) } },
        meAdmin,
      ),
    );
    await screen.findByRole("button", { name: /^Pieza 36/ });
    expect(screen.queryByRole("button", { name: "Guardar odontograma" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Dentición")).not.toBeInTheDocument();
  });

  it("sin consentimiento: edición bloqueada con aviso, marcas existentes visibles", async () => {
    renderApp(
      RUTA,
      conOdonto(v1, {
        "GET /api/pacientes/7": {
          json: paciente({ consentimiento_datos: false, consentimiento_datos_at: null }),
        },
      }),
    );
    await screen.findByRole("button", { name: /^Pieza 36/ });
    expect(screen.getByRole("button", { name: "Guardar odontograma" })).toBeDisabled();
    expect(screen.getByLabelText("Dentición")).toBeDisabled();
    expect(
      screen.getAllByText("Sin consentimiento de datos: no se pueden cargar datos de salud").length,
    ).toBeGreaterThan(1);
  });
});
