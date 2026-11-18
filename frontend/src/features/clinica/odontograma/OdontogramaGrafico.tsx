/** Dibujo del odontograma: cada pieza es un <button> con un SVG de 5 caras. */

import type { Cara, Denticion, EstadoPieza, Pieza, Piezas, Registro } from "../tipos";
import { arcadas, ETIQUETA_ESTADO, ETIQUETA_REGISTRO, ORDEN_CARAS, posicionCaras } from "./fdi";

const POLIGONOS: Record<"arriba" | "abajo" | "izquierda" | "derecha", string> = {
  arriba: "0,0 40,0 30,10 10,10",
  abajo: "10,30 30,30 40,40 0,40",
  izquierda: "0,0 10,10 10,30 0,40",
  derecha: "40,0 40,40 30,30 30,10",
};

/** a realizar = trama rayada roja; existente = relleno azul sólido (no depende solo del color). */
function relleno(registro: Registro | undefined): string {
  if (registro === "a_realizar") return "url(#odo-trama)";
  if (registro === "existente") return "var(--odo-existente)";
  return "white";
}

/** "caries a realizar en M" / "ausente" para el nombre accesible. */
export function descripcionPieza(pieza: Pieza | undefined): string {
  if (!pieza) return "";
  const partes: string[] = [];
  if (pieza.estado) {
    const { codigo, registro } = pieza.estado;
    partes.push(
      `${ETIQUETA_ESTADO[codigo].toLowerCase()}${registro === "a_realizar" ? " a realizar" : ""}`,
    );
  }
  for (const c of ORDEN_CARAS) {
    const m = pieza.caras?.[c];
    if (m) {
      partes.push(
        `${ETIQUETA_ESTADO[m.codigo].toLowerCase()} ${ETIQUETA_REGISTRO[m.registro].toLowerCase()} en ${c}`,
      );
    }
  }
  return partes.join(", ");
}

function SimboloEstado({ codigo, color }: { codigo: EstadoPieza; color: string }) {
  const trazo = { stroke: color, strokeWidth: 3, fill: "none" } as const;
  switch (codigo) {
    case "ausente":
    case "extraida":
    case "extraccion_indicada":
      return (
        <g {...trazo}>
          <line x1="3" y1="3" x2="37" y2="37" />
          <line x1="37" y1="3" x2="3" y2="37" />
        </g>
      );
    case "corona":
      return <circle cx="20" cy="20" r="17" {...trazo} />;
    case "endodoncia":
      return <line x1="20" y1="2" x2="20" y2="38" {...trazo} />;
    case "implante":
      return (
        <text x="20" y="27" textAnchor="middle" fontSize="22" fontWeight="bold" fill={color}>
          I
        </text>
      );
  }
}

function PiezaSvg({ numero, pieza }: { numero: number; pieza: Pieza | undefined }) {
  const pos = posicionCaras(numero);
  const caras: [Cara, string][] = [
    [pos.arriba, POLIGONOS.arriba],
    [pos.abajo, POLIGONOS.abajo],
    [pos.izquierda, POLIGONOS.izquierda],
    [pos.derecha, POLIGONOS.derecha],
  ];
  const estado = pieza?.estado;
  const colorEstado =
    estado?.registro === "a_realizar" || estado?.codigo === "extraccion_indicada"
      ? "var(--odo-a-realizar)"
      : "var(--odo-existente)";
  return (
    <svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true" focusable="false">
      {caras.map(([c, puntos]) => (
        <polygon
          key={c}
          data-cara={c}
          points={puntos}
          stroke="currentColor"
          strokeWidth="1"
          style={{ fill: relleno(pieza?.caras?.[c]?.registro) }}
        />
      ))}
      <rect
        data-cara="O"
        x="10"
        y="10"
        width="20"
        height="20"
        stroke="currentColor"
        strokeWidth="1"
        style={{ fill: relleno(pieza?.caras?.O?.registro) }}
      />
      {estado && <SimboloEstado codigo={estado.codigo} color={colorEstado} />}
    </svg>
  );
}

interface Props {
  denticion: Denticion;
  piezas: Piezas;
  onAbrir: (pieza: number, cara: Cara | null) => void;
}

export function OdontogramaGrafico({ denticion, piezas, onAbrir }: Props) {
  const { superior, inferior } = arcadas(denticion);
  const fila = (numeros: number[]) => (
    <div key={numeros[0]} className="flex justify-center gap-1">
      {numeros.map((n) => {
        const pieza = piezas[String(n)];
        const marcas = descripcionPieza(pieza);
        return (
          <button
            key={n}
            id={`pieza-${n}`}
            type="button"
            aria-label={marcas ? `Pieza ${n}: ${marcas}` : `Pieza ${n}`}
            className="flex min-h-11 min-w-10 flex-col items-center rounded text-xs"
            onClick={(e) => {
              const destino = (e.target as Element).closest("[data-cara]");
              onAbrir(n, (destino?.getAttribute("data-cara") as Cara | null) ?? null);
            }}
          >
            <PiezaSvg numero={n} pieza={pieza} />
            <span aria-hidden="true">{n}</span>
          </button>
        );
      })}
    </div>
  );
  return (
    <div className="overflow-x-auto rounded-[14px] border border-border bg-white p-4 text-slate-800 [color-scheme:light]">
      <svg width="0" height="0" aria-hidden="true" focusable="false" className="absolute">
        <defs>
          <pattern
            id="odo-trama"
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="white" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--odo-a-realizar)" strokeWidth="3" />
          </pattern>
        </defs>
      </svg>
      <div className="mx-auto w-max space-y-1">
        {superior.map(fila)}
        <hr className="my-2 border-slate-200" />
        {inferior.map(fila)}
      </div>
    </div>
  );
}
