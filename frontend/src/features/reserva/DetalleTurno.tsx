/** Datos del turno para el paciente (comprobante y reprogramación), en la zona de la clínica. */

import { CalendarDays, Clock, MapPin, Stethoscope, UserRound } from "lucide-react";
import type { ReactNode } from "react";

import type { ReservaPublica } from "./api";
import { fechaLarga, hora } from "./formato";

const ESTADOS: Record<string, string> = {
  reservado: "Reservado",
  confirmado: "Confirmado",
  cancelado: "Cancelado",
  asistido: "Atendido",
  ausente: "Ausente",
};

const PUNTO: Record<string, string> = {
  reservado: "bg-muted",
  confirmado: "bg-primary",
  cancelado: "bg-danger",
  asistido: "bg-success",
  ausente: "bg-warning",
};

function Fila({
  icono,
  etiqueta,
  children,
}: {
  icono: ReactNode;
  etiqueta: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 py-3">
      <span aria-hidden className="mt-0.5 text-muted [&>svg]:size-4">
        {icono}
      </span>
      <dt className="w-24 shrink-0 text-sm text-muted">{etiqueta}</dt>
      <dd className="min-w-0 font-medium">{children}</dd>
    </div>
  );
}

export function DetalleTurno({ reserva }: { reserva: ReservaPublica }) {
  const zona = reserva.zona_horaria;
  return (
    <div className="rounded-[18px] border border-border bg-surface shadow-xs">
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <p className="flex items-center gap-2 text-lg font-semibold">
          <CalendarDays aria-hidden className="size-5 text-primary" />
          <span className="inline-block first-letter:uppercase">
            {fechaLarga(reserva.inicio, zona)}
          </span>
        </p>
        <span className="inline-flex items-center gap-1.5 rounded-md bg-surface-2 px-2 py-1 text-xs font-medium">
          <span
            aria-hidden
            className={`size-1.5 rounded-full ${PUNTO[reserva.estado] ?? "bg-muted"}`}
          />
          {ESTADOS[reserva.estado] ?? reserva.estado}
        </span>
      </div>
      <dl className="divide-y divide-border px-5">
        <Fila icono={<MapPin />} etiqueta="Clínica">
          {reserva.clinica}
        </Fila>
        <Fila icono={<UserRound />} etiqueta="Profesional">
          {reserva.profesional}
        </Fila>
        <Fila icono={<Stethoscope />} etiqueta="Prestación">
          {reserva.prestacion}
        </Fila>
        <Fila icono={<Clock />} etiqueta="Horario">
          <span className="tabular-nums">{`${hora(reserva.inicio, zona)} a ${hora(reserva.fin, zona)} hs`}</span>
        </Fila>
      </dl>
    </div>
  );
}
