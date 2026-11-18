import {
  ChevronRight,
  ClipboardList,
  History,
  IdCard,
  Mail,
  Paperclip,
  Phone,
  ShieldAlert,
  ShieldCheck,
  ShieldPlus,
  Smile,
} from "lucide-react";
import { Link, Outlet, useLoaderData, useParams, useRevalidator } from "react-router";

import { requireSession, useSesion } from "@/features/auth/session";
import { apiFetch } from "@/shared/api/client";
import { cargarSeguro, type Resultado } from "@/shared/api/resultado";
import { fecha } from "@/shared/formato";
import { Avatar } from "@/shared/ui/Avatar";
import { Aviso } from "@/shared/ui/Aviso";
import { cx } from "@/shared/ui/cx";
import { TEXTO_SIN_CONSENTIMIENTO } from "@/shared/ui/EstadoSeccion";
import { Tabs } from "@/shared/ui/Tabs";
import { useEstadoDesde } from "@/shared/useEstadoDesde";

import type { Historia, Paciente, Pagina, Profesional } from "../tipos";
import type { ContextoPaciente } from "./contexto";

interface Datos {
  paciente: Resultado<Paciente>;
  historia: Resultado<Historia>;
  profesionales: Profesional[];
}

export async function loader({
  params,
  request,
}: {
  params: { pacienteId?: string };
  request: Request;
}): Promise<Datos> {
  await requireSession(new URL(request.url));
  const id = params.pacienteId;
  const [paciente, historia, profesionales] = await Promise.all([
    cargarSeguro(apiFetch<Paciente>(`/api/pacientes/${id}`)),
    cargarSeguro(apiFetch<Historia>(`/api/pacientes/${id}/historia`)),
    cargarSeguro(apiFetch<Pagina<Profesional>>("/api/catalogo/profesionales?limit=200")),
  ]);
  return {
    paciente,
    historia,
    profesionales: profesionales.tipo === "ok" ? profesionales.datos.items : [],
  };
}

const TABS = [
  ["ficha", "Ficha", <ClipboardList key="f" />],
  ["odontograma", "Odontograma", <Smile key="o" />],
  ["evoluciones", "Evoluciones", <History key="e" />],
  ["adjuntos", "Adjuntos", <Paperclip key="a" />],
] as const;

export function Component() {
  const datos = useLoaderData() as Datos;
  const yo = useSesion();
  const { pacienteId } = useParams();
  const revalidator = useRevalidator();
  const [paciente, setPaciente] = useEstadoDesde(
    datos.paciente.tipo === "ok" ? datos.paciente.datos : null,
  );
  const [historia, setHistoria] = useEstadoDesde(datos.historia);

  if (paciente === null || yo === null) {
    return (
      <section className="rounded-[18px] border border-border bg-surface p-6 shadow-xs">
        <h1 className="text-xl font-semibold">
          {datos.paciente.tipo === "no-encontrado"
            ? "Paciente no encontrado"
            : "No pudimos cargar el paciente"}
        </h1>
        <p className="mt-2">
          <Link className="font-medium text-primary hover:underline" to="/pacientes">
            Volver a pacientes
          </Link>
        </p>
        {datos.paciente.tipo !== "no-encontrado" && (
          <button
            type="button"
            className="mt-3 h-9 cursor-pointer rounded-lg border border-border bg-surface px-3 text-sm font-medium hover:bg-surface-2"
            onClick={() => void revalidator.revalidate()}
          >
            Reintentar
          </button>
        )}
      </section>
    );
  }

  const contexto: ContextoPaciente = {
    paciente,
    setPaciente,
    historia,
    actualizarHistoria: (f) => {
      if (historia.tipo === "ok") {
        setHistoria({ tipo: "ok", datos: f(historia.datos) });
      }
    },
    profesionales: datos.profesionales,
    yo,
    reintentar: () => void revalidator.revalidate(),
  };

  return (
    <section className="space-y-5">
      <title>{`${paciente.apellido}, ${paciente.nombre} · Turnos Odontología`}</title>
      <nav aria-label="Migas" className="flex items-center gap-1.5 text-[13px] text-muted">
        <Link className="hover:text-foreground hover:underline" to="/pacientes">
          Pacientes
        </Link>
        <ChevronRight aria-hidden className="size-3.5" />
        <span className="truncate text-foreground">
          {paciente.apellido}, {paciente.nombre}
        </span>
      </nav>
      <section
        aria-label="Paciente"
        className="rounded-[18px] border border-border bg-surface p-5 shadow-xs sm:p-6"
      >
        <div className="flex flex-wrap items-start gap-4">
          <Avatar nombre={paciente.nombre} apellido={paciente.apellido} tamano="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-semibold sm:text-[28px]">
              {paciente.apellido}, {paciente.nombre}
            </h1>
            <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-sm text-muted">
              <span className="inline-flex items-center gap-1.5 tabular-nums">
                <IdCard aria-hidden className="size-4" />
                DNI {paciente.dni}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Phone aria-hidden className="size-4" />
                {paciente.telefono ?? "sin teléfono"}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Mail aria-hidden className="size-4" />
                {paciente.email ?? "sin email"}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <ShieldPlus aria-hidden className="size-4" />
                {paciente.obra_social_nombre ?? "Sin obra social"}
                {paciente.obra_social_plan ? ` (${paciente.obra_social_plan})` : ""}
              </span>
            </p>
          </div>
          <p
            className={cx(
              "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium",
              paciente.consentimiento_datos
                ? "bg-success-soft text-success"
                : "bg-warning-soft text-warning",
            )}
          >
            {paciente.consentimiento_datos ? (
              <ShieldCheck aria-hidden className="size-3.5" />
            ) : (
              <ShieldAlert aria-hidden className="size-3.5" />
            )}
            {paciente.consentimiento_datos
              ? `Consentimiento de datos: otorgado${
                  paciente.consentimiento_datos_at
                    ? ` el ${fecha(paciente.consentimiento_datos_at)}`
                    : ""
                }`
              : "Consentimiento de datos: no otorgado"}
          </p>
        </div>
        {!paciente.consentimiento_datos && (
          <Aviso tipo="alerta" className="mt-4">
            {TEXTO_SIN_CONSENTIMIENTO}
          </Aviso>
        )}
      </section>
      <Tabs
        etiqueta="Secciones del paciente"
        pestanas={TABS.map(([ruta, titulo, icono]) => ({
          to: `/pacientes/${pacienteId}/${ruta}`,
          etiqueta: titulo,
          icono,
        }))}
      />
      <div className="motion-safe:animate-[fundido_200ms_var(--ease-suave)]" key={pacienteId}>
        <Outlet context={contexto} />
      </div>
    </section>
  );
}
