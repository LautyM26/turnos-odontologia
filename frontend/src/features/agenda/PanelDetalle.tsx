/**
 * Detalle del turno y cambios de estado (C-07 D8): solo los botones que la tabla de
 * transiciones y el rol permiten; la API decide y su mensaje (422/403) se muestra tal cual.
 */

import {
  Armchair,
  CalendarDays,
  ClipboardList,
  ExternalLink,
  Stethoscope,
  UserRound,
} from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";
import { Link } from "react-router";

import type { Rol } from "@/features/clinica/tipos";
import { ApiError } from "@/shared/api/client";
import { Aviso } from "@/shared/ui/Aviso";
import { Button } from "@/shared/ui/Button";
import { DialogoConfirmacion } from "@/shared/ui/DialogoConfirmacion";
import { Drawer } from "@/shared/ui/Drawer";
import { EstadoBadge } from "@/shared/ui/EstadoBadge";

import { type AgendaTurno, type Catalogo, transicionar } from "./api";
import { etiquetaFecha, fechaLocal, horaLocal } from "./tiempo";
import { accionesPermitidas } from "./transiciones";

const ORIGEN: Record<string, string> = {
  mostrador: "Mostrador",
  enlace: "Reserva online",
  whatsapp: "WhatsApp",
  lista_espera: "Lista de espera",
};

interface Props {
  turno: AgendaTurno | null;
  catalogo: Catalogo;
  zona: string;
  roles: readonly Rol[];
  ahora: Date;
  onCerrar: () => void;
  onCambio: (mensaje: string) => void;
}

function Dato({
  icono,
  etiqueta,
  children,
}: {
  icono: ReactNode;
  etiqueta: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 py-2.5">
      <span aria-hidden className="mt-0.5 text-muted [&>svg]:size-4">
        {icono}
      </span>
      <div className="min-w-0">
        <dt className="text-xs text-muted">{etiqueta}</dt>
        <dd className="text-sm font-medium">{children}</dd>
      </div>
    </div>
  );
}

