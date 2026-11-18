/**
 * Grilla de la agenda (C-07 D6): eje de horas + columnas (sillones en Día, días en Semana).
 * Turnos posicionados por minutos locales de la clínica, bloqueos no reservables encima,
 * horas fuera de atención sombreadas y línea "ahora". La grilla scrollea en ambos ejes con
 * encabezado y eje de horas fijos.
 */

import { Globe, ListOrdered, MessageCircle, Plus } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { cx } from "@/shared/ui/cx";
import { ETIQUETA_ESTADO } from "@/shared/ui/EstadoBadge";

import type { AgendaBloqueo, AgendaTurno } from "./api";
import { asignarCarriles } from "./carriles";
import { fechaLocal, horaLocal, minutosAHhmm, minutosLocales, type Rango } from "./tiempo";

export const ESCALA = 1.6; // px por minuto: 15 min = 24 px, 1 h = 96 px
const PASO = 15;

export interface ColumnaGrilla {
  clave: string;
  titulo: string;
  subtitulo?: string;
  fecha: string;
  sillonId: number | null;
  profesionalId: number | null;
  esHoy: boolean;
  /** Realzar el encabezado (solo el día de hoy en la vista Semana). */
  destacar?: boolean;
  turnos: AgendaTurno[];
  bloqueos: AgendaBloqueo[];
  /** Tramos de atención en minutos locales; `null` = sin datos de horario (todo disponible). */
  disponibles: Rango[] | null;
}

interface Props {
  columnas: ColumnaGrilla[];
  rango: Rango;
  zona: string;
  ahoraMin: number | null;
  puedeCrear: boolean;
  resaltado: number | null;
  onSlot: (columna: ColumnaGrilla, minutos: number) => void;
  onTurno: (turno: AgendaTurno) => void;
}

const ESTILO_TURNO: Record<string, string> = {
  reservado: "border-l-muted bg-surface",
  confirmado: "border-l-primary bg-primary-soft",
  asistido: "border-l-success bg-success-soft",
  ausente: "border-l-warning bg-warning-soft",
  cancelado: "border-l-danger/60 bg-surface opacity-60",
};

const ORIGEN: Record<string, { Icono: typeof Globe; texto: string } | undefined> = {
  enlace: { Icono: Globe, texto: "Reserva online" },
  whatsapp: { Icono: MessageCircle, texto: "WhatsApp" },
  lista_espera: { Icono: ListOrdered, texto: "Lista de espera" },
};

function minutosEnColumna(
  iso: string,
  fecha: string,
  zona: string,
  extremo: "inicio" | "fin",
): number {
  // un rango que cruza la medianoche se recorta al día de la columna
  const m = minutosLocales(iso, zona);
  const mismoDia = fechaLocal(iso, zona) === fecha;
  if (mismoDia) {
    return extremo === "fin" && m === 0 ? 24 * 60 : m;
  }
  return extremo === "inicio" ? 0 : 24 * 60;
}

function complemento(disponibles: Rango[], rango: Rango): Rango[] {
  const orden = [...disponibles].sort((a, b) => a.inicio - b.inicio);
  const huecos: Rango[] = [];
  let cursor = rango.inicio;
  for (const d of orden) {
    if (d.inicio > cursor) {
      huecos.push({ inicio: cursor, fin: Math.min(d.inicio, rango.fin) });
    }
    cursor = Math.max(cursor, d.fin);
  }
  if (cursor < rango.fin) {
    huecos.push({ inicio: cursor, fin: rango.fin });
  }
  return huecos.filter((h) => h.fin > h.inicio);
}

