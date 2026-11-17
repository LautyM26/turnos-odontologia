/** Interpreta el campo único de búsqueda: DNI, teléfono o texto libre (spec patients-web). */

export type Busqueda =
  | { tipo: "todos" }
  | { tipo: "corta" }
  | { tipo: "dni" | "telefono" | "q"; param: "dni" | "telefono" | "q"; valor: string };

export function interpretarBusqueda(texto: string): Busqueda {
  const valor = texto.trim();
  if (valor === "") {
    return { tipo: "todos" };
  }
  const digitos = valor.replace(/\D/g, "").length;
  if (/^[\d.]+$/.test(valor) && (digitos === 7 || digitos === 8)) {
    return { tipo: "dni", param: "dni", valor };
  }
  if (/^[\d\s()+-]+$/.test(valor) && (valor.startsWith("+") || digitos >= 10)) {
    return { tipo: "telefono", param: "telefono", valor };
  }
  return valor.length < 3 ? { tipo: "corta" } : { tipo: "q", param: "q", valor };
}
