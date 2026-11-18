/**
 * Reprogramación por enlace (C-20 D5, spec reschedule-web) sobre la API de C-17: turno actual +
 * hasta 3 opciones; confirmar → turno nuevo. 409 → alternativas de la respuesta. Sin sesión.
 */

import { ArrowLeft, CalendarCheck2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { ApiError } from "@/shared/api/client";
import { Aviso } from "@/shared/ui/Aviso";
import { Skeleton } from "@/shared/ui/Skeleton";

import {
  HorarioOcupado,
  type HuecoPublico,
  obtenerReserva,
  opcionesReprogramacion,
  type ReservaPublica,
  reprogramar,
} from "./api";
import { DetalleTurno } from "./DetalleTurno";
import { fechaLarga, hora } from "./formato";
import { ReservaNoEncontrada } from "./ReservaPage";

const NO_REPROGRAMABLE = "Este turno ya no se puede reprogramar online. Comunicate con la clínica.";
const ESPERAR = "Hiciste muchos pedidos seguidos. Esperá un minuto y volvé a intentar.";

function mensaje(e: unknown, generico: string): string {
  if (e instanceof ApiError && e.status === 429) return ESPERAR;
  if (e instanceof ApiError && e.status === 422) return NO_REPROGRAMABLE;
  return generico;
}

export function Component() {
  const { token = "" } = useParams();
  const comprobante = `/reserva/${encodeURIComponent(token)}`;
  const [reserva, setReserva] = useState<ReservaPublica | null>(null);
  const [opciones, setOpciones] = useState<HuecoPublico[] | null>(null);
  const [elegido, setElegido] = useState<HuecoPublico | null>(null);
  const [noEncontrada, setNoEncontrada] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "error" | "alerta"; texto: string } | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [hecho, setHecho] = useState(false);

  useEffect(() => {
    // Regla dura 13: datos independientes en paralelo.
    void Promise.allSettled([obtenerReserva(token), opcionesReprogramacion(token)]).then(
      ([r, o]) => {
        const es404 = (x: PromiseSettledResult<unknown>) =>
          x.status === "rejected" && x.reason instanceof ApiError && x.reason.status === 404;
        if (es404(r) || es404(o)) {
          setNoEncontrada(true);
          return;
        }
        if (r.status === "rejected") {
          setAviso({
            tipo: "error",
            texto: mensaje(r.reason, "No pudimos cargar el turno. Intentá de nuevo."),
          });
          return;
        }
        setReserva(r.value);
        if (o.status === "fulfilled") {
          setOpciones(o.value);
        } else {
          setOpciones([]);
          setAviso({
            tipo: "error",
            texto: mensaje(o.reason, "No pudimos cargar los horarios. Intentá de nuevo."),
          });
        }
      },
    );
  }, [token]);

  async function confirmar(): Promise<void> {
    if (elegido === null) return;
    setEnviando(true);
    setAviso(null);
    try {
      setReserva(await reprogramar(token, elegido.inicio));
      setHecho(true);
    } catch (e) {
      if (e instanceof HorarioOcupado) {
        setOpciones(e.alternativas);
        setElegido(null);
        setAviso({
          tipo: "alerta",
          texto:
            e.alternativas.length > 0
              ? "Ese horario se acaba de ocupar. Elegí otra de estas opciones."
              : "Ese horario se acaba de ocupar y no quedan otras opciones. Comunicate con la clínica.",
        });
      } else {
        setAviso({
          tipo: "error",
          texto: mensaje(e, "No pudimos reprogramar. Intentá de nuevo en unos minutos."),
        });
      }
    } finally {
      setEnviando(false);
    }
  }

  if (noEncontrada) {
    return <ReservaNoEncontrada />;
  }

  return (
    <section className="mx-auto max-w-xl px-4 py-10 sm:py-14">
      <title>Reprogramar turno · Turnos Odontología</title>
      <Link
        to={comprobante}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-muted transition-colors hover:text-foreground"
      >
        <ArrowLeft aria-hidden className="size-4" />
        Volver al comprobante
      </Link>
      <h1 className="mt-4 text-3xl font-bold tracking-tight">
        {hecho ? "Turno reprogramado" : "Reprogramar turno"}
      </h1>
      {hecho && (
        <p className="mt-2 flex items-center gap-2 text-success">
          <CalendarCheck2 aria-hidden className="size-5" />
          Listo, tu turno tiene un horario nuevo.
        </p>
      )}

      <div className="mt-6">
        {reserva === null ? (
          aviso === null && (
            <div aria-busy="true" className="space-y-3">
              <span className="sr-only">Cargando…</span>
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          )
        ) : (
          <DetalleTurno reserva={reserva} />
        )}
      </div>

      <div aria-live="polite" className="mt-4">
        {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
      </div>

      {hecho ? (
        <Link
          to={comprobante}
          className="mt-6 inline-flex h-11 items-center rounded-xl bg-primary px-4 font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary-hover"
        >
          Ver comprobante
        </Link>
      ) : (
        reserva !== null &&
        opciones !== null &&
        opciones.length > 0 && (
          <section aria-labelledby="titulo-opciones" className="mt-6">
            <h2 id="titulo-opciones" className="text-lg font-semibold">
              Elegí un horario nuevo
            </h2>
            <ul className="mt-3 grid gap-2">
              {opciones.map((o) => {
                const activo = elegido?.inicio === o.inicio;
                return (
                  <li key={o.inicio}>
                    <button
                      type="button"
                      aria-pressed={activo}
                      className={`flex w-full cursor-pointer items-center justify-between gap-3 rounded-xl border px-4 py-3 text-left transition-[background-color,border-color] duration-150 ${
                        activo
                          ? "border-primary bg-primary-soft"
                          : "border-border-control bg-surface hover:border-primary"
                      }`}
                      onClick={() => setElegido(o)}
                    >
                      <span className="inline-block font-medium first-letter:uppercase">
                        {fechaLarga(o.inicio, reserva.zona_horaria)}
                      </span>
                      <span className="tabular-nums text-muted">{`${hora(o.inicio, reserva.zona_horaria)} hs`}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <button
              type="button"
              className="mt-5 inline-flex h-12 w-full cursor-pointer items-center justify-center rounded-xl bg-primary px-4 font-medium text-primary-foreground shadow-sm transition-[background-color,transform] duration-150 hover:bg-primary-hover active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
              disabled={elegido === null || enviando}
              onClick={() => void confirmar()}
            >
              {enviando ? "Reprogramando…" : "Confirmar nuevo horario"}
            </button>
          </section>
        )
      )}
      {!hecho && opciones !== null && opciones.length === 0 && aviso === null && (
        <p className="mt-6 text-muted">
          No hay otros horarios disponibles por ahora.{" "}
          <Link className="font-medium text-primary underline" to={comprobante}>
            Volver al comprobante
          </Link>
        </p>
      )}
    </section>
  );
}
