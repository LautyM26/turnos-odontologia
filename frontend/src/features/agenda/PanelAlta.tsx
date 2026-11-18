/**
 * Alta de turno desde la agenda (C-07 D8): buscador de paciente + alta rápida, prestación,
 * sobreturno con motivo, y ante un 409 hasta 6 huecos alternativos del mismo día.
 * El fin del turno lo calcula el servidor (regla dura 6): acá solo se muestra la duración.
 */

import { CalendarClock, Search, UserPlus, UserRound, X } from "lucide-react";
import { type FormEvent, useEffect, useId, useMemo, useState } from "react";

import type { Paciente } from "@/features/clinica/tipos";
import { ApiError } from "@/shared/api/client";
import { Aviso } from "@/shared/ui/Aviso";
import { Button } from "@/shared/ui/Button";
import { cx } from "@/shared/ui/cx";
import { Drawer } from "@/shared/ui/Drawer";
import { Field, Input, Select, Textarea } from "@/shared/ui/Field";

import {
  buscarHuecos,
  buscarPacientes,
  type Catalogo,
  crearPaciente,
  crearTurno,
  type Hueco,
} from "./api";
import {
  hhmmAMinutos,
  horaLocal,
  instanteLocal,
  minutosAHhmm,
  minutosLocales,
  ventanaDia,
} from "./tiempo";

export interface ValoresAlta {
  fecha: string;
  minutos: number;
  sillonId: number | null;
  profesionalId: number | null;
}

interface Props {
  abierto: boolean;
  valores: ValoresAlta;
  catalogo: Catalogo;
  zona: string;
  onCerrar: () => void;
  onCreado: (turnoId: number) => void;
  onConflicto: () => void;
}

const MAX_ALTERNATIVAS = 6;

function textoError(e: unknown): string {
  if (e instanceof ApiError) {
    return e.detail;
  }
  return "No pudimos completar la operación. Revisá la conexión e intentá de nuevo.";
}

