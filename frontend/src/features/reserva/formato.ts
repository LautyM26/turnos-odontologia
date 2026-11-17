/** Fechas en la zona horaria de la clínica (no la del navegador): el turno es presencial. */

export function fechaLarga(iso: string, zona: string): string {
  return new Intl.DateTimeFormat("es-AR", {
    timeZone: zona,
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(iso));
}

export function hora(iso: string, zona: string): string {
  return new Intl.DateTimeFormat("es-AR", {
    timeZone: zona,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

/** Agrupa inicios por día local de la clínica, conservando el orden del servidor. */
export function porDia<T extends { inicio: string }>(items: T[], zona: string): [string, T[]][] {
  const grupos = new Map<string, T[]>();
  for (const item of items) {
    const dia = fechaLarga(item.inicio, zona);
    grupos.set(dia, [...(grupos.get(dia) ?? []), item]);
  }
  return [...grupos.entries()];
}
