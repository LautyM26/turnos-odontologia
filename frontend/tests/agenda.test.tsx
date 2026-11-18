/** Agenda del staff (C-07, spec agenda-web) con la app completa y fetch simulado. */

import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Me } from "@/features/clinica/tipos";

import type { Respuesta } from "./helpers/api";
import { conSesion, renderApp } from "./helpers/app";
import { meOdontologo, meRecepcion } from "./helpers/fixtures";

// 2033-09-05 es lunes. Buenos Aires = UTC-3: 10:00 local = 13:00Z.
const AHORA = new Date("2033-09-05T15:00:00Z"); // 12:00 local
const RUTA = "/agenda?fecha=2033-09-05";

const PROFESIONALES = [
  { id: 1, nombre: "Dra. Valeria Ríos", especialidad: null, usuario_id: 10, agenda_activa: true },
  { id: 2, nombre: "Dr. Tomás Ibarra", especialidad: null, usuario_id: 20, agenda_activa: true },
];
const SILLONES = [
  { id: 11, nombre: "Sillón Uno", tipo: "sillon" },
  { id: 12, nombre: "Sillón Dos", tipo: "sillon" },
];
const PRESTACIONES = [{ id: 5, nombre: "Consulta", duracion_min: 30 }];
const FRANJAS = [1, 2, 3, 4, 5].flatMap((d) => [
  { dia_semana: d, inicio: "09:00", fin: "13:00" },
  { dia_semana: d, inicio: "14:00", fin: "18:00" },
]);
const T1 = {
  id: 101,
  profesional_id: 1,
  sillon_id: 11,
  paciente_id: 7,
  paciente_nombre: "Sintético, Ana",
  prestacion_id: 5,
  prestacion_nombre: "Consulta",
  inicio: "2033-09-05T13:00:00Z",
  fin: "2033-09-05T13:30:00Z",
  estado: "confirmado",
  origen: "mostrador",
  es_sobreturno: false,
  motivo_sobreturno: null,
}; // fmt: skip
const T2 = {
  ...T1,
  id: 102,
  profesional_id: 2,
  sillon_id: 12,
  paciente_nombre: "Sintético, Bruno",
  inicio: "2033-09-05T13:15:00Z",
  fin: "2033-09-05T13:45:00Z",
  estado: "reservado",
  origen: "enlace",
  es_sobreturno: true,
  motivo_sobreturno: "urgencia sintética",
}; // fmt: skip
const ALMUERZO = {
  id: 9,
  alcance: "clinica",
  profesional_id: null,
  sillon_id: null,
  inicio: "2033-09-05T16:00:00Z",
  fin: "2033-09-05T17:00:00Z",
  motivo: "Almuerzo",
}; // fmt: skip

function tabla(me: Me, extra: Record<string, Respuesta> = {}): Record<string, Respuesta> {
  return {
    ...conSesion(me),
    "GET /api/catalogo/profesionales": { json: { items: PROFESIONALES, next_cursor: null } },
    "GET /api/catalogo/sillones": { json: { items: SILLONES, next_cursor: null } },
    "GET /api/catalogo/prestaciones": { json: { items: PRESTACIONES, next_cursor: null } },
    "GET /api/agenda/turnos": { json: [T1, T2] },
    "GET /api/agenda/bloqueos": { json: [ALMUERZO] },
    "GET /api/catalogo/profesionales/1/horario": {
      json: { profesional_id: 1, zona_horaria: "America/Argentina/Buenos_Aires", franjas: FRANJAS },
    },
    "GET /api/catalogo/profesionales/2/horario": {
      json: { profesional_id: 2, zona_horaria: "America/Argentina/Buenos_Aires", franjas: FRANJAS },
    },
    ...extra,
  };
}

