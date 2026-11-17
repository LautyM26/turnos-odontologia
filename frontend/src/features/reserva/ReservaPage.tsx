/** Comprobante de la reserva por enlace (C-06): ver y cancelar con el token, sin cuenta. */

import { useEffect, useState } from "react";
import { useParams } from "react-router";

import { ApiError } from "@/shared/api/client";
import { Aviso } from "@/shared/ui/Aviso";
import { DialogoConfirmacion } from "@/shared/ui/DialogoConfirmacion";

import { cancelarReserva, obtenerReserva, type ReservaPublica } from "./api";
import { fechaLarga, hora } from "./formato";

const ESTADOS: Record<string, string> = {
  reservado: "Reservado",
  confirmado: "Confirmado",
  cancelado: "Cancelado",
  asistido: "Atendido",
  ausente: "Ausente",
};

export function Component() {
  const { token = "" } = useParams();
  const [reserva, setReserva] = useState<ReservaPublica | null>(null);
  const [noEncontrada, setNoEncontrada] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "exito" | "error"; texto: string } | null>(null);

  useEffect(() => {
    obtenerReserva(token)
      .then(setReserva)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) {
          setNoEncontrada(true);
        } else {
          setAviso({ tipo: "error", texto: "No pudimos cargar la reserva. Intentá de nuevo." });
        }
      });
  }, [token]);

  async function cancelar(): Promise<void> {
    setConfirmando(false);
    setCancelando(true);
    try {
      setReserva(await cancelarReserva(token));
      setAviso({ tipo: "exito", texto: "Turno cancelado. El horario quedó libre." });
    } catch (e) {
      const texto =
        e instanceof ApiError && e.status === 422
          ? "Este turno ya no se puede cancelar online. Comunicate con la clínica."
          : "No pudimos cancelar. Intentá de nuevo en unos minutos.";
      setAviso({ tipo: "error", texto });
    } finally {
      setCancelando(false);
    }
  }

  if (noEncontrada) {
    return (
      <section className="mx-auto max-w-xl px-4 py-12">
        <title>Reserva no encontrada · Turnos Odontología</title>
        <h1 className="text-2xl font-semibold">Reserva no encontrada</h1>
        <p className="mt-2 text-muted">Revisá que el enlace esté completo.</p>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-xl px-4 py-10">
      <title>Tu turno · Turnos Odontología</title>
      <h1 className="text-3xl font-semibold">Tu turno</h1>
      <div aria-live="polite" className="mt-4">
        {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
      </div>
      {reserva === null ? (
        !aviso && (
          <p className="mt-2 text-muted" aria-busy="true">
            Cargando…
          </p>
        )
      ) : (
        <>
          <dl className="mt-6 grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 rounded-lg border border-border p-5">
            <dt className="text-muted">Clínica</dt>
            <dd>{reserva.clinica}</dd>
            <dt className="text-muted">Profesional</dt>
            <dd>{reserva.profesional}</dd>
            <dt className="text-muted">Prestación</dt>
            <dd>{reserva.prestacion}</dd>
            <dt className="text-muted">Día</dt>
            <dd className="first-letter:uppercase">
              {fechaLarga(reserva.inicio, reserva.zona_horaria)}
            </dd>
            <dt className="text-muted">Horario</dt>
            <dd className="tabular-nums">
              {`${hora(reserva.inicio, reserva.zona_horaria)} a ${hora(reserva.fin, reserva.zona_horaria)} hs`}
            </dd>
            <dt className="text-muted">Estado</dt>
            <dd className="font-medium">{ESTADOS[reserva.estado] ?? reserva.estado}</dd>
          </dl>
          {reserva.estado !== "cancelado" && (
            <p className="mt-4 text-sm text-muted">
              Guardá este enlace: con él podés ver o cancelar tu turno. No lo compartas.
            </p>
          )}
          {reserva.cancelable && (
            <button
              type="button"
              className="mt-6 rounded-md border border-danger px-4 py-2 font-medium text-danger disabled:opacity-60"
              disabled={cancelando}
              onClick={() => setConfirmando(true)}
            >
              {cancelando ? "Cancelando…" : "Cancelar turno"}
            </button>
          )}
          <DialogoConfirmacion
            abierto={confirmando}
            titulo="¿Cancelar el turno?"
            confirmar="Sí, cancelar"
            cancelar="Volver"
            onConfirmar={() => void cancelar()}
            onCancelar={() => setConfirmando(false)}
          >
            El horario quedará libre para otra persona. Esta acción no se puede deshacer.
          </DialogoConfirmacion>
        </>
      )}
    </section>
  );
}
