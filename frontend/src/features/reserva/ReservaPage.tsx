/** Comprobante de la reserva por enlace (C-06): ver, reprogramar (C-20) y cancelar con el token, sin cuenta. */

import { CalendarClock } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { ApiError } from "@/shared/api/client";
import { Aviso } from "@/shared/ui/Aviso";
import { DialogoConfirmacion } from "@/shared/ui/DialogoConfirmacion";
import { Skeleton } from "@/shared/ui/Skeleton";

import { cancelarReserva, obtenerReserva, type ReservaPublica } from "./api";
import { DetalleTurno } from "./DetalleTurno";

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
    return <ReservaNoEncontrada />;
  }

  return (
    <section className="mx-auto max-w-xl px-4 py-10 sm:py-14">
      <title>Tu turno · Turnos Odontología</title>
      <h1 className="text-3xl font-bold tracking-tight">Tu turno</h1>
      <div aria-live="polite" className="mt-4">
        {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
      </div>
      {reserva === null ? (
        !aviso && (
          <div aria-busy="true" className="mt-6 space-y-3">
            <span className="sr-only">Cargando…</span>
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        )
      ) : (
        <>
          <div className="mt-6">
            <DetalleTurno reserva={reserva} />
          </div>
          {reserva.estado !== "cancelado" && (
            <p className="mt-4 text-sm text-muted">
              Guardá este enlace: con él podés ver, reprogramar o cancelar tu turno. No lo
              compartas.
            </p>
          )}
          {reserva.cancelable && (
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to={`/reprogramar/${encodeURIComponent(token)}`}
                className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary px-4 font-medium text-primary-foreground shadow-xs transition-[background-color,transform] duration-150 hover:bg-primary-hover active:translate-y-px"
              >
                <CalendarClock aria-hidden className="size-4" />
                Reprogramar
              </Link>
              <button
                type="button"
                className="inline-flex h-11 cursor-pointer items-center rounded-xl border border-danger/40 bg-surface px-4 font-medium text-danger transition-colors hover:bg-danger-soft disabled:cursor-not-allowed disabled:opacity-60"
                disabled={cancelando}
                onClick={() => setConfirmando(true)}
              >
                {cancelando ? "Cancelando…" : "Cancelar turno"}
              </button>
            </div>
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

export function ReservaNoEncontrada() {
  return (
    <section className="mx-auto max-w-xl px-4 py-16">
      <title>Reserva no encontrada · Turnos Odontología</title>
      <h1 className="text-2xl font-semibold">Reserva no encontrada</h1>
      <p className="mt-2 text-muted">Revisá que el enlace esté completo.</p>
    </section>
  );
}