beforeEach(() => {
  vi.setSystemTime(AHORA);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const turno = (nombre: RegExp | string) => screen.findByRole("button", { name: nombre });

describe("vista día por sillón", () => {
  it("muestra una columna por sillón con los turnos, su estado y el sobreturno", async () => {
    renderApp(RUTA, tabla(meRecepcion));
    expect(await screen.findByRole("heading", { name: "Agenda" })).toBeInTheDocument();
    expect(await screen.findByText("Sillón Uno")).toBeInTheDocument();
    expect(screen.getByText("Sillón Dos")).toBeInTheDocument();
    expect(await turno("10:00 a 10:30, Sintético, Ana, Confirmado")).toBeInTheDocument();
    expect(
      await turno("10:15 a 10:45, Sintético, Bruno, Reservado, sobreturno"),
    ).toBeInTheDocument();
  });

  it("carga turnos, bloqueos y horarios en paralelo (regla dura 13)", async () => {
    let liberar: () => void = () => undefined;
    const pendiente = new Promise<void>((r) => {
      liberar = r;
    });
    const { api } = renderApp(
      RUTA,
      tabla(meRecepcion, {
        "GET /api/agenda/turnos": async () => {
          await pendiente;
          return { json: [T1] };
        },
      }),
    );
    // con turnos todavía pendiente, bloqueos y horarios ya salieron
    await waitFor(() => expect(api.de("GET /api/agenda/bloqueos")).toHaveLength(1));
    expect(api.de("GET /api/catalogo/profesionales/1/horario")).toHaveLength(1);
    expect(api.de("GET /api/catalogo/profesionales/2/horario")).toHaveLength(1);
    expect(api.de("GET /api/agenda/turnos")).toHaveLength(1);
    liberar();
    expect(await turno(/Sintético, Ana/)).toBeInTheDocument();
  });

  it("el bloqueo muestra su motivo y no ofrece crear turnos encima", async () => {
    renderApp(RUTA, tabla(meRecepcion));
    expect((await screen.findAllByText("Almuerzo")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Nuevo turno 13:15 en Sillón Uno" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "Nuevo turno 11:00 en Sillón Uno" }),
    ).toBeInTheDocument();
    const bloqueo = document.querySelector("[data-bloqueo='9']");
    expect(bloqueo).not.toBeNull();
    await userEvent.click(bloqueo as Element);
    expect(screen.queryByRole("dialog", { name: "Nuevo turno" })).toBeNull();
  });

  it("recarga cada 60 s", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    vi.setSystemTime(AHORA);
    const { api } = renderApp(RUTA, tabla(meRecepcion));
    await turno(/Sintético, Ana/);
    const antes = api.de("GET /api/agenda/turnos").length;
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    await waitFor(() => expect(api.de("GET /api/agenda/turnos").length).toBe(antes + 1));
  });
});

describe("vista semana y deep-link", () => {
  it("la URL abre la semana del profesional con 7 columnas", async () => {
    const { api } = renderApp(
      "/agenda?fecha=2033-09-07&vista=semana&profesional=1",
      tabla(meRecepcion),
    );
    await turno(/Sintético, Ana/);
    expect(api.de("GET /api/agenda/turnos")[0]?.url).toContain("profesional_id=1");
    expect(screen.getByRole("button", { name: "Semana" })).toHaveAttribute("aria-pressed", "true");
    // lunes 5 a domingo 11
    expect(screen.getByText(/Semana del 5 de septiembre/i)).toBeInTheDocument();
    expect(screen.getByText("dom 11")).toBeInTheDocument();
  });

  it("cambiar a semana actualiza la URL", async () => {
    const { router } = renderApp(RUTA, tabla(meRecepcion));
    await turno(/Sintético, Ana/);
    await userEvent.click(screen.getByRole("button", { name: "Semana" }));
    await waitFor(() => expect(router.state.location.search).toContain("vista=semana"));
  });
});

describe("alta de turno", () => {
  it("con paciente existente: crea el turno y recarga la agenda", async () => {
    const { api } = renderApp(
      RUTA,
      tabla(meRecepcion, {
        "GET /api/pacientes": {
          json: {
            items: [{ id: 7, nombre: "Ana", apellido: "Sintético", dni: "30111222" }],
            next_cursor: null,
          },
        },
        "POST /api/turnos": { status: 201, json: { id: 555 } },
      }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Nuevo turno 11:00 en Sillón Uno" }),
    );
    const panel = await screen.findByRole("dialog", { name: "Nuevo turno" });
    await userEvent.type(within(panel).getByLabelText("Buscar paciente"), "Sint");
    await userEvent.click(await within(panel).findByRole("button", { name: /Sintético, Ana/ }));
    const recargasAntes = api.de("GET /api/agenda/turnos").length;
    await userEvent.click(within(panel).getByRole("button", { name: "Crear turno" }));
    await waitFor(() => expect(api.de("POST /api/turnos")).toHaveLength(1));
    expect(api.cuerpo("POST /api/turnos")).toEqual({
      profesional_id: 1,
      sillon_id: 11,
      paciente_id: 7,
      prestacion_id: 5,
      inicio: "2033-09-05T14:00:00.000Z",
    }); // fmt: skip
    await waitFor(() =>
      expect(api.de("GET /api/agenda/turnos").length).toBeGreaterThan(recargasAntes),
    );
    expect(await screen.findByText("Turno creado.")).toBeInTheDocument();
  });

  it("alta rápida de paciente lo crea y lo deja elegido", async () => {
    const { api } = renderApp(
      RUTA,
      tabla(meRecepcion, {
        "POST /api/pacientes": {
          status: 201,
          json: { id: 8, nombre: "Lucía", apellido: "Prueba", dni: "40222333" },
        },
      }),
    );
    await userEvent.click(await screen.findByRole("button", { name: "Nuevo turno" }));
    const panel = await screen.findByRole("dialog", { name: "Nuevo turno" });
    await userEvent.click(within(panel).getByRole("button", { name: "Nuevo paciente" }));
    await userEvent.type(within(panel).getByLabelText("Nombre"), "Lucía");
    await userEvent.type(within(panel).getByLabelText("Apellido"), "Prueba");
    await userEvent.type(within(panel).getByLabelText("DNI"), "40222333");
    await userEvent.type(within(panel).getByLabelText("Email"), "lucia@ejemplo.test");
    await userEvent.click(within(panel).getByRole("button", { name: "Crear paciente" }));
    expect(await within(panel).findByText("Prueba, Lucía")).toBeInTheDocument();
    expect(api.cuerpo("POST /api/pacientes")).toEqual({
      nombre: "Lucía",
      apellido: "Prueba",
      dni: "40222333",
      email: "lucia@ejemplo.test",
    }); // fmt: skip
  });

  it("409: avisa, recarga y ofrece alternativas que actualizan la hora", async () => {
    const { api } = renderApp(
      RUTA,
      tabla(meRecepcion, {
        "GET /api/pacientes": {
          json: {
            items: [{ id: 7, nombre: "Ana", apellido: "Sintético", dni: "30111222" }],
            next_cursor: null,
          },
        },
        "POST /api/turnos": { status: 409, json: { detail: "Horario no disponible" } },
        "GET /api/agenda/huecos": {
          json: [
            { inicio: "2033-09-05T14:15:00Z", fin: "2033-09-05T14:45:00Z", sillon_ids: [11, 12] },
            { inicio: "2033-09-05T14:30:00Z", fin: "2033-09-05T15:00:00Z", sillon_ids: [12] },
          ],
        },
      }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Nuevo turno 11:00 en Sillón Uno" }),
    );
    const panel = await screen.findByRole("dialog", { name: "Nuevo turno" });
    await userEvent.type(within(panel).getByLabelText("Buscar paciente"), "Sint");
    await userEvent.click(await within(panel).findByRole("button", { name: /Sintético, Ana/ }));
    await userEvent.click(within(panel).getByRole("button", { name: "Crear turno" }));
    expect(await within(panel).findByText(/ya no está disponible/)).toBeInTheDocument();
    const lista = await within(panel).findByRole("list", { name: "Horarios alternativos" });
    await userEvent.click(within(lista).getByRole("button", { name: "11:30" }));
    expect(within(panel).getByLabelText("Hora")).toHaveValue("11:30");
    expect(within(panel).getByLabelText("Sillón")).toHaveValue("12");
    expect(api.de("GET /api/agenda/huecos")).toHaveLength(1);
  });
});

describe("detalle y transiciones", () => {
  it("recepción cancela con confirmación", async () => {
    const { api } = renderApp(
      RUTA,
      tabla(meRecepcion, {
        "POST /api/turnos/101/transicion": { json: { ...T1, estado: "cancelado" } },
      }),
    );
    await userEvent.click(await turno(/Sintético, Ana, Confirmado/));
    const panel = await screen.findByRole("dialog", { name: "Sintético, Ana" });
    expect(within(panel).getByRole("button", { name: "Marcar asistido" })).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Cancelar turno" }));
    await userEvent.click(await screen.findByRole("button", { name: "Sí, cancelar" }));
    await waitFor(() =>
      expect(api.cuerpo("POST /api/turnos/101/transicion")).toEqual({ estado: "cancelado" }),
    );
  });

  it("422 de la API se muestra en el detalle", async () => {
    renderApp(
      RUTA,
      tabla(meRecepcion, {
        "POST /api/turnos/102/transicion": {
          status: 422,
          json: { detail: "Transición no permitida" },
        },
      }),
    );
    await userEvent.click(await turno(/Sintético, Bruno/));
    const panel = await screen.findByRole("dialog", { name: "Sintético, Bruno" });
    await userEvent.click(within(panel).getByRole("button", { name: "Confirmar" }));
    expect(await within(panel).findByText("Transición no permitida")).toBeInTheDocument();
  });
});

describe("odontólogo", () => {
  it("ve fija su agenda, sin alta de turnos", async () => {
    const { api } = renderApp(RUTA, tabla(meOdontologo));
    await turno(/Sintético, Ana/);
    expect(screen.getByText(/Mi agenda/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nuevo turno" })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Nuevo turno \d/ })).toBeNull();
    expect(api.de("GET /api/agenda/turnos")[0]?.url).toContain("profesional_id=1");
  });

  it("antes del inicio no tiene acciones; desde el inicio solo asistido/ausente", async () => {
    vi.setSystemTime(new Date("2033-09-05T12:00:00Z")); // 09:00 local, antes del turno de 10:00
    renderApp(RUTA, tabla(meOdontologo));
    await userEvent.click(await turno(/Sintético, Ana/));
    const panel = await screen.findByRole("dialog", { name: "Sintético, Ana" });
    expect(within(panel).queryByRole("button", { name: "Marcar asistido" })).toBeNull();
    expect(within(panel).getByText(/desde su horario de inicio/)).toBeInTheDocument();
  });
});
