/**
 * Tiempo en la zona de la clínica (C-07 D6), sin librerías: `Intl.DateTimeFormat` con
 * `timeZone`. Las fechas de calendario viajan como "YYYY-MM-DD" (fecha local de la clínica).
 */

const DIA_MS = 24 * 60 * 60 * 1000;
const DIAS_SEMANA: Record<string, number> = {
  Mon: 1,
  Tue: 2,
  Wed: 3,
  Thu: 4,
  Fri: 5,
  Sat: 6,
  Sun: 7,
};

export interface PartesLocales {
  anio: number;
  mes: number;
  dia: number;
  hora: number;
  minuto: number;
  diaSemana: number;
}

const formateadores = new Map<string, Intl.DateTimeFormat>();

function formateador(zona: string): Intl.DateTimeFormat {
  let f = formateadores.get(zona);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone: zona,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      weekday: "short",
    });
    formateadores.set(zona, f);
  }
  return f;
}

export function partesLocales(instante: Date | string, zona: string): PartesLocales {
  const partes = formateador(zona).formatToParts(new Date(instante));
  const valor = (tipo: string): string => partes.find((p) => p.type === tipo)?.value ?? "0";
  return {
    anio: Number(valor("year")),
    mes: Number(valor("month")),
    dia: Number(valor("day")),
    hora: Number(valor("hour")) % 24,
    minuto: Number(valor("minute")),
    diaSemana: DIAS_SEMANA[valor("weekday")] ?? 1,
  };
}

export function minutosLocales(instante: Date | string, zona: string): number {
  const p = partesLocales(instante, zona);
  return p.hora * 60 + p.minuto;
}

const dos = (n: number): string => String(n).padStart(2, "0");

export function fechaLocal(instante: Date | string, zona: string): string {
  const p = partesLocales(instante, zona);
  return `${p.anio}-${dos(p.mes)}-${dos(p.dia)}`;
}

function aUtc(fecha: string): number {
  const [a, m, d] = fecha.split("-").map(Number);
  return Date.UTC(a ?? 1970, (m ?? 1) - 1, d ?? 1);
}

export function sumarDias(fecha: string, n: number): string {
  const t = new Date(aUtc(fecha) + n * DIA_MS);
  return `${t.getUTCFullYear()}-${dos(t.getUTCMonth() + 1)}-${dos(t.getUTCDate())}`;
}

/** Día ISO (1 = lunes) de una fecha de calendario. */
export function diaSemana(fecha: string): number {
  const d = new Date(aUtc(fecha)).getUTCDay();
  return d === 0 ? 7 : d;
}

/** Instante (UTC) que en la zona de la clínica es `fecha` a los `minutos` desde la medianoche. */
export function instanteLocal(fecha: string, minutos: number, zona: string): Date {
  const deseado = aUtc(fecha) + minutos * 60_000;
  let candidato = deseado;
  for (let i = 0; i < 2; i += 1) {
    const p = partesLocales(new Date(candidato), zona);
    const visto = Date.UTC(p.anio, p.mes - 1, p.dia, p.hora, p.minuto);
    candidato += deseado - visto;
  }
  return new Date(candidato);
}

export function ventanaDia(fecha: string, zona: string): { desde: Date; hasta: Date } {
  return {
    desde: instanteLocal(fecha, 0, zona),
    hasta: instanteLocal(sumarDias(fecha, 1), 0, zona),
  };
}

/** Los 7 días (lunes a domingo) de la semana que contiene `fecha`. */
export function semanaDe(fecha: string): string[] {
  const lunes = sumarDias(fecha, 1 - diaSemana(fecha));
  return Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i));
}

export function hhmmAMinutos(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

export function minutosAHhmm(min: number): string {
  return `${dos(Math.floor(min / 60) % 24)}:${dos(min % 60)}`;
}

export interface Rango {
  inicio: number;
  fin: number;
}

/**
 * Rango visible en minutos: unión de franjas de los días mostrados y de los turnos (para no
 * ocultar sobreturnos fuera de horario), redondeado a la hora; 08–20 si no hay nada.
 */
export function rangoVisible(franjas: Rango[], ocupados: Rango[]): Rango {
  const todos = [...franjas, ...ocupados];
  if (todos.length === 0) {
    return { inicio: 8 * 60, fin: 20 * 60 };
  }
  const inicio = Math.min(...todos.map((r) => r.inicio));
  const fin = Math.max(...todos.map((r) => r.fin));
  return { inicio: Math.floor(inicio / 60) * 60, fin: Math.min(24 * 60, Math.ceil(fin / 60) * 60) };
}

const ETIQUETA_DIA = new Map<string, Intl.DateTimeFormat>();

export function etiquetaFecha(
  fecha: string,
  zona: string,
  opciones: Intl.DateTimeFormatOptions,
): string {
  const clave = `${zona}|${JSON.stringify(opciones)}`;
  let f = ETIQUETA_DIA.get(clave);
  if (!f) {
    f = new Intl.DateTimeFormat("es-AR", { timeZone: zona, ...opciones });
    ETIQUETA_DIA.set(clave, f);
  }
  // mediodía local: evita saltos de fecha por la conversión
  return f.format(instanteLocal(fecha, 12 * 60, zona));
}

export function horaLocal(instante: string, zona: string): string {
  return minutosAHhmm(minutosLocales(instante, zona));
}
