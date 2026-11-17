import type { Me } from "./tipos";

/** Solo para mostrar u ocultar controles: la autoridad real es el backend (403). */
export function puedeEscribirClinica(yo: Me): boolean {
  return yo.roles.includes("odontologo");
}

export function puedeCorregir(
  evolucion: { autor_usuario_id: number; corregida_por_id: number | null },
  yo: Me,
): boolean {
  return (
    puedeEscribirClinica(yo) &&
    evolucion.autor_usuario_id === yo.sub &&
    evolucion.corregida_por_id === null
  );
}
