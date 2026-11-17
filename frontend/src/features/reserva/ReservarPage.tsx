/**
 * Reserva online sin cuenta (C-06, US-003, Flujo 1): prestación + profesional → huecos reales de
 * la semana → datos mínimos → confirmación. Ante un 409 recarga huecos y conserva lo cargado.
 * Nada se guarda en el navegador: el token vive solo en la URL del comprobante.
 */

import { type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ApiError } from "@/shared/api/client";
import { Aviso } from "@/shared/ui/Aviso";

import {
  type CatalogoPublico,
  crearReserva,
  type HuecoPublico,
  obtenerCatalogo,
  obtenerHuecos,
} from "./api";
import { fechaLarga, hora, porDia } from "./formato";

const DIA_MS = 24 * 60 * 60 * 1000;

interface Datos {
  dni: string;
  nombre: string;
  apellido: string;
  email: string;
  telefono: string;
  privacidad: boolean;
}

const VACIO: Datos = {
  dni: "",
  nombre: "",
  apellido: "",
  email: "",
  telefono: "",
  privacidad: false,
};

function inicioDeSemana(semana: number): Date {
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  return new Date(hoy.getTime() + semana * 7 * DIA_MS);
}

function mensaje(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) {
      return error.detail === "Horario no disponible"
        ? "Ese horario se acaba de ocupar. Elegí otro de la lista actualizada."
        : error.detail;
    }
    if (error.status === 429) {
      return "Hiciste muchos pedidos seguidos. Esperá un minuto y volvé a intentar.";
    }
    if (error.status === 422) {
      return `Revisá los datos: ${error.detail}`;
    }
  }
  return "No pudimos completar la reserva. Revisá tu conexión e intentá de nuevo.";
}

const CAMPO = "mt-1 w-full rounded-md border border-border bg-background px-3 py-2";
const ETIQUETA = "block text-sm font-medium";

