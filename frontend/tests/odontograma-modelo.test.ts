/** Modelo puro del odontograma: FDI y reducer del borrador (spec odontogram-web). */

import { describe, expect, it } from "vitest";

import {
  aPayload,
  type Borrador,
  borradorDesde,
  cambiarDenticion,
  hallazgos,
  hayCambios,
  marcarCara,
  marcarPieza,
} from "@/features/clinica/odontograma/borrador";
import { arcadas, esPiezaFdi, piezasDe, posicionCaras } from "@/features/clinica/odontograma/fdi";

import { odontograma } from "./helpers/fixtures";

describe("fdi", () => {
  it("cantidad de piezas por dentición", () => {
    expect(piezasDe("permanente")).toHaveLength(32);
    expect(piezasDe("temporal")).toHaveLength(20);
    expect(piezasDe("mixta")).toHaveLength(52);
  });

  it("bordes válidos e inválidos", () => {
    for (const n of [11, 18, 48, 51, 85]) expect(esPiezaFdi(n)).toBe(true);
    for (const n of [19, 56, 86, 10, 0, 91]) expect(esPiezaFdi(n)).toBe(false);
  });

  it("orden de dibujo por arcada (permanente y temporal)", () => {
    const p = arcadas("permanente");
    expect(p.superior).toEqual([[18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28]]);
    expect(p.inferior).toEqual([[48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]]);
    const t = arcadas("temporal");
    expect(t.superior).toEqual([[55, 54, 53, 52, 51, 61, 62, 63, 64, 65]]);
    expect(t.inferior).toEqual([[85, 84, 83, 82, 81, 71, 72, 73, 74, 75]]);
  });

  it("mixta: permanentes en la fila externa y temporales en la interna", () => {
    const m = arcadas("mixta");
    expect(m.superior).toHaveLength(2);
    expect(m.superior[0]?.[0]).toBe(18);
    expect(m.superior[1]?.[0]).toBe(55);
    expect(m.inferior[0]?.[0]).toBe(85);
    expect(m.inferior[1]?.[0]).toBe(48);
    expect([...m.superior.flat(), ...m.inferior.flat()]).toHaveLength(52);
  });

  it("orientación de caras por cuadrante", () => {
    // superior izquierda de pantalla (cuadrante 1): V arriba, L abajo, M a la derecha
    expect(posicionCaras(16)).toEqual({ arriba: "V", abajo: "L", izquierda: "D", derecha: "M" });
    // superior derecha (2): M a la izquierda
    expect(posicionCaras(26)).toEqual({ arriba: "V", abajo: "L", izquierda: "M", derecha: "D" });
    // inferior: L arriba, V abajo (36 = cuadrante 3, M a la izquierda)
    expect(posicionCaras(36)).toEqual({ arriba: "L", abajo: "V", izquierda: "M", derecha: "D" });
    expect(posicionCaras(46)).toEqual({ arriba: "L", abajo: "V", izquierda: "D", derecha: "M" });
    expect(posicionCaras(55).derecha).toBe("M");
    expect(posicionCaras(75).izquierda).toBe("M");
  });
});

const vacio: Borrador = { denticion: "permanente", piezas: {} };