export function PanelAlta({
  abierto,
  valores,
  catalogo,
  zona,
  onCerrar,
  onCreado,
  onConflicto,
}: Props) {
  const ids = useId();
  const profesionalesActivos = catalogo.profesionales.filter((p) => p.agenda_activa);
  const [profesionalId, setProfesionalId] = useState<number | "">("");
  const [sillonId, setSillonId] = useState<number | "">("");
  const [fecha, setFecha] = useState(valores.fecha);
  const [hora, setHora] = useState(minutosAHhmm(valores.minutos));
  const [prestacionId, setPrestacionId] = useState<number | "">("");
  const [paciente, setPaciente] = useState<Paciente | null>(null);
  const [busqueda, setBusqueda] = useState("");
  const [resultados, setResultados] = useState<Paciente[] | null>(null);
  const [altaRapida, setAltaRapida] = useState(false);
  const [nuevo, setNuevo] = useState({
    nombre: "",
    apellido: "",
    dni: "",
    email: "",
    telefono: "",
  });
  const [errorPaciente, setErrorPaciente] = useState<{
    detalle: string;
    campos: Record<string, string>;
  } | null>(null);
  const [creandoPaciente, setCreandoPaciente] = useState(false);
  const [sobreturno, setSobreturno] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alternativas, setAlternativas] = useState<Hueco[] | null>(null);

  // Reiniciar al abrir con valores nuevos (clic en otro hueco).
  // biome-ignore lint/correctness/useExhaustiveDependencies: reinicio solo al abrir con valores nuevos
  useEffect(() => {
    if (!abierto) {
      return;
    }
    setProfesionalId(valores.profesionalId ?? profesionalesActivos[0]?.id ?? "");
    setSillonId(valores.sillonId ?? catalogo.sillones[0]?.id ?? "");
    setFecha(valores.fecha);
    setHora(minutosAHhmm(valores.minutos));
    setPrestacionId(catalogo.prestaciones[0]?.id ?? "");
    setPaciente(null);
    setBusqueda("");
    setResultados(null);
    setAltaRapida(false);
    setSobreturno(false);
    setMotivo("");
    setError(null);
    setAlternativas(null);
    setErrorPaciente(null);
  }, [abierto, valores]);

  // Búsqueda de pacientes con debounce (nombre o DNI).
  useEffect(() => {
    const texto = busqueda.trim();
    if (texto.length < 2 || paciente) {
      setResultados(null);
      return;
    }
    let vigente = true;
    const t = setTimeout(() => {
      buscarPacientes(texto)
        .then((lista) => vigente && setResultados(lista))
        .catch(() => vigente && setResultados([]));
    }, 250);
    return () => {
      vigente = false;
      clearTimeout(t);
    };
  }, [busqueda, paciente]);

  const prestacion = useMemo(
    () => catalogo.prestaciones.find((p) => p.id === prestacionId),
    [catalogo.prestaciones, prestacionId],
  );

  async function crearNuevoPaciente(): Promise<void> {
    setCreandoPaciente(true);
    setErrorPaciente(null);
    try {
      const creado = await crearPaciente({
        nombre: nuevo.nombre.trim(),
        apellido: nuevo.apellido.trim(),
        dni: nuevo.dni.trim(),
        ...(nuevo.email.trim() ? { email: nuevo.email.trim() } : {}),
        ...(nuevo.telefono.trim() ? { telefono: nuevo.telefono.trim() } : {}),
      });
      setPaciente(creado);
      setAltaRapida(false);
    } catch (e) {
      setErrorPaciente({
        detalle:
          e instanceof ApiError && e.status === 409
            ? "Ya existe un paciente con ese DNI. Buscalo por DNI para elegirlo."
            : textoError(e),
        campos: e instanceof ApiError && e.campos ? e.campos : {},
      });
    } finally {
      setCreandoPaciente(false);
    }
  }

  async function confirmar(ev: FormEvent<HTMLFormElement>): Promise<void> {
    ev.preventDefault();
    if (!paciente || profesionalId === "" || sillonId === "" || prestacionId === "") {
      setError("Completá paciente, profesional, sillón y prestación.");
      return;
    }
    if (sobreturno && !motivo.trim()) {
      setError("El sobreturno necesita un motivo.");
      return;
    }
    setEnviando(true);
    setError(null);
    setAlternativas(null);
    const inicio = instanteLocal(fecha, hhmmAMinutos(hora), zona).toISOString();
    try {
      const turno = await crearTurno({
        profesional_id: profesionalId,
        sillon_id: sillonId,
        paciente_id: paciente.id,
        prestacion_id: prestacionId,
        inicio,
        ...(sobreturno ? { sobreturno: true, motivo_sobreturno: motivo.trim() } : {}),
      });
      onCreado(turno.id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("Ese horario ya no está disponible. Elegí una de estas alternativas:");
        onConflicto();
        try {
          const { desde, hasta } = ventanaDia(fecha, zona);
          const huecos = await buscarHuecos(profesionalId, prestacionId, desde, hasta);
          const pedido = hhmmAMinutos(hora);
          const despues = huecos.filter((h) => minutosLocales(h.inicio, zona) > pedido);
          const antes = huecos.filter((h) => minutosLocales(h.inicio, zona) < pedido).reverse();
          setAlternativas([...despues, ...antes].slice(0, MAX_ALTERNATIVAS));
        } catch {
          setAlternativas([]);
        }
      } else {
        setError(textoError(e));
      }
    } finally {
      setEnviando(false);
    }
  }

  function elegirAlternativa(h: Hueco): void {
    setHora(horaLocal(h.inicio, zona));
    if (sillonId === "" || !h.sillon_ids.includes(sillonId)) {
      setSillonId(h.sillon_ids[0] ?? sillonId);
    }
    setAlternativas(null);
    setError(null);
  }

  const pie = (
    <>
      <Button variante="secondary" onClick={onCerrar}>
        Cancelar
      </Button>
      <Button type="submit" form={`${ids}-form`} cargando={enviando} icono={<CalendarClock />}>
        Crear turno
      </Button>
    </>
  );

  return (
    <Drawer
      abierto={abierto}
      titulo="Nuevo turno"
      descripcion="Dar un turno desde la agenda"
      onCerrar={onCerrar}
      pie={pie}
    >
      <form id={`${ids}-form`} className="space-y-6" onSubmit={confirmar} noValidate>
        <section aria-labelledby={`${ids}-pac`} className="space-y-3">
          <h3 id={`${ids}-pac`} className="text-sm font-semibold">
            Paciente
          </h3>
          {paciente ? (
            <div className="flex items-center gap-3 rounded-[10px] border border-primary/30 bg-primary-soft px-3 py-2.5">
              <span className="grid size-9 place-items-center rounded-full bg-surface text-primary">
                <UserRound aria-hidden className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">
                  {paciente.apellido}, {paciente.nombre}
                </p>
                <p className="text-xs tabular-nums text-muted">DNI {paciente.dni}</p>
              </div>
              <Button variante="ghost" tamano="sm" onClick={() => setPaciente(null)} icono={<X />}>
                Cambiar
              </Button>
            </div>
          ) : altaRapida ? (
            <div className="space-y-3 rounded-[10px] border border-border bg-surface-2/60 p-3">
              {errorPaciente ? <Aviso tipo="error">{errorPaciente.detalle}</Aviso> : null}
              <div className="grid gap-3 sm:grid-cols-2">
                <Field id={`${ids}-n-nombre`} label="Nombre" error={errorPaciente?.campos.nombre}>
                  {(c) => (
                    <Input
                      {...c}
                      value={nuevo.nombre}
                      onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })}
                    />
                  )}
                </Field>
                <Field
                  id={`${ids}-n-apellido`}
                  label="Apellido"
                  error={errorPaciente?.campos.apellido}
                >
                  {(c) => (
                    <Input
                      {...c}
                      value={nuevo.apellido}
                      onChange={(e) => setNuevo({ ...nuevo, apellido: e.target.value })}
                    />
                  )}
                </Field>
                <Field id={`${ids}-n-dni`} label="DNI" error={errorPaciente?.campos.dni}>
                  {(c) => (
                    <Input
                      {...c}
                      inputMode="numeric"
                      value={nuevo.dni}
                      onChange={(e) => setNuevo({ ...nuevo, dni: e.target.value })}
                    />
                  )}
                </Field>
                <Field id={`${ids}-n-tel`} label="Teléfono" error={errorPaciente?.campos.telefono}>
                  {(c) => (
                    <Input
                      {...c}
                      type="tel"
                      value={nuevo.telefono}
                      onChange={(e) => setNuevo({ ...nuevo, telefono: e.target.value })}
                    />
                  )}
                </Field>
                <Field
                  id={`${ids}-n-email`}
                  label="Email"
                  className="sm:col-span-2"
                  error={errorPaciente?.campos.email}
                  ayuda="Al menos teléfono o email."
                >
                  {(c) => (
                    <Input
                      {...c}
                      type="email"
                      value={nuevo.email}
                      onChange={(e) => setNuevo({ ...nuevo, email: e.target.value })}
                    />
                  )}
                </Field>
              </div>
              <div className="flex justify-end gap-2">
                <Button variante="ghost" tamano="sm" onClick={() => setAltaRapida(false)}>
                  Volver a buscar
                </Button>
                <Button
                  tamano="sm"
                  cargando={creandoPaciente}
                  onClick={() => void crearNuevoPaciente()}
                  icono={<UserPlus />}
                >
                  Crear paciente
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <Field
                id={`${ids}-buscar`}
                label="Buscar paciente"
                ayuda="Por apellido, nombre o DNI."
              >
                {(c) => (
                  <div className="relative">
                    <Search
                      aria-hidden
                      className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
                    />
                    <Input
                      {...c}
                      className="pl-9"
                      value={busqueda}
                      autoComplete="off"
                      onChange={(e) => setBusqueda(e.target.value)}
                    />
                  </div>
                )}
              </Field>
              {resultados !== null && (
                <ul
                  aria-label="Resultados de pacientes"
                  className="max-h-52 overflow-y-auto rounded-[10px] border border-border"
                >
                  {resultados.length === 0 ? (
                    <li className="px-3 py-3 text-sm text-muted">
                      Sin resultados para "{busqueda.trim()}".
                    </li>
                  ) : (
                    resultados.map((p) => (
                      <li key={p.id} className="border-b border-border last:border-b-0">
                        <button
                          type="button"
                          onClick={() => setPaciente(p)}
                          className="flex w-full cursor-pointer items-center justify-between gap-3 px-3 py-2.5 text-left text-sm transition-colors hover:bg-surface-2"
                        >
                          <span className="truncate font-medium">
                            {p.apellido}, {p.nombre}
                          </span>
                          <span className="shrink-0 text-xs tabular-nums text-muted">
                            DNI {p.dni}
                          </span>
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              )}
              <Button
                variante="ghost"
                tamano="sm"
                onClick={() => setAltaRapida(true)}
                icono={<UserPlus />}
              >
                Nuevo paciente
              </Button>
            </div>
          )}
        </section>

        <section aria-labelledby={`${ids}-turno`} className="space-y-3">
          <h3 id={`${ids}-turno`} className="text-sm font-semibold">
            Turno
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id={`${ids}-prof`} label="Profesional">
              {(c) => (
                <Select
                  {...c}
                  value={profesionalId}
                  onChange={(e) => setProfesionalId(Number(e.target.value))}
                >
                  {profesionalesActivos.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field id={`${ids}-sillon`} label="Sillón">
              {(c) => (
                <Select
                  {...c}
                  value={sillonId}
                  onChange={(e) => setSillonId(Number(e.target.value))}
                >
                  {catalogo.sillones.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.nombre}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field id={`${ids}-fecha`} label="Fecha">
              {(c) => (
                <Input
                  {...c}
                  type="date"
                  value={fecha}
                  onChange={(e) => setFecha(e.target.value)}
                />
              )}
            </Field>
            <Field id={`${ids}-hora`} label="Hora">
              {(c) => (
                <Input
                  {...c}
                  type="time"
                  step={900}
                  value={hora}
                  onChange={(e) => setHora(e.target.value)}
                />
              )}
            </Field>
            <Field
              id={`${ids}-prest`}
              label="Prestación"
              className="sm:col-span-2"
              ayuda={
                prestacion
                  ? `Dura ${prestacion.duracion_min} min; el fin lo calcula el sistema.`
                  : undefined
              }
            >
              {(c) => (
                <Select
                  {...c}
                  value={prestacionId}
                  onChange={(e) => setPrestacionId(Number(e.target.value))}
                >
                  {catalogo.prestaciones.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre} ({p.duracion_min} min)
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </section>

        <section className="space-y-3 rounded-[10px] border border-border p-3">
          <label className="flex cursor-pointer items-start gap-2.5 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 size-4 cursor-pointer accent-[var(--warning)]"
              checked={sobreturno}
              onChange={(e) => setSobreturno(e.target.checked)}
            />
            <span>
              <span className="font-medium">Sobreturno</span>
              <span className="block text-xs text-muted">
                Se superpone a otros turnos; respeta bloqueos y requiere motivo.
              </span>
            </span>
          </label>
          {sobreturno && (
            <Field id={`${ids}-motivo`} label="Motivo del sobreturno">
              {(c) => (
                <Textarea
                  {...c}
                  maxLength={500}
                  value={motivo}
                  onChange={(e) => setMotivo(e.target.value)}
                />
              )}
            </Field>
          )}
        </section>

        <div aria-live="polite" className="space-y-3">
          {error ? <Aviso tipo={alternativas ? "alerta" : "error"}>{error}</Aviso> : null}
          {alternativas !== null &&
            (alternativas.length === 0 ? (
              <p className="text-sm text-muted">No hay otros horarios libres ese día.</p>
            ) : (
              <ul aria-label="Horarios alternativos" className="flex flex-wrap gap-2">
                {alternativas.map((h) => (
                  <li key={h.inicio}>
                    <button
                      type="button"
                      onClick={() => elegirAlternativa(h)}
                      className={cx(
                        "h-9 cursor-pointer rounded-lg border border-primary/30 bg-primary-soft px-3 text-sm font-medium tabular-nums text-primary-hover",
                        "transition-colors hover:bg-primary hover:text-primary-foreground",
                      )}
                    >
                      {horaLocal(h.inicio, zona)}
                    </button>
                  </li>
                ))}
              </ul>
            ))}
        </div>
      </form>
    </Drawer>
  );
}
