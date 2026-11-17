import type { Me, Rol } from "@/features/clinica/tipos";

const ETIQUETAS: Record<Rol, string> = {
  admin: "Administrador",
  odontologo: "Odontólogo",
  recepcionista: "Recepcionista",
  "paciente-enlace": "Enlace paciente",
};

/** "Administrador, Odontólogo" para mostrar en la barra superior. */
export function rolesLegibles(me: Me): string {
  return me.roles.map((r) => ETIQUETAS[r]).join(", ");
}