describe("borrador: marcar", () => {
  it("marcarCara agrega y quita; la pieza vacía desaparece", () => {
    const b1 = marcarCara(vacio, 16, "O", { codigo: "caries", registro: "a_realizar" });
    expect(b1.piezas["16"]?.caras?.O).toEqual({ codigo: "caries", registro: "a_realizar" });
    const b2 = marcarCara(b1, 16, "O", null);
    expect(b2.piezas).toEqual({});
  });

  it("marcarCara no muta el borrador original", () => {
    marcarCara(vacio, 16, "O", { codigo: "caries", registro: "existente" });
    expect(vacio.piezas).toEqual({});
  });

  it("marcarPieza ausente/extraída limpia las caras; corona las conserva", () => {
    const con = marcarCara(vacio, 26, "O", { codigo: "obturacion", registro: "existente" });
    const ausente = marcarPieza(con, 26, { codigo: "ausente", registro: "existente" });
    expect(ausente.piezas["26"]).toEqual({
      estado: { codigo: "ausente", registro: "existente" },
      caras: {},
    });
    const corona = marcarPieza(con, 26, { codigo: "corona", registro: "a_realizar" });
    expect(corona.piezas["26"]?.caras?.O).toBeDefined();
    const extraida = marcarPieza(con, 26, { codigo: "extraida", registro: "existente" });
    expect(extraida.piezas["26"]?.caras).toEqual({});
  });

  it("marcarPieza(null) quita el estado y la pieza vacía desaparece", () => {
    const b = marcarPieza(vacio, 26, { codigo: "implante", registro: "existente" });
    expect(marcarPieza(b, 26, null).piezas).toEqual({});
  });

  it("no se pueden marcar caras de una pieza ausente", () => {
    const aus = marcarPieza(vacio, 26, { codigo: "ausente", registro: "existente" });
    expect(marcarCara(aus, 26, "O", { codigo: "caries", registro: "existente" })).toBe(aus);
  });
});

describe("borrador: dentición", () => {
  it("cambiar a una dentición que no descarta nada no avisa piezas", () => {
    const r = cambiarDenticion(vacio, "temporal");
    expect(r.descartadas).toEqual([]);
    expect(r.borrador.denticion).toBe("temporal");
  });

  it("mixta -> permanente descarta la 55 y conserva la 16", () => {
    let b: Borrador = { denticion: "mixta", piezas: {} };
    b = marcarCara(b, 16, "O", { codigo: "caries", registro: "existente" });
    b = marcarCara(b, 55, "O", { codigo: "caries", registro: "existente" });
    const r = cambiarDenticion(b, "permanente");
    expect(r.descartadas).toEqual([55]);
    expect(Object.keys(r.borrador.piezas)).toEqual(["16"]);
  });
});

describe("borrador: payload y cambios", () => {
  it("aPayload arma el cuerpo con version_esperada y omite piezas vacías", () => {
    const b = marcarCara(vacio, 16, "O", { codigo: "caries", registro: "a_realizar" });
    const p = aPayload({ ...b, piezas: { ...b.piezas, "17": { caras: {} } } }, 1);
    expect(p).toEqual({
      version_esperada: 1,
      denticion: "permanente",
      piezas: { "16": { caras: { O: { codigo: "caries", registro: "a_realizar" } } } },
    });
  });

  it("hayCambios compara contra la versión cargada", () => {
    const v0 = odontograma();
    expect(hayCambios(borradorDesde(v0), v0)).toBe(false);
    expect(hayCambios({ denticion: "temporal", piezas: {} }, v0)).toBe(true);
    const v1 = odontograma({
      version: 1,
      denticion: "permanente",
      piezas: { "16": { caras: { O: { codigo: "caries", registro: "existente" } } } },
    });
    expect(hayCambios(borradorDesde(v1), v1)).toBe(false);
    expect(hayCambios(marcarCara(borradorDesde(v1), 16, "O", null), v1)).toBe(true);
    // estado null y pieza vacía no cuentan como cambio
    expect(
      hayCambios(
        { ...borradorDesde(v1), piezas: { ...v1.piezas, "17": { estado: null, caras: {} } } },
        v1,
      ),
    ).toBe(false);
  });

  it("borradorDesde versión 0 es permanente vacío", () => {
    expect(borradorDesde(odontograma())).toEqual({ denticion: "permanente", piezas: {} });
  });

  it("hallazgos: filas ordenadas por pieza y cara", () => {
    let b = marcarCara(vacio, 36, "O", { codigo: "obturacion", registro: "existente" });
    b = marcarCara(b, 36, "M", { codigo: "caries", registro: "a_realizar" });
    b = marcarPieza(b, 11, { codigo: "corona", registro: "existente" });
    expect(hallazgos(b.piezas).map((h) => h.texto)).toEqual([
      "11 · Pieza · Corona · Existente",
      "36 · M · Caries · A realizar",
      "36 · O · Obturación · Existente",
    ]);
  });
});
