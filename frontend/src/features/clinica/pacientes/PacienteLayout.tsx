import { Link, NavLink, Outlet, useLoaderData, useParams, useRevalidator } from "react-router";

import { requireSession, useSesion } from "@/features/auth/session";
import { apiFetch } from "@/shared/api/client";
import { cargarSeguro, type Resultado } from "@/shared/api/resultado";
import { fecha } from "@/shared/formato";
import { Aviso } from "@/shared/ui/Aviso";
import { TEXTO_SIN_CONSENTIMIENTO } from "@/shared/ui/EstadoSeccion";
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
  ["ficha", "Ficha"],
  ["odontograma", "Odontograma"],
  ["evoluciones", "Evoluciones"],
  ["adjuntos", "Adjuntos"],
] as const;

const claseTab =
  "inline-block border-b-2 border-transparent px-3 py-2 aria-[current=page]:border-primary aria-[current=page]:font-semibold";

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
      <section>
        <h1 className="text-xl font-semibold">
          {datos.paciente.tipo === "no-encontrado"
            ? "Paciente no encontrado"
            : "No pudimos cargar el paciente"}
        </h1>
        <p className="mt-2">
          <Link className="underline" to="/pacientes">
            Volver a pacientes
          </Link>
        </p>
        {datos.paciente.tipo !== "no-encontrado" && (
          <button
            type="button"
            className="mt-2 rounded border border-border px-3 py-1"
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
    <section>
      <title>{`${paciente.apellido}, ${paciente.nombre} · Turnos Odontología`}</title>
      <nav aria-label="Migas" className="text-sm text-muted">
        <Link className="underline" to="/pacientes">
          Pacientes
        </Link>{" "}
        › {paciente.apellido}, {paciente.nombre}
      </nav>
      <section
        aria-label="Paciente"
        className="mt-2 rounded-md border border-border bg-surface p-4"
      >
        <h1 className="text-2xl font-semibold">
          {paciente.apellido}, {paciente.nombre}
        </h1>
        <p className="mt-1 text-sm">
          DNI {paciente.dni} · {paciente.telefono ?? "sin teléfono"} ·{" "}
          {paciente.email ?? "sin email"} · {paciente.obra_social_nombre ?? "Sin obra social"}
          {paciente.obra_social_plan ? ` (${paciente.obra_social_plan})` : ""}
        </p>
        <p className="mt-1 text-sm font-medium">
          {paciente.consentimiento_datos
            ? `Consentimiento de datos: otorgado${
                paciente.consentimiento_datos_at
                  ? ` el ${fecha(paciente.consentimiento_datos_at)}`
                  : ""
              }`
            : "Consentimiento de datos: no otorgado"}
        </p>
        {!paciente.consentimiento_datos && (
          <Aviso tipo="alerta" className="mt-2">
            {TEXTO_SIN_CONSENTIMIENTO}
          </Aviso>
        )}
      </section>
      <nav aria-label="Secciones del paciente" className="mt-4 border-b border-border">
        <ul className="flex flex-wrap">
          {TABS.map(([ruta, titulo]) => (
            <li key={ruta}>
              <NavLink className={claseTab} to={`/pacientes/${pacienteId}/${ruta}`}>
                {titulo}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="mt-4">
        <Outlet context={contexto} />
      </div>
    </section>
  );
}
