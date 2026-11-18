/**
 * Landing de producto (C-20 D2, spec product-landing). Sin pedidos a la API.
 * Capturas reales de la app con datos sintéticos (`public/landing/`, regla dura 14).
 * Motion: reveal al scroll y una tarjeta flotante; todo cede ante prefers-reduced-motion.
 */

import {
  ArrowRight,
  CalendarCheck2,
  CalendarDays,
  CircleCheck,
  FileLock2,
  MessageCircle,
  Smartphone,
  Stethoscope,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { Link } from "react-router";

import { useReveal } from "@/shared/ui/useReveal";

const RESERVA_DEMO = "/reservar/clinica-piloto";

const escalon = (i: number): CSSProperties => ({ "--i": i }) as CSSProperties;

function Captura({
  src,
  alt,
  ancho,
  alto,
  className = "",
  prioridad = false,
}: {
  src: string;
  alt: string;
  ancho: number;
  alto: number;
  className?: string;
  prioridad?: boolean;
}) {
  return (
    <img
      src={src}
      alt={alt}
      width={ancho}
      height={alto}
      loading={prioridad ? "eager" : "lazy"}
      decoding="async"
      className={`block h-auto w-full ${className}`}
    />
  );
}

function Diferencial({
  icono,
  titulo,
  texto,
  className = "",
  i,
  children,
}: {
  icono: ReactNode;
  titulo: string;
  texto: string;
  className?: string;
  i: number;
  children?: ReactNode;
}) {
  return (
    <article
      data-reveal
      style={escalon(i)}
      className={`group relative flex flex-col overflow-hidden rounded-[20px] border border-border p-6 transition-shadow duration-300 hover:shadow-md ${className}`}
    >
      <span
        aria-hidden
        className="mb-4 grid size-10 place-items-center rounded-xl bg-surface text-primary shadow-xs [&>svg]:size-5"
      >
        {icono}
      </span>
      <h3 className="text-lg font-semibold">{titulo}</h3>
      <p className="mt-1.5 max-w-[46ch] text-sm leading-relaxed text-muted">{texto}</p>
      {children}
    </article>
  );
}

export function HomePage() {
  const ref = useReveal<HTMLDivElement>();
  return (
    <div ref={ref}>
      <title>Turnos Odontología · Gestión de clínicas odontológicas</title>

      {/* Hero partido */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -top-40 h-[480px] bg-[radial-gradient(60%_60%_at_70%_30%,var(--primary-soft),transparent_70%)]"
        />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-14 sm:px-6 lg:grid-cols-[1fr_1.15fr] lg:pt-20">
          <div>
            <p
              data-reveal
              style={escalon(0)}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-muted"
            >
              <Stethoscope aria-hidden className="size-3.5 text-primary" />
              Para consultorios y clínicas odontológicas
            </p>
            <h1
              data-reveal
              style={escalon(1)}
              className="mt-5 text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl"
            >
              Turnos Odontología
            </h1>
            <p
              data-reveal
              style={escalon(2)}
              className="mt-5 max-w-[34ch] text-lg leading-relaxed text-muted sm:text-xl"
            >
              La agenda de tu clínica por sillón, sin superposiciones, con reserva online y historia
              clínica en un solo lugar.
            </p>
            <div data-reveal style={escalon(3)} className="mt-8 flex flex-wrap gap-3">
              <Link
                to={RESERVA_DEMO}
                className="group inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-5 font-medium text-primary-foreground shadow-sm transition-[background-color,transform] duration-150 hover:bg-primary-hover active:translate-y-px"
              >
                Reservar turno
                <ArrowRight
                  aria-hidden
                  className="size-4 transition-transform duration-200 group-hover:translate-x-0.5"
                />
              </Link>
              <Link
                to="/login"
                className="inline-flex h-12 items-center rounded-xl border border-border bg-surface px-5 font-medium shadow-xs transition-colors hover:bg-surface-2"
              >
                Ingresar
              </Link>
            </div>
          </div>

          <div data-reveal style={escalon(2)} className="relative">
            <div className="overflow-hidden rounded-[20px] border border-border bg-surface shadow-lg">
              <Captura
                src="/landing/agenda.png"
                alt="Agenda del día con una columna por sillón, turnos confirmados, reservas online y un bloqueo de mantenimiento"
                ancho={1440}
                alto={900}
                prioridad
              />
            </div>
            <div className="absolute -bottom-6 -left-4 hidden w-64 rounded-2xl border border-border bg-surface/95 p-4 shadow-md backdrop-blur sm:block motion-safe:animate-[flotar_6s_ease-in-out_infinite]">
              <div className="flex items-start gap-3">
                <span
                  aria-hidden
                  className="grid size-9 shrink-0 place-items-center rounded-full bg-success-soft text-success"
                >
                  <CircleCheck className="size-5" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold">Turno confirmado</p>
                  <p className="mt-0.5 text-xs text-muted">El paciente respondió por WhatsApp</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Diferenciales: bento asimétrico de 5 */}
      <section aria-labelledby="diferenciales" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2
          id="diferenciales"
          data-reveal
          className="max-w-[22ch] text-3xl font-semibold tracking-tight sm:text-4xl"
        >
          Todo lo que pasa en el consultorio, ordenado
        </h2>
        <div className="mt-10 grid gap-4 md:grid-cols-6">
          <Diferencial
            i={0}
            icono={<CalendarDays />}
            titulo="Agenda por sillón, sin superposiciones"
            texto="Cada turno ocupa un profesional y un sillón. La base de datos impide los choques, incluso con dos reservas al mismo tiempo."
            className="bg-surface md:col-span-4 md:row-span-2"
          >
            <div className="relative mt-6 min-h-60 flex-1 overflow-hidden rounded-xl border border-border">
              <Captura
                src="/landing/semana.png"
                alt="Vista semanal de la agenda de un profesional"
                ancho={1440}
                alto={900}
                className="absolute inset-0 h-full object-cover object-left-top"
              />
            </div>
          </Diferencial>
          <Diferencial
            i={1}
            icono={<Smartphone />}
            titulo="Reserva online sin cuenta"
            texto="El paciente elige un horario real desde el celular con su DNI. Puede cancelar o reprogramar con su enlace."
            className="bg-primary-soft md:col-span-2"
          >
            <div className="mx-auto mt-5 w-40 overflow-hidden rounded-[18px] border border-border shadow-sm">
              <Captura
                src="/landing/reserva-movil.png"
                alt="Pantalla de reserva online en un celular"
                ancho={390}
                alto={844}
              />
            </div>
          </Diferencial>
          <Diferencial
            i={2}
            icono={<Stethoscope />}
            titulo="Historia clínica con odontograma"
            texto="Odontograma FDI, evoluciones que no se pueden borrar y adjuntos, con acceso clínico solo para el profesional."
            className="bg-surface md:col-span-2"
          />
          <Diferencial
            i={3}
            icono={<MessageCircle />}
            titulo="Recordatorios por WhatsApp"
            texto="El recordatorio llega el día anterior y el paciente confirma, cancela o reprograma respondiendo el mensaje."
            className="bg-surface md:col-span-3"
          />
          <Diferencial
            i={4}
            icono={<FileLock2 />}
            titulo="Cumplimiento legal"
            texto="Consentimientos firmados con constancia, privacidad de datos de salud y exportación completa de la información."
            className="bg-accent-soft md:col-span-3"
          >
            <p className="mt-4 flex flex-wrap gap-2 text-xs font-medium">
              {["Ley 26.529", "Ley 25.326", "Ley 25.506"].map((ley) => (
                <span
                  key={ley}
                  className="rounded-md bg-surface px-2 py-1 text-foreground shadow-xs"
                >
                  {ley}
                </span>
              ))}
            </p>
          </Diferencial>
        </div>
      </section>

      {/* Cómo funciona */}
      <section aria-labelledby="como" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 id="como" data-reveal className="text-3xl font-semibold tracking-tight sm:text-4xl">
            Cómo funciona
          </h2>
          <ol className="relative mt-10 grid gap-8 md:grid-cols-3">
            <span
              aria-hidden
              className="absolute left-5 right-5 top-5 hidden h-px bg-border md:block"
            />
            {[
              {
                titulo: "Reservá",
                texto: "El paciente elige un hueco real de la agenda, sin crear cuenta.",
                Icono: Smartphone,
              },
              {
                titulo: "Confirmá",
                texto: "El recordatorio por WhatsApp confirma el turno o libera el horario.",
                Icono: MessageCircle,
              },
              {
                titulo: "Atendé",
                texto: "El odontólogo registra la evolución y el odontograma en la ficha.",
                Icono: CalendarCheck2,
              },
            ].map(({ titulo, texto, Icono }, i) => (
              <li key={titulo} data-reveal style={escalon(i)} className="relative">
                <span
                  aria-hidden
                  className="relative grid size-10 place-items-center rounded-full border border-border bg-background text-primary"
                >
                  <Icono className="size-[18px]" />
                </span>
                <h3 className="mt-4 text-lg font-semibold">{titulo}</h3>
                <p className="mt-1 max-w-[32ch] text-sm leading-relaxed text-muted">{texto}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* CTA final */}
      <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <div
          data-reveal
          className="relative overflow-hidden rounded-[24px] bg-primary px-6 py-12 text-primary-foreground sm:px-12"
        >
          <div
            aria-hidden
            className="pointer-events-none absolute -right-20 -top-20 size-72 rounded-full bg-primary-foreground/10"
          />
          <h2 className="max-w-[20ch] text-3xl font-semibold tracking-tight sm:text-4xl">
            Probá la reserva como paciente
          </h2>
          <p className="mt-3 max-w-[48ch] opacity-90">
            Elegí un horario de la clínica de demostración. Los datos son sintéticos.
          </p>
          <Link
            to={RESERVA_DEMO}
            className="mt-7 inline-flex h-12 items-center gap-2 rounded-xl bg-primary-foreground px-5 font-medium text-primary transition-transform duration-150 hover:-translate-y-px active:translate-y-0"
          >
            Reservar turno
            <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}
