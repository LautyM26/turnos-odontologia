/** Lógica pura de la agenda (C-07 D6/D8): zona horaria, semana, rango, carriles, transiciones. */

import { describe, expect, it } from "vitest";

import { asignarCarriles } from "@/features/agenda/carriles";
import {
  diaSemana,
  fechaLocal,
  horaLocal,
  instanteLocal,
  minutosLocales,
  rangoVisible,
  semanaDe,
  sumarDias,
  ventanaDia,
} from "@/features/agenda/tiempo";
import { accionesPermitidas } from "@/features/agenda/transiciones";

const AR = "America/Argentina/Buenos_Aires";

describe("zona horaria de la clínica", () => {
  it("un instante UTC de madrugada cae el día anterior en Buenos Aires", () => {
    expect(fechaLocal("2033-09-06T01:30:00Z", AR)).toBe("2033-09-05");
    expect(minutosLocales("2033-09-06T01:30:00Z", AR)).toBe(22 * 60 + 30);
    expect(horaLocal("2033-09-05T13:00:00Z", AR)).toBe("10:00");
  });

  it("instanteLocal convierte fecha + minutos locales a UTC", () => {
    expect(instanteLocal("2033-09-05", 9 * 60, AR).toISOString()).toBe("2033-09-05T12:00:00.000Z");
  });

  it("la ventana del día va de medianoche a medianoche local", () => {
    const { desde, hasta } = ventanaDia("2033-09-05", AR);
    expect(desde.toISOString()).toBe("2033-09-05T03:00:00.000Z");
    expect(hasta.toISOString()).toBe("2033-09-06T03:00:00.000Z");
  });
});

describe("calendario", () => {
  it("semana de lunes a domingo y suma de días entre meses", () => {
    expect(diaSemana("2033-09-05")).toBe(1);
    expect(semanaDe("2033-09-08")).toEqual([
      "2033-09-05",
      "2033-09-06",
      "2033-09-07",
      "2033-09-08",
      "2033-09-09",
      "2033-09-10",
      "2033-09-11",
    ]); // fmt: skip
    expect(sumarDias("2033-09-30", 1)).toBe("2033-10-01");
    expect(semanaDe("2033-09-11")[0]).toBe("2033-09-05");
  });

  it("rango visible por franjas y turnos, redondeado; default 08-20", () => {
    expect(rangoVisible([], [])).toEqual({ inicio: 480, fin: 1200 });
    expect(
      rangoVisible(
        [
          { inicio: 540, fin: 780 },
          { inicio: 840, fin: 1080 },
        ],
        [],
      ),
    ).toEqual({
      inicio: 540,
      fin: 1080,
    });
    // un sobreturno a las 19:15-19:45 amplía el rango
    expect(rangoVisible([{ inicio: 540, fin: 780 }], [{ inicio: 1155, fin: 1185 }])).toEqual({
      inicio: 540,
      fin: 1200,
    });
  });
});

describe("carriles", () => {
  it("dos turnos superpuestos comparten el ancho; uno separado ocupa todo", () => {
    const c = asignarCarriles([
      { id: 1, inicio: 600, fin: 630 },
      { id: 2, inicio: 615, fin: 645 },
      { id: 3, inicio: 700, fin: 730 },
    ]);
    expect(c.get(1)).toEqual({ carril: 0, total: 2 });
    expect(c.get(2)).toEqual({ carril: 1, total: 2 });
    expect(c.get(3)).toEqual({ carril: 0, total: 1 });
  });

  it("turnos contiguos no se superponen", () => {
    const c = asignarCarriles([
      { id: 1, inicio: 600, fin: 630 },
      { id: 2, inicio: 630, fin: 660 },
    ]);
    expect(c.get(2)).toEqual({ carril: 0, total: 1 });
  });
});

describe("transiciones visibles", () => {
  it("recepción: todas las de la tabla; asistido/ausente solo si ya empezó", () => {
    expect(accionesPermitidas("reservado", ["recepcionista"], false).map((a) => a.estado)).toEqual([
      "confirmado",
      "cancelado",
    ]);
    expect(accionesPermitidas("confirmado", ["recepcionista"], true).map((a) => a.estado)).toEqual([
      "asistido",
      "ausente",
      "cancelado",
    ]);
  });

  it("odontólogo: solo asistido/ausente y desde el inicio; estados finales sin acciones", () => {
    expect(accionesPermitidas("confirmado", ["odontologo"], false)).toEqual([]);
    expect(accionesPermitidas("confirmado", ["odontologo"], true).map((a) => a.estado)).toEqual([
      "asistido",
      "ausente",
    ]);
    expect(accionesPermitidas("cancelado", ["admin"], true)).toEqual([]);
  });
});