export function PanelDetalle({ turno, catalogo, zona, roles, ahora, onCerrar, onCambio }: Props) {
  const ids = useId();
  const [enviando, setEnviando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmarCancelar, setConfirmarCancelar] = useState(false);
  const [motivo, setMotivo] = useState("");

  // biome-ignore lint/correctness/useExhaustiveDependencies: reiniciar solo al cambiar de turno
  useEffect(() => {
    setError(null);
    setMotivo("");
    setConfirmarCancelar(false);
  }, [turno?.id]);

  if (turno === null) {
    return (
      <Drawer abierto={false} titulo="Turno" onCerrar={onCerrar}>
        {null}
      </Drawer>
    );
  }

  const acciones = accionesPermitidas(turno.estado, roles, ahora >= new Date(turno.inicio));
  const profesional = catalogo.profesionales.find((p) => p.id === turno.profesional_id);
  const sillon = catalogo.sillones.find((s) => s.id === turno.sillon_id);

  async function aplicar(estado: string, motivoCancelacion?: string): Promise<void> {
    if (turno === null) {
      return;
    }
    setEnviando(estado);
    setError(null);
    try {
      await transicionar(turno.id, estado, motivoCancelacion);
      onCambio(
        `Turno de ${turno.paciente_nombre}: ${estado === "confirmado" ? "confirmado" : estado}.`,
      );
    } catch (e) {
      setError(
        e instanceof ApiError ? e.detail : "No pudimos cambiar el estado. Intentá de nuevo.",
      );
    } finally {
      setEnviando(null);
    }
  }

  const pie =
    acciones.length > 0 ? (
      <div className="flex w-full flex-wrap justify-end gap-2">
        {acciones.map((a) =>
          a.estado === "cancelado" ? (
            <Button
              key={a.estado}
              variante="danger"
              onClick={() => setConfirmarCancelar(true)}
              disabled={enviando !== null}
            >
              {a.etiqueta}
            </Button>
          ) : (
            <Button
              key={a.estado}
              variante={a.estado === "confirmado" ? "primary" : "secondary"}
              cargando={enviando === a.estado}
              disabled={enviando !== null && enviando !== a.estado}
              onClick={() => void aplicar(a.estado)}
            >
              {a.etiqueta}
            </Button>
          ),
        )}
      </div>
    ) : undefined;

  return (
    <>
      <Drawer
        abierto
        titulo={turno.paciente_nombre}
        descripcion={
          <span className="flex items-center gap-2">
            <EstadoBadge estado={turno.estado} />
            {turno.es_sobreturno ? (
              <span className="rounded-md border border-dashed border-warning px-1.5 py-0.5 text-xs font-medium text-warning">
                Sobreturno
              </span>
            ) : null}
          </span>
        }
        onCerrar={onCerrar}
        {...(pie ? { pie } : {})}
      >
        <div className="rounded-[14px] bg-surface-2 px-4 py-4">
          <p className="font-heading text-2xl font-semibold tabular-nums tracking-tight">
            {horaLocal(turno.inicio, zona)} a {horaLocal(turno.fin, zona)}
          </p>
          <p className="mt-0.5 text-sm text-muted first-letter:uppercase">
            {etiquetaFecha(fechaLocal(turno.inicio, zona), zona, {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </p>
        </div>

        <dl className="mt-4 divide-y divide-border">
          <Dato icono={<UserRound />} etiqueta="Paciente">
            <Link
              to={`/pacientes/${turno.paciente_id}`}
              className="inline-flex items-center gap-1 text-primary hover:underline"
            >
              {turno.paciente_nombre}
              <ExternalLink aria-hidden className="size-3.5" />
            </Link>
          </Dato>
          <Dato icono={<ClipboardList />} etiqueta="Prestación">
            {turno.prestacion_nombre}
          </Dato>
          <Dato icono={<Stethoscope />} etiqueta="Profesional">
            {profesional?.nombre ?? `Profesional #${turno.profesional_id}`}
          </Dato>
          <Dato icono={<Armchair />} etiqueta="Sillón">
            {sillon?.nombre ?? `Sillón #${turno.sillon_id}`}
          </Dato>
          <Dato icono={<CalendarDays />} etiqueta="Origen">
            {ORIGEN[turno.origen] ?? turno.origen}
          </Dato>
        </dl>

        {turno.es_sobreturno && turno.motivo_sobreturno ? (
          <p className="mt-3 rounded-[10px] border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-warning">
            Motivo del sobreturno: {turno.motivo_sobreturno}
          </p>
        ) : null}

        <div aria-live="polite" className="mt-4">
          {error ? <Aviso tipo="error">{error}</Aviso> : null}
          {acciones.length === 0 ? (
            <p className="text-sm text-muted">
              {turno.estado === "cancelado" ||
              turno.estado === "asistido" ||
              turno.estado === "ausente"
                ? "Este turno ya está cerrado."
                : "Las acciones de este turno están disponibles desde su horario de inicio."}
            </p>
          ) : null}
        </div>
      </Drawer>

      <DialogoConfirmacion
        abierto={confirmarCancelar}
        titulo="¿Cancelar el turno?"
        confirmar="Sí, cancelar"
        cancelar="Volver"
        onCancelar={() => setConfirmarCancelar(false)}
        onConfirmar={() => {
          setConfirmarCancelar(false);
          void aplicar("cancelado", motivo.trim() || undefined);
        }}
      >
        <p>El horario queda libre para otro paciente.</p>
        <label
          htmlFor={`${ids}-motivo`}
          className="mt-3 block text-[13px] font-medium text-foreground"
        >
          Motivo (opcional)
        </label>
        <textarea
          id={`${ids}-motivo`}
          maxLength={500}
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          className="mt-1 min-h-16 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-3 focus:ring-focus"
        />
      </DialogoConfirmacion>
    </>
  );
}
