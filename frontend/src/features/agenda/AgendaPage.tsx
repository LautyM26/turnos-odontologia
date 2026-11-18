/**
 * Agenda del staff (C-07, US-001/US-002 lado UI): Día por sillón y Semana por profesional.
 * Estado en la URL (`fecha`, `vista`, `profesional`) para deep-link y botón atrás.
 * El odontólogo ve fija su propia agenda y no da turnos (POST /api/turnos es de staff).
 */

import { CalendarPlus, ChevronLeft, ChevronRight, RefreshCw, UserRoundX } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { useSesion } from "@/features/auth/session";
import { Aviso } from "@/shared/ui/Aviso";
import { Button } from "@/shared/ui/Button";
import { cx } from "@/shared/ui/cx";
import { EmptyState } from "@/shared/ui/EmptyState";
import { Select } from "@/shared/ui/Field";
import { Skeleton } from "@/shared/ui/Skeleton";

import { type AgendaTurno, type Catalogo, cargarCatalogo, type Horario } from "./api";
import { type ColumnaGrilla, Grilla } from "./Grilla";
import { PanelAlta, type ValoresAlta } from "./PanelAlta";
import { PanelDetalle } from "./PanelDetalle";
import {
  diaSemana,
  etiquetaFecha,
  fechaLocal,
  hhmmAMinutos,
  instanteLocal,
  minutosLocales,
  type Rango,
  rangoVisible,
  semanaDe,
  sumarDias,
  ventanaDia,
} from "./tiempo";
import { puedeGestionar } from "./transiciones";
import { useAgenda, ZONA_POR_DEFECTO } from "./useAgenda";

type Vista = "dia" | "semana";

function franjasDelDia(horarios: Horario[], fecha: string): Rango[] {
  const dia = diaSemana(fecha);
  return horarios.flatMap((h) =>
    h.franjas
      .filter((f) => f.dia_semana === dia)
      .map((f) => ({ inicio: hhmmAMinutos(f.inicio), fin: hhmmAMinutos(f.fin) })),
  );
}

function useAhora(): Date {
  const [ahora, setAhora] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setAhora(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);
  return ahora;
}

