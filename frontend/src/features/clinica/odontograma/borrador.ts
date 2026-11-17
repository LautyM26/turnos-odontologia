/** Reducer puro del borrador del odontograma (sin DOM, sin mutaciones). */

import type {
  Cara,
  Denticion,
  MarcaCara,
  MarcaPieza,
  Odontograma,
  OdontogramaIn,
  Pieza,
  Piezas,
} from "../tipos";
import { ETIQUETA_ESTADO, ETIQUETA_REGISTRO, ORDEN_CARAS, piezasDe, SIN_CARAS } from "./fdi";

export interface Borrador {
  denticion: Denticion;
  piezas: Piezas;
}

function vacia(p: Pieza): boolean {
  return !p.estado && Object.keys(p.caras ?? {}).length === 0;
}

function conPieza(b: Borrador, pieza: number, nueva: Pieza): Borrador {
  const { [String(pieza)]: _quitada, ...resto } = b.piezas;
  return { ...b, piezas: vacia(nueva) ? resto : { ...resto, [String(pieza)]: nueva } };
}

export function marcarCara(
  b: Borrador,
  pieza: number,
  cara: Cara,
  marca: MarcaCara | null,
): Borrador {
  const actual = b.piezas[String(pieza)] ?? {};
  if (actual.estado && SIN_CARAS.includes(actual.estado.codigo)) {
    return b;
  }
  const { [cara]: _quitada, ...resto } = actual.caras ?? {};
  return conPieza(b, pieza, {
    ...(actual.estado ? { estado: actual.estado } : {}),
    caras: marca ? { ...resto, [cara]: marca } : resto,
  });
}

export function marcarPieza(b: Borrador, pieza: number, marca: MarcaPieza | null): Borrador {
  const actual = b.piezas[String(pieza)] ?? {};
  const sinCaras = marca !== null && SIN_CARAS.includes(marca.codigo);
  return conPieza(b, pieza, {
    ...(marca ? { estado: marca } : {}),
    caras: sinCaras ? {} : (actual.caras ?? {}),
  });
}

/** Aplica la nueva dentición y devuelve las piezas con marcas que quedaron afuera. */
export function cambiarDenticion(
  b: Borrador,
  denticion: Denticion,
): { borrador: Borrador; descartadas: number[] } {
  const validas = new Set(piezasDe(denticion));
  const descartadas: number[] = [];
  const piezas: Piezas = {};
  for (const [clave, pieza] of Object.entries(b.piezas)) {
    if (validas.has(Number(clave))) {
      piezas[clave] = pieza;
    } else {
      descartadas.push(Number(clave));
    }
  }
  return { borrador: { denticion, piezas }, descartadas: descartadas.sort((a, c) => a - c) };
}

function normalizar(piezas: Piezas): Piezas {
  const salida: Piezas = {};
  for (const clave of Object.keys(piezas).sort()) {
    const p = piezas[clave] as Pieza;
    if (vacia(p)) continue;
    const caras: Partial<Record<Cara, MarcaCara>> = {};
    for (const c of ORDEN_CARAS) {
      const m = p.caras?.[c];
      if (m) caras[c] = { codigo: m.codigo, registro: m.registro };
    }
    salida[clave] = {
      ...(p.estado ? { estado: { codigo: p.estado.codigo, registro: p.estado.registro } } : {}),
      caras,
    };
  }
  return salida;
}

export function aPayload(b: Borrador, versionEsperada: number): OdontogramaIn {
  return {
    version_esperada: versionEsperada,
    denticion: b.denticion,
    piezas: normalizar(b.piezas),
  };
}

export function borradorDesde(o: Odontograma): Borrador {
  return o.version === 0 || o.denticion === null
    ? { denticion: "permanente", piezas: {} }
    : { denticion: o.denticion, piezas: normalizar(o.piezas) };
}

export function hayCambios(b: Borrador, vigente: Odontograma): boolean {
  const base = borradorDesde(vigente);
  return (
    b.denticion !== base.denticion ||
    JSON.stringify(normalizar(b.piezas)) !== JSON.stringify(base.piezas)
  );
}

export interface Hallazgo {
  pieza: number;
  cara: Cara | null;
  texto: string;
}

/** Filas de la tabla textual: "36 · M · Caries · A realizar". */
export function hallazgos(piezas: Piezas): Hallazgo[] {
  const filas: Hallazgo[] = [];
  const claves = Object.keys(normalizar(piezas))
    .map(Number)
    .sort((a, b) => a - b);
  for (const pieza of claves) {
    const p = piezas[String(pieza)] as Pieza;
    if (p.estado) {
      filas.push({
        pieza,
        cara: null,
        texto: `${pieza} · Pieza · ${ETIQUETA_ESTADO[p.estado.codigo]} · ${ETIQUETA_REGISTRO[p.estado.registro]}`,
      });
    }
    for (const cara of ORDEN_CARAS) {
      const m = p.caras?.[cara];
      if (m) {
        filas.push({
          pieza,
          cara,
          texto: `${pieza} · ${cara} · ${ETIQUETA_ESTADO[m.codigo]} · ${ETIQUETA_REGISTRO[m.registro]}`,
        });
      }
    }
  }
  return filas;
}
