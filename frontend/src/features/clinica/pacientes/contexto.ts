import { useOutletContext } from "react-router";

import type { Resultado } from "@/shared/api/resultado";

import type { Historia, Me, Paciente, Profesional } from "../tipos";

/** Datos compartidos por las pestañas (D5): estado local alimentado por el loader. */
export interface ContextoPaciente {
  paciente: Paciente;
  setPaciente: (p: Paciente) => void;
  historia: Resultado<Historia>;
  /** Aplica una mutación local (versión nueva, evolución nueva) sin volver a pedir la historia. */
  actualizarHistoria: (f: (h: Historia) => Historia) => void;
  profesionales: Profesional[];
  yo: Me;
  /** Vuelve a ejecutar el loader (Reintentar). */
  reintentar: () => void;
}

export function useContextoPaciente(): ContextoPaciente {
  return useOutletContext<ContextoPaciente>();
}