export function Component() {
  const me = useSesion();
  const roles = me?.roles ?? [];
  const gestion = puedeGestionar(roles);
  const [params, setParams] = useSearchParams();
  const ahora = useAhora();
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null);
  const [errorCatalogo, setErrorCatalogo] = useState<string | null>(null);
  const [alta, setAlta] = useState<ValoresAlta | null>(null);
  const [detalle, setDetalle] = useState<AgendaTurno | null>(null);
  const [resaltado, setResaltado] = useState<number | null>(null);
  const [anuncio, setAnuncio] = useState("");

  const zonaUi = ZONA_POR_DEFECTO;
  const hoy = fechaLocal(ahora, zonaUi);
  const fecha = /^\d{4}-\d{2}-\d{2}$/.test(params.get("fecha") ?? "")
    ? (params.get("fecha") as string)
    : hoy;
  const vista: Vista = params.get("vista") === "semana" ? "semana" : "dia";
  const profParam = params.get("profesional");

  useEffect(() => {
    const control = new AbortController();
    cargarCatalogo(control.signal)
      .then(setCatalogo)
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) {
          setErrorCatalogo("No pudimos cargar sillones y profesionales.");
        }
      });
    return () => control.abort();
  }, []);

  const profesionales = useMemo(
    () => (catalogo?.profesionales ?? []).filter((p) => p.agenda_activa),
    [catalogo],
  );
  // Odontólogo sin rol de gestión: su profesional (vinculado por usuario_id) queda fijo.
  const propio = !gestion ? (profesionales.find((p) => p.usuario_id === me?.sub) ?? null) : null;
  const profesionalId: number | null = propio
    ? propio.id
    : profParam !== null && profesionales.some((p) => p.id === Number(profParam))
      ? Number(profParam)
      : vista === "semana"
        ? (profesionales[0]?.id ?? null)
        : null;

  const dias = vista === "semana" ? semanaDe(fecha) : [fecha];
  const desde = catalogo ? instanteLocal(dias[0] as string, 0, zonaUi) : null;
  const hasta = catalogo ? ventanaDia(dias[dias.length - 1] as string, zonaUi).hasta : null;
  const sinVinculo = catalogo !== null && !gestion && propio === null;
  const idsHorario = profesionalId !== null ? [profesionalId] : profesionales.map((p) => p.id);

  const { datos, cargando, error, recargar } = useAgenda(
    sinVinculo ? null : desde,
    sinVinculo ? null : hasta,
    profesionalId,
    catalogo ? idsHorario : [],
  );
  const zona = datos?.zona ?? zonaUi;

  const cambiar = useCallback(
    (cambios: Record<string, string | null>) => {
      setParams(
        (prev) => {
          const siguiente = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(cambios)) {
            if (v === null) {
              siguiente.delete(k);
            } else {
              siguiente.set(k, v);
            }
          }
          return siguiente;
        },
        { replace: false },
      );
    },
    [setParams],
  );

  const mover = (pasos: number): void =>
    cambiar({ fecha: sumarDias(fecha, pasos * (vista === "semana" ? 7 : 1)) });

  const columnas: ColumnaGrilla[] = useMemo(() => {
    if (!catalogo || !datos) {
      return [];
    }
    const horariosPorProf = (id: number | null): Horario[] =>
      id === null ? datos.horarios : datos.horarios.filter((h) => h.profesional_id === id);
    if (vista === "semana") {
      return dias.map((d) => ({
        clave: d,
        titulo: etiquetaFecha(d, zona, { weekday: "short", day: "numeric" }),
        subtitulo: etiquetaFecha(d, zona, { month: "short" }),
        fecha: d,
        sillonId: null,
        profesionalId,
        esHoy: d === hoy,
        destacar: d === hoy,
        turnos: datos.turnos.filter((t) => fechaLocal(t.inicio, zona) === d),
        bloqueos: datos.bloqueos.filter(
          (b) =>
            b.alcance !== "sillon" &&
            fechaLocal(b.inicio, zona) <= d &&
            fechaLocal(new Date(new Date(b.fin).getTime() - 1), zona) >= d,
        ),
        disponibles: franjasDelDia(horariosPorProf(profesionalId), d),
      }));
    }
    const disponibles = franjasDelDia(horariosPorProf(profesionalId), fecha);
    return catalogo.sillones.map((s) => ({
      clave: String(s.id),
      titulo: s.nombre,
      subtitulo: s.tipo === "box" ? "Box" : s.tipo === "equipo" ? "Equipo" : "Sillón",
      fecha,
      sillonId: s.id,
      profesionalId,
      esHoy: fecha === hoy,
      turnos: datos.turnos.filter((t) => t.sillon_id === s.id),
      bloqueos: datos.bloqueos.filter(
        (b) =>
          b.alcance === "clinica" ||
          (b.alcance === "sillon" && b.sillon_id === s.id) ||
          (b.alcance === "profesional" &&
            profesionalId !== null &&
            b.profesional_id === profesionalId),
      ),
      disponibles: datos.horarios.length > 0 ? disponibles : null,
    }));
  }, [catalogo, datos, vista, dias, fecha, hoy, profesionalId, zona]);

  const rango = useMemo(() => {
    const franjas = columnas.flatMap((c) => c.disponibles ?? []);
    const ocupados = (datos?.turnos ?? []).map((t) => ({
      inicio: minutosLocales(t.inicio, zona),
      fin: Math.max(minutosLocales(t.fin, zona), minutosLocales(t.inicio, zona) + 15),
    }));
    return rangoVisible(franjas, ocupados);
  }, [columnas, datos, zona]);

  const turnosVisibles = columnas.flatMap((c) => c.turnos);
  const resumen = {
    total: turnosVisibles.filter((t) => t.estado !== "cancelado").length,
    confirmados: turnosVisibles.filter((t) => t.estado === "confirmado").length,
    online: turnosVisibles.filter((t) => t.origen === "enlace" && t.estado !== "cancelado").length,
    sobreturnos: turnosVisibles.filter((t) => t.es_sobreturno && t.estado !== "cancelado").length,
  };

  const titulo =
    vista === "semana"
      ? `Semana del ${etiquetaFecha(dias[0] as string, zona, { day: "numeric", month: "long" })}`
      : etiquetaFecha(fecha, zona, { weekday: "long", day: "numeric", month: "long" });

  function nuevoTurno(): void {
    const ahoraMin = minutosLocales(ahora, zona);
    const proximo =
      fecha === hoy ? Math.ceil((ahoraMin + 1) / 15) * 15 : Math.max(rango.inicio, 9 * 60);
    setAlta({ fecha, minutos: Math.min(proximo, 23 * 60 + 45), sillonId: null, profesionalId });
  }

  if (errorCatalogo) {
    return <Aviso tipo="error">{errorCatalogo}</Aviso>;
  }

  return (
    <section aria-labelledby="titulo-agenda" className="space-y-4">
      <title>Agenda · Turnos Odontología</title>
      <div aria-live="polite" className="sr-only">
        {anuncio}
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 id="titulo-agenda" className="text-2xl font-semibold sm:text-[28px]">
            Agenda
          </h1>
          <p className="mt-0.5 text-sm text-muted first-letter:uppercase">{titulo}</p>
        </div>
        {gestion && (
          <Button onClick={nuevoTurno} icono={<CalendarPlus />} disabled={!catalogo}>
            Nuevo turno
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-[14px] border border-border bg-surface p-2 shadow-xs">
        <div className="flex items-center gap-1">
          <Button variante="secondary" tamano="sm" onClick={() => cambiar({ fecha: hoy })}>
            Hoy
          </Button>
          <button
            type="button"
            aria-label={vista === "semana" ? "Semana anterior" : "Día anterior"}
            onClick={() => mover(-1)}
            className="grid size-8 cursor-pointer place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
          >
            <ChevronLeft aria-hidden className="size-4" />
          </button>
          <button
            type="button"
            aria-label={vista === "semana" ? "Semana siguiente" : "Día siguiente"}
            onClick={() => mover(1)}
            className="grid size-8 cursor-pointer place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
          >
            <ChevronRight aria-hidden className="size-4" />
          </button>
          <label className="sr-only" htmlFor="agenda-fecha">
            Fecha
          </label>
          <input
            id="agenda-fecha"
            type="date"
            value={fecha}
            onChange={(e) => e.target.value && cambiar({ fecha: e.target.value })}
            className="h-8 cursor-pointer rounded-lg border border-border bg-surface px-2 text-[13px] tabular-nums hover:border-border-strong"
          />
        </div>

        <fieldset className="flex rounded-lg bg-surface-2 p-0.5">
          <legend className="sr-only">Vista</legend>
          {(["dia", "semana"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={vista === v}
              onClick={() => cambiar({ vista: v === "dia" ? null : "semana" })}
              className={cx(
                "h-7 cursor-pointer rounded-md px-3 text-[13px] font-medium transition-all duration-150",
                vista === v
                  ? "bg-surface text-foreground shadow-xs"
                  : "text-muted hover:text-foreground",
              )}
            >
              {v === "dia" ? "Día" : "Semana"}
            </button>
          ))}
        </fieldset>

        {gestion ? (
          <div className="min-w-48">
            <label className="sr-only" htmlFor="agenda-prof">
              Profesional
            </label>
            <Select
              id="agenda-prof"
              className="h-8 text-[13px]"
              value={profesionalId ?? ""}
              onChange={(e) => cambiar({ profesional: e.target.value || null })}
            >
              {vista === "dia" && <option value="">Todos los profesionales</option>}
              {profesionales.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </Select>
          </div>
        ) : propio ? (
          <span className="rounded-lg bg-primary-soft px-2.5 py-1 text-[13px] font-medium text-primary-hover">
            Mi agenda · {propio.nombre}
          </span>
        ) : null}

        <div className="ml-auto flex items-center gap-3">
          {datos && (
            <dl className="hidden items-center gap-4 text-[13px] md:flex">
              <div className="flex items-baseline gap-1.5">
                <dt className="text-muted">Turnos</dt>
                <dd className="font-semibold tabular-nums">{resumen.total}</dd>
              </div>
              <div className="flex items-baseline gap-1.5">
                <dt className="text-muted">Confirmados</dt>
                <dd className="font-semibold tabular-nums text-primary">{resumen.confirmados}</dd>
              </div>
              <div className="flex items-baseline gap-1.5">
                <dt className="text-muted">Online</dt>
                <dd className="font-semibold tabular-nums text-accent">{resumen.online}</dd>
              </div>
              {resumen.sobreturnos > 0 && (
                <div className="flex items-baseline gap-1.5">
                  <dt className="text-muted">Sobreturnos</dt>
                  <dd className="font-semibold tabular-nums text-warning">{resumen.sobreturnos}</dd>
                </div>
              )}
            </dl>
          )}
          <button
            type="button"
            aria-label="Actualizar agenda"
            onClick={() => void recargar()}
            className="grid size-8 cursor-pointer place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
          >
            <RefreshCw aria-hidden className={cx("size-4", cargando && datos && "animate-spin")} />
          </button>
        </div>
      </div>

      {error ? <Aviso tipo="error">{error}</Aviso> : null}

      {sinVinculo ? (
        <EmptyState
          icono={<UserRoundX />}
          titulo="Tu usuario no tiene un profesional vinculado"
          texto="Pedile al administrador que vincule tu usuario a un profesional para ver tu agenda."
        />
      ) : !catalogo || (cargando && !datos) ? (
        <div
          className="space-y-2 rounded-[14px] border border-border bg-surface p-4"
          aria-busy="true"
        >
          <span className="sr-only">Cargando agenda…</span>
          <Skeleton className="h-8 w-full" />
          {["s1", "s2", "s3", "s4", "s5", "s6"].map((k) => (
            <Skeleton key={k} className="h-16 w-full" />
          ))}
        </div>
      ) : catalogo.sillones.length === 0 ? (
        <EmptyState
          icono={<CalendarPlus />}
          titulo="Todavía no hay sillones cargados"
          texto="Cargá sillones y profesionales desde la administración para empezar a dar turnos."
        />
      ) : (
        <div
          key={`${vista}-${fecha}-${profesionalId ?? "todos"}`}
          className="motion-safe:animate-[fundido_180ms_var(--ease-suave)]"
        >
          <Grilla
            columnas={columnas}
            rango={rango}
            zona={zona}
            ahoraMin={dias.includes(hoy) ? minutosLocales(ahora, zona) : null}
            puedeCrear={gestion}
            resaltado={resaltado}
            onSlot={(c, minutos) =>
              setAlta({
                fecha: c.fecha,
                minutos,
                sillonId: c.sillonId,
                profesionalId: c.profesionalId ?? profesionalId,
              })
            }
            onTurno={setDetalle}
          />
        </div>
      )}

      {catalogo && alta && (
        <PanelAlta
          abierto={alta !== null}
          valores={alta}
          catalogo={catalogo}
          zona={zona}
          onCerrar={() => setAlta(null)}
          onConflicto={() => void recargar()}
          onCreado={(id) => {
            setAlta(null);
            setResaltado(id);
            setAnuncio("Turno creado.");
            void recargar();
          }}
        />
      )}

      {catalogo && (
        <PanelDetalle
          turno={detalle}
          catalogo={catalogo}
          zona={zona}
          roles={roles}
          ahora={ahora}
          onCerrar={() => setDetalle(null)}
          onCambio={(mensaje) => {
            setDetalle(null);
            setAnuncio(mensaje);
            void recargar();
          }}
        />
      )}
    </section>
  );
}
