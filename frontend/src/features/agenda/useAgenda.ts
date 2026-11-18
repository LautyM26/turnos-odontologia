/**
 * Datos de la agenda (C-07 D7): turnos, bloqueos y horarios en PARALELO (regla dura 13),
 * recarga cada 60 s y al volver a la pestaña. Cancela pedidos viejos con AbortController.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  type AgendaBloqueo,
  type AgendaTurno,
  type Horario,
  listarBloqueos,
  listarTurnos,
  obtenerHorario,
} from "./api";

export const ZONA_POR_DEFECTO = "America/Argentina/Buenos_Aires";
export const REFRESCO_MS = 60_000;

export interface DatosAgenda {
  turnos: AgendaTurno[];
  bloqueos: AgendaBloqueo[];
  horarios: Horario[];
  zona: string;
}

interface Estado {
  datos: DatosAgenda | null;
  cargando: boolean;
  error: string | null;
}

export function useAgenda(
  desde: Date | null,
  hasta: Date | null,
  profesionalFiltro: number | null,
  profesionalesHorario: number[],
): Estado & { recargar: () => Promise<void> } {
  const [estado, setEstado] = useState<Estado>({ datos: null, cargando: true, error: null });
  const control = useRef<AbortController | null>(null);
  const claveHorarios = profesionalesHorario.join(",");
  const desdeMs = desde?.getTime() ?? null;
  const hastaMs = hasta?.getTime() ?? null;

  const cargar = useCallback(
    async (silencioso: boolean): Promise<void> => {
      if (desdeMs === null || hastaMs === null) {
        return;
      }
      control.current?.abort();
      const actual = new AbortController();
      control.current = actual;
      if (!silencioso) {
        setEstado((e) => ({ ...e, cargando: true, error: null }));
      }
      const ids = claveHorarios === "" ? [] : claveHorarios.split(",").map(Number);
      try {
        const [turnos, bloqueos, ...horarios] = await Promise.all([
          listarTurnos(new Date(desdeMs), new Date(hastaMs), profesionalFiltro, actual.signal),
          listarBloqueos(new Date(desdeMs), new Date(hastaMs), profesionalFiltro, actual.signal),
          ...ids.map((id) => obtenerHorario(id, actual.signal)),
        ]);
        if (actual.signal.aborted) {
          return;
        }
        setEstado({
          datos: {
            turnos: turnos as AgendaTurno[],
            bloqueos: bloqueos as AgendaBloqueo[],
            horarios: horarios as Horario[],
            zona: (horarios[0] as Horario | undefined)?.zona_horaria ?? ZONA_POR_DEFECTO,
          },
          cargando: false,
          error: null,
        });
      } catch (e) {
        if (actual.signal.aborted || (e instanceof DOMException && e.name === "AbortError")) {
          return;
        }
        setEstado((prev) => ({
          ...prev,
          cargando: false,
          error: "No pudimos cargar la agenda. Revisá la conexión y volvé a intentar.",
        }));
      }
    },
    [desdeMs, hastaMs, profesionalFiltro, claveHorarios],
  );

  useEffect(() => {
    void cargar(false);
    return () => control.current?.abort();
  }, [cargar]);

  useEffect(() => {
    const intervalo = setInterval(() => void cargar(true), REFRESCO_MS);
    const alVolver = (): void => {
      if (document.visibilityState === "visible") {
        void cargar(true);
      }
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => {
      clearInterval(intervalo);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [cargar]);

  const recargar = useCallback(() => cargar(true), [cargar]);
  return { ...estado, recargar };
}
