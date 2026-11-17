/** Notación FDI, orden de dibujo, orientación de caras y catálogos (DC-3). Módulo puro. */

import type { Cara, Denticion, EstadoCara, EstadoPieza, Registro } from "../tipos";

const rango = (desde: number, hasta: number): number[] =>
  Array.from({ length: Math.abs(hasta - desde) + 1 }, (_, i) =>
    desde <= hasta ? desde + i : desde - i,
  );

/** Fila de una arcada: cuadrante de pantalla izquierda (de la distal a la media) + derecha. */
const fila = (qIzq: number, qDer: number, n: number): number[] => [
  ...rango(qIzq * 10 + n, qIzq * 10 + 1),
  ...rango(qDer * 10 + 1, qDer * 10 + n),
];

const PERM_SUP = fila(1, 2, 8);
const PERM_INF = fila(4, 3, 8);
const TEMP_SUP = fila(5, 6, 5);
const TEMP_INF = fila(8, 7, 5);

export interface Arcadas {
  /** Filas de arriba hacia abajo. */
  superior: number[][];
  inferior: number[][];
}

/** Maxilar superior arriba; en mixta las temporales van en la fila interna de cada arcada. */
export function arcadas(denticion: Denticion): Arcadas {
  switch (denticion) {
    case "permanente":
      return { superior: [PERM_SUP], inferior: [PERM_INF] };
    case "temporal":
      return { superior: [TEMP_SUP], inferior: [TEMP_INF] };
    case "mixta":
      return { superior: [PERM_SUP, TEMP_SUP], inferior: [TEMP_INF, PERM_INF] };
  }
}

export function piezasDe(denticion: Denticion): number[] {
  const a = arcadas(denticion);
  return [...a.superior.flat(), ...a.inferior.flat()];
}

export function esPiezaFdi(n: number): boolean {
  return piezasDe("mixta").includes(n);
}

export interface PosicionCaras {
  arriba: Cara;
  abajo: Cara;
  izquierda: Cara;
  derecha: Cara;
}

/** V/L según la arcada; M mira a la línea media (a la derecha de pantalla en cuadrantes 1,4,5,8). */
export function posicionCaras(pieza: number): PosicionCaras {
  const cuadrante = Math.floor(pieza / 10);
  const superior = [1, 2, 5, 6].includes(cuadrante);
  const mesialADerecha = [1, 4, 5, 8].includes(cuadrante);
  return {
    arriba: superior ? "V" : "L",
    abajo: superior ? "L" : "V",
    izquierda: mesialADerecha ? "D" : "M",
    derecha: mesialADerecha ? "M" : "D",
  };
}

export const ORDEN_CARAS: Cara[] = ["V", "L", "M", "D", "O"];

export const ETIQUETA_CARA: Record<Cara, string> = {
  V: "Vestibular",
  L: "Lingual / palatina",
  M: "Mesial",
  D: "Distal",
  O: "Oclusal",
};

export const ESTADOS_PIEZA: { codigo: EstadoPieza; etiqueta: string }[] = [
  { codigo: "ausente", etiqueta: "Ausente" },
  { codigo: "extraida", etiqueta: "Extraída" },
  { codigo: "extraccion_indicada", etiqueta: "Extracción indicada" },
  { codigo: "corona", etiqueta: "Corona" },
  { codigo: "endodoncia", etiqueta: "Endodoncia" },
  { codigo: "implante", etiqueta: "Implante" },
];

export const ESTADOS_CARA: { codigo: EstadoCara; etiqueta: string }[] = [
  { codigo: "caries", etiqueta: "Caries" },
  { codigo: "obturacion", etiqueta: "Obturación" },
  { codigo: "sellador", etiqueta: "Sellador" },
  { codigo: "fractura", etiqueta: "Fractura" },
];

export const ETIQUETA_REGISTRO: Record<Registro, string> = {
  existente: "Existente",
  a_realizar: "A realizar",
};

export const ETIQUETA_ESTADO: Record<EstadoPieza | EstadoCara, string> = Object.fromEntries(
  [...ESTADOS_PIEZA, ...ESTADOS_CARA].map((e) => [e.codigo, e.etiqueta]),
) as Record<EstadoPieza | EstadoCara, string>;

/** Estados de pieza que no admiten caras marcadas. */
export const SIN_CARAS: EstadoPieza[] = ["ausente", "extraida"];