export function Grilla({
  columnas,
  rango,
  zona,
  ahoraMin,
  puedeCrear,
  resaltado,
  onSlot,
  onTurno,
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const alto = (rango.fin - rango.inicio) * ESCALA;
  const horas = useMemo(() => {
    const lista: number[] = [];
    for (let m = rango.inicio; m < rango.fin; m += 60) {
      lista.push(m);
    }
    return lista;
  }, [rango]);
  const slots = useMemo(() => {
    const lista: number[] = [];
    for (let m = rango.inicio; m < rango.fin; m += PASO) {
      lista.push(m);
    }
    return lista;
  }, [rango]);
  const y = (min: number): number => (min - rango.inicio) * ESCALA;

  // Al abrir, llevar la vista a la hora actual (o al primer turno), una sola vez por rango.
  const primerTurno = columnas
    .flatMap((c) => c.turnos)
    .map((t) => minutosLocales(t.inicio, zona))
    .sort((a, b) => a - b)[0];
  const ahoraVisible = ahoraMin !== null && ahoraMin >= rango.inicio && ahoraMin <= rango.fin;
  const foco = ahoraVisible ? (ahoraMin as number) : (primerTurno ?? rango.inicio);
  // biome-ignore lint/correctness/useExhaustiveDependencies: solo al cambiar el rango visible
  useEffect(() => {
    const el = contenedor.current;
    if (el) {
      el.scrollTop = Math.max(0, y(foco) - 96);
    }
  }, [rango.inicio, rango.fin]);

  const columnasGrid = `64px repeat(${columnas.length}, minmax(168px, 1fr))`;

  return (
    <div
      ref={contenedor}
      className="relative max-h-[calc(100dvh-15rem)] min-h-[420px] overflow-auto rounded-[14px] border border-border bg-surface shadow-xs"
    >
      <div className="min-w-fit" style={{ display: "grid", gridTemplateColumns: columnasGrid }}>
        {/* encabezado fijo */}
        <div className="sticky left-0 top-0 z-30 border-b border-border bg-surface" />
        {columnas.map((c) => (
          <div
            key={`h-${c.clave}`}
            className="sticky top-0 z-20 border-b border-l border-border bg-surface/95 px-3 py-2.5 backdrop-blur-sm"
          >
            <p
              className={cx(
                "truncate font-heading text-sm font-semibold",
                c.destacar ? "text-primary" : "text-foreground",
              )}
            >
              {c.titulo}
            </p>
            {c.subtitulo ? <p className="truncate text-xs text-muted">{c.subtitulo}</p> : null}
          </div>
        ))}

        {/* eje de horas */}
        <div className="sticky left-0 z-10 bg-surface" style={{ height: alto }}>
          {horas.map((m) => (
            <span
              key={m}
              className="absolute right-2 -translate-y-1/2 text-[11px] font-medium tabular-nums text-muted"
              style={{ top: y(m) }}
            >
              {m === rango.inicio ? "" : minutosAHhmm(m)}
            </span>
          ))}
        </div>

        {columnas.map((c) => {
          const enMinutos = c.turnos.map((t) => ({
            turno: t,
            inicio: minutosEnColumna(t.inicio, c.fecha, zona, "inicio"),
            fin: minutosEnColumna(t.fin, c.fecha, zona, "fin"),
          }));
          // Los cancelados no reservan carril: van atenuados por detrás, a ancho completo.
          const carriles = asignarCarriles(
            enMinutos
              .filter((t) => t.turno.estado !== "cancelado")
              .map((t) => ({ id: t.turno.id, inicio: t.inicio, fin: t.fin })),
          );
          const bloqueos = c.bloqueos.map((b) => ({
            bloqueo: b,
            inicio: Math.max(rango.inicio, minutosEnColumna(b.inicio, c.fecha, zona, "inicio")),
            fin: Math.min(rango.fin, minutosEnColumna(b.fin, c.fecha, zona, "fin")),
          }));
          const bloqueado = (m: number): boolean =>
            bloqueos.some((b) => m < b.fin && m + PASO > b.inicio);
          return (
            <div
              key={`c-${c.clave}`}
              className="relative border-l border-border"
              style={{
                height: alto,
                backgroundImage:
                  "repeating-linear-gradient(to bottom, var(--border) 0 1px, transparent 1px 96px), repeating-linear-gradient(to bottom, color-mix(in srgb, var(--border) 45%, transparent) 0 1px, transparent 1px 24px)",
              }}
            >
              {/* fuera de horario */}
              {c.disponibles &&
                complemento(c.disponibles, rango).map((f) => (
                  <div
                    key={`f-${f.inicio}`}
                    aria-hidden
                    className="absolute inset-x-0 bg-surface-2/80"
                    style={{ top: y(f.inicio), height: (f.fin - f.inicio) * ESCALA }}
                  />
                ))}

              {/* huecos clickeables (teclado: botón "Nuevo turno" de la barra) */}
              {puedeCrear &&
                slots
                  .filter((m) => !bloqueado(m))
                  .map((m) => (
                    <button
                      key={`s-${m}`}
                      type="button"
                      tabIndex={-1}
                      aria-label={`Nuevo turno ${minutosAHhmm(m)} en ${c.titulo}`}
                      onClick={() => onSlot(c, m)}
                      className="group absolute inset-x-1 flex cursor-pointer items-center gap-1 rounded-md px-2 text-[11px] font-medium text-transparent transition-colors duration-100 hover:bg-primary-soft hover:text-primary-hover"
                      style={{ top: y(m) + 1, height: PASO * ESCALA - 2 }}
                    >
                      <Plus aria-hidden className="size-3 opacity-0 group-hover:opacity-100" />
                      {minutosAHhmm(m)}
                    </button>
                  ))}

              {/* bloqueos: no reservables, interceptan el clic */}
              {bloqueos
                .filter((b) => b.fin > b.inicio)
                .map(({ bloqueo, inicio, fin }) => (
                  <div
                    key={`b-${bloqueo.id}`}
                    data-bloqueo={bloqueo.id}
                    title={bloqueo.motivo}
                    className="absolute inset-x-0 z-[5] overflow-hidden border-y border-border bg-[repeating-linear-gradient(135deg,var(--surface-2)_0_7px,var(--background)_7px_14px)] px-2 py-1"
                    style={{ top: y(inicio), height: (fin - inicio) * ESCALA }}
                  >
                    <span className="inline-block max-w-full truncate rounded bg-surface/90 px-1.5 py-0.5 text-[11px] font-medium text-muted">
                      {bloqueo.motivo}
                    </span>
                  </div>
                ))}

              {/* turnos */}
              {enMinutos.map(({ turno, inicio, fin }) => {
                const cancelado = turno.estado === "cancelado";
                const lugar = carriles.get(turno.id) ?? { carril: 0, total: 1 };
                const altoTurno = Math.max((fin - inicio) * ESCALA - 3, 20);
                const compacto = altoTurno < 40;
                const conPrestacion = altoTurno >= 60;
                const origen = ORIGEN[turno.origen];
                const etiqueta = `${horaLocal(turno.inicio, zona)} a ${horaLocal(turno.fin, zona)}, ${turno.paciente_nombre}, ${ETIQUETA_ESTADO[turno.estado] ?? turno.estado}${turno.es_sobreturno ? ", sobreturno" : ""}`;
                return (
                  <button
                    key={turno.id}
                    type="button"
                    aria-label={etiqueta}
                    onClick={() => onTurno(turno)}
                    className={cx(
                      cancelado ? "z-[6]" : "z-10",
                      "absolute cursor-pointer overflow-hidden rounded-lg border border-border border-l-[3px] px-2 py-1 text-left shadow-xs",
                      "transition-[box-shadow,transform] duration-150 ease-suave hover:z-20 hover:-translate-y-px hover:shadow-md",
                      ESTILO_TURNO[turno.estado] ?? ESTILO_TURNO.reservado,
                      turno.es_sobreturno &&
                        "outline-1 outline-offset-[-3px] outline-dashed outline-warning",
                      resaltado === turno.id && "motion-safe:animate-[resaltar_900ms_ease-out_2]",
                    )}
                    style={{
                      top: y(inicio) + 1.5,
                      height: altoTurno,
                      left: `calc(${(lugar.carril / lugar.total) * 100}% + 4px)`,
                      width: `calc(${100 / lugar.total}% - 8px)`,
                    }}
                  >
                    <span
                      className={cx(
                        "flex items-center gap-1 text-[11px] font-medium tabular-nums text-muted",
                        turno.estado === "cancelado" && "line-through",
                      )}
                    >
                      {horaLocal(turno.inicio, zona)}
                      {compacto ? (
                        <span className="truncate font-semibold text-foreground">
                          {turno.paciente_nombre}
                        </span>
                      ) : null}
                      {origen ? (
                        <origen.Icono aria-hidden className="ml-auto size-3 shrink-0" />
                      ) : null}
                    </span>
                    {!compacto && (
                      <>
                        <span
                          className={cx(
                            "block truncate text-[13px] font-semibold leading-tight text-foreground",
                            turno.estado === "cancelado" && "line-through",
                          )}
                        >
                          {turno.paciente_nombre}
                        </span>
                        {conPrestacion ? (
                          <span className="block truncate text-xs text-muted">
                            {turno.es_sobreturno ? "Sobreturno · " : ""}
                            {turno.prestacion_nombre}
                          </span>
                        ) : null}
                      </>
                    )}
                  </button>
                );
              })}

              {/* ahora */}
              {c.esHoy &&
                ahoraMin !== null &&
                ahoraMin >= rango.inicio &&
                ahoraMin <= rango.fin && (
                  <div
                    aria-hidden
                    className="pointer-events-none absolute inset-x-0 z-[15] h-0.5 bg-accent"
                    style={{ top: y(ahoraMin) }}
                  >
                    <span className="absolute -left-1 -top-[3px] size-2 rounded-full bg-accent" />
                  </div>
                )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