export function Component() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const [catalogo, setCatalogo] = useState<CatalogoPublico | null>(null);
  const [noEncontrado, setNoEncontrado] = useState(false);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [prestacionId, setPrestacionId] = useState<number | null>(null);
  const [profesionalId, setProfesionalId] = useState<number | null>(null);
  const [semana, setSemana] = useState(0);
  const [huecos, setHuecos] = useState<HuecoPublico[] | null>(null);
  const [elegido, setElegido] = useState<HuecoPublico | null>(null);
  const [datos, setDatos] = useState<Datos>(VACIO);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [campos, setCampos] = useState<Record<string, string>>({});
  const formulario = useRef<HTMLFormElement>(null);

  useEffect(() => {
    obtenerCatalogo(slug)
      .then(setCatalogo)
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) {
          setNoEncontrado(true);
        } else {
          setErrorCarga("No pudimos cargar la clínica. Intentá de nuevo en unos minutos.");
        }
      });
  }, [slug]);

  const cargarHuecos = useCallback(async () => {
    if (prestacionId === null || profesionalId === null) {
      setHuecos(null);
      return;
    }
    const desde = inicioDeSemana(semana);
    setHuecos(null);
    try {
      const lista = await obtenerHuecos(
        slug,
        profesionalId,
        prestacionId,
        desde,
        new Date(desde.getTime() + 7 * DIA_MS),
      );
      setHuecos(lista);
    } catch (e) {
      setHuecos([]);
      setError(mensaje(e));
    }
  }, [slug, prestacionId, profesionalId, semana]);

  useEffect(() => {
    setElegido(null);
    void cargarHuecos();
  }, [cargarHuecos]);

  // En móvil la lista de horarios es larga: llevar al formulario al elegir uno.
  useEffect(() => {
    if (elegido === null) {
      return;
    }
    const reducido = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    formulario.current?.scrollIntoView?.({
      behavior: reducido ? "auto" : "smooth",
      block: "start",
    });
  }, [elegido]);

  async function confirmar(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    if (elegido === null || prestacionId === null || profesionalId === null) {
      return;
    }
    setEnviando(true);
    setError(null);
    setCampos({});
    try {
      const reserva = await crearReserva(slug, {
        profesional_id: profesionalId,
        prestacion_id: prestacionId,
        inicio: elegido.inicio,
        dni: datos.dni.trim(),
        nombre: datos.nombre.trim(),
        apellido: datos.apellido.trim(),
        ...(datos.email.trim() ? { email: datos.email.trim() } : {}),
        ...(datos.telefono.trim() ? { telefono: datos.telefono.trim() } : {}),
        acepta_privacidad: true,
      });
      await navigate(`/reserva/${encodeURIComponent(reserva.token)}`);
    } catch (e) {
      setError(mensaje(e));
      if (e instanceof ApiError && e.campos) {
        setCampos(e.campos);
      }
      if (e instanceof ApiError && e.status === 409) {
        setElegido(null);
        await cargarHuecos();
      }
      setEnviando(false);
      formulario.current?.focus();
    }
  }

  if (noEncontrado) {
    return (
      <section className="mx-auto max-w-2xl px-4 py-12">
        <title>Enlace no encontrado · Turnos Odontología</title>
        <h1 className="text-2xl font-semibold">Enlace no encontrado</h1>
        <p className="mt-2 text-muted">
          Revisá el enlace que te compartió la clínica o pedile uno nuevo.
        </p>
      </section>
    );
  }
  if (catalogo === null) {
    return (
      <section className="mx-auto max-w-2xl px-4 py-12" aria-busy={errorCarga === null}>
        <h1 className="text-2xl font-semibold">Reservar turno</h1>
        {errorCarga ? (
          <Aviso tipo="error" className="mt-4">
            {errorCarga}
          </Aviso>
        ) : (
          <p className="mt-2 text-muted">Cargando…</p>
        )}
      </section>
    );
  }

  const zona = catalogo.zona_horaria;
  const actualizar = (campo: keyof Datos) => (e: { target: { value: string } }) =>
    setDatos((d) => ({ ...d, [campo]: e.target.value }));
  const errorDe = (campo: string) =>
    campos[campo] ? (
      <p id={`${campo}-error`} className="mt-1 text-sm text-danger">
        {campos[campo]}
      </p>
    ) : null;
  const describe = (campo: string) => (campos[campo] ? `${campo}-error` : undefined);

  return (
    <section className="mx-auto max-w-2xl px-4 py-10">
      <title>{`Reservar turno · ${catalogo.clinica}`}</title>
      <p className="text-sm uppercase tracking-wide text-muted">{catalogo.clinica}</p>
      <h1 className="mt-1 text-3xl font-semibold">Reservar turno</h1>
      <p className="mt-2 text-muted">Sin crear cuenta. Te lleva un minuto.</p>

      <fieldset className="mt-8 grid gap-4 sm:grid-cols-2">
        <legend className="sr-only">Qué y con quién</legend>
        <div>
          <label className={ETIQUETA} htmlFor="prestacion">
            Prestación
          </label>
          <select
            id="prestacion"
            className={CAMPO}
            value={prestacionId ?? ""}
            onChange={(e) => setPrestacionId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Elegí una prestación</option>
            {catalogo.prestaciones.map((p) => (
              <option key={p.id} value={p.id}>
                {`${p.nombre} (${p.duracion_min} min)`}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={ETIQUETA} htmlFor="profesional">
            Profesional
          </label>
          <select
            id="profesional"
            className={CAMPO}
            value={profesionalId ?? ""}
            onChange={(e) => setProfesionalId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Elegí un profesional</option>
            {catalogo.profesionales.map((p) => (
              <option key={p.id} value={p.id}>
                {p.especialidad ? `${p.nombre} · ${p.especialidad}` : p.nombre}
              </option>
            ))}
          </select>
        </div>
      </fieldset>

      {prestacionId !== null && profesionalId !== null && (
        <section className="mt-8" aria-labelledby="titulo-horarios">
          <div className="flex items-center justify-between gap-2">
            <h2 id="titulo-horarios" className="text-xl font-semibold">
              Horarios disponibles
            </h2>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded-md border border-border px-3 py-1 text-sm disabled:opacity-50"
                disabled={semana === 0}
                onClick={() => setSemana((s) => s - 1)}
              >
                Semana anterior
              </button>
              <button
                type="button"
                className="rounded-md border border-border px-3 py-1 text-sm"
                onClick={() => setSemana((s) => s + 1)}
              >
                Semana siguiente
              </button>
            </div>
          </div>
          {huecos === null ? (
            <p className="mt-3 text-muted" aria-busy="true">
              Buscando horarios…
            </p>
          ) : huecos.length === 0 ? (
            <p className="mt-3 text-muted">
              No hay horarios libres esta semana. Probá la siguiente.
            </p>
          ) : (
            <div className="mt-4 space-y-5">
              {porDia(huecos, zona).map(([dia, lista]) => (
                <div key={dia}>
                  <h3 className="text-sm font-medium text-muted first-letter:uppercase">{dia}</h3>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {lista.map((h) => {
                      const activo = elegido?.inicio === h.inicio;
                      return (
                        <li key={h.inicio}>
                          <button
                            type="button"
                            aria-pressed={activo}
                            className={`rounded-md border px-3 py-1.5 text-sm tabular-nums transition-colors duration-150 ${
                              activo
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border hover:bg-surface"
                            }`}
                            onClick={() => setElegido(h)}
                          >
                            {hora(h.inicio, zona)}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <div aria-live="polite" className="mt-6">
        {error && (
          <Aviso tipo={error.startsWith("Ese horario") ? "alerta" : "error"}>{error}</Aviso>
        )}
      </div>

      {elegido !== null && (
        <form
          ref={formulario}
          tabIndex={-1}
          className="mt-6 space-y-4 rounded-lg border border-border p-5 motion-safe:animate-[aparecer_150ms_ease-out]"
          onSubmit={confirmar}
          aria-labelledby="titulo-datos"
        >
          <h2 id="titulo-datos" className="text-xl font-semibold">
            Tus datos
          </h2>
          <p className="text-sm text-muted">
            {`Turno: ${fechaLarga(elegido.inicio, zona)}, ${hora(elegido.inicio, zona)} a ${hora(elegido.fin, zona)} hs`}
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className={ETIQUETA} htmlFor="nombre">
                Nombre
              </label>
              <input
                id="nombre"
                className={CAMPO}
                required
                autoComplete="given-name"
                value={datos.nombre}
                onChange={actualizar("nombre")}
                aria-invalid={Boolean(campos.nombre)}
                aria-describedby={describe("nombre")}
              />
              {errorDe("nombre")}
            </div>
            <div>
              <label className={ETIQUETA} htmlFor="apellido">
                Apellido
              </label>
              <input
                id="apellido"
                className={CAMPO}
                required
                autoComplete="family-name"
                value={datos.apellido}
                onChange={actualizar("apellido")}
                aria-invalid={Boolean(campos.apellido)}
                aria-describedby={describe("apellido")}
              />
              {errorDe("apellido")}
            </div>
            <div>
              <label className={ETIQUETA} htmlFor="dni">
                DNI
              </label>
              <input
                id="dni"
                className={CAMPO}
                required
                inputMode="numeric"
                value={datos.dni}
                onChange={actualizar("dni")}
                aria-invalid={Boolean(campos.dni)}
                aria-describedby={describe("dni")}
              />
              {errorDe("dni")}
            </div>
            <div>
              <label className={ETIQUETA} htmlFor="telefono">
                Teléfono
              </label>
              <input
                id="telefono"
                className={CAMPO}
                type="tel"
                autoComplete="tel"
                value={datos.telefono}
                onChange={actualizar("telefono")}
                aria-invalid={Boolean(campos.telefono)}
                aria-describedby={describe("telefono")}
              />
              {errorDe("telefono")}
            </div>
            <div className="sm:col-span-2">
              <label className={ETIQUETA} htmlFor="email">
                Email
              </label>
              <input
                id="email"
                className={CAMPO}
                type="email"
                autoComplete="email"
                value={datos.email}
                onChange={actualizar("email")}
                aria-invalid={Boolean(campos.email)}
                aria-describedby={describe("email")}
              />
              {errorDe("email")}
              <p className="mt-1 text-xs text-muted">Dejanos al menos un teléfono o un email.</p>
            </div>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              required
              checked={datos.privacidad}
              onChange={(e) => setDatos((d) => ({ ...d, privacidad: e.target.checked }))}
            />
            <span>
              Acepto la{" "}
              <Link className="underline" to="/privacidad" target="_blank">
                política de privacidad
              </Link>
              .
            </span>
          </label>
          <button
            type="submit"
            className="w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground transition-opacity disabled:opacity-60"
            disabled={enviando || (!datos.email.trim() && !datos.telefono.trim())}
          >
            {enviando ? "Reservando…" : "Confirmar reserva"}
          </button>
        </form>
      )}
    </section>
  );
}
