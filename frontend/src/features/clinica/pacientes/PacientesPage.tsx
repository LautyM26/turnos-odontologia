import { Search } from "lucide-react";
import { useState } from "react";
import { Form, Link, type LoaderFunctionArgs, useLoaderData, useRevalidator } from "react-router";
import { requireSession } from "@/features/auth/session";
import { apiFetch } from "@/shared/api/client";
import { cargarSeguro, type Resultado } from "@/shared/api/resultado";

import { Avatar } from "@/shared/ui/Avatar";
import { Button } from "@/shared/ui/Button";
import { EstadoSeccion } from "@/shared/ui/EstadoSeccion";
import { PageHeader } from "@/shared/ui/PageHeader";

import type { Paciente, Pagina } from "../tipos";
import { interpretarBusqueda } from "./busqueda";

const LIMITE = 50;

interface Datos {
  buscar: string;
  corta: boolean;
  resultado: Resultado<Pagina<Paciente>>;
}

function urlListado(buscar: string, afterId?: number): string | null {
  const b = interpretarBusqueda(buscar);
  if (b.tipo === "corta") {
    return null;
  }
  const params = new URLSearchParams({ limit: String(LIMITE) });
  if (b.tipo !== "todos") {
    params.set(b.param, b.valor);
  }
  if (afterId !== undefined) {
    params.set("after_id", String(afterId));
  }
  return `/api/pacientes?${params}`;
}

export async function loader({ request }: LoaderFunctionArgs): Promise<Datos> {
  await requireSession(new URL(request.url));
  const buscar = new URL(request.url).searchParams.get("buscar") ?? "";
  const url = urlListado(buscar);
  if (url === null) {
    return {
      buscar,
      corta: true,
      resultado: { tipo: "ok", datos: { items: [], next_cursor: null } },
    };
  }
  return { buscar, corta: false, resultado: await cargarSeguro(apiFetch<Pagina<Paciente>>(url)) };
}

function Lista({ buscar, inicial }: { buscar: string; inicial: Pagina<Paciente> }) {
  const [items, setItems] = useState(inicial.items);
  const [cursor, setCursor] = useState(inicial.next_cursor);
  const [cargando, setCargando] = useState(false);
  const [falla, setFalla] = useState<string | null>(null);

  async function cargarMas(): Promise<void> {
    const url = urlListado(buscar, cursor ?? undefined);
    if (url === null) {
      return;
    }
    setCargando(true);
    setFalla(null);
    try {
      const pagina = await apiFetch<Pagina<Paciente>>(url);
      const ya = new Set(items.map((p) => p.id));
      setItems([...items, ...pagina.items.filter((p) => !ya.has(p.id))]);
      setCursor(pagina.next_cursor);
    } catch {
      setFalla("No pudimos cargar más pacientes");
    } finally {
      setCargando(false);
    }
  }

  if (items.length === 0) {
    return buscar.trim() === "" ? (
      <EstadoSeccion estado={{ tipo: "vacio", mensaje: "Todavía no hay pacientes cargados." }} />
    ) : (
      <div className="rounded-[14px] border border-border bg-surface px-6 py-10 text-center">
        <p className="font-medium">No hay pacientes que coincidan con «{buscar.trim()}»</p>
        <Link
          className="mt-2 inline-block text-sm font-medium text-primary hover:underline"
          to="/pacientes"
        >
          Limpiar búsqueda
        </Link>
      </div>
    );
  }
  return (
    <div>
      <ul className="overflow-hidden rounded-[14px] border border-border bg-surface shadow-xs">
        <li
          aria-hidden="true"
          className="hidden grid-cols-[2fr_1fr_1.2fr_1.4fr] gap-4 border-b border-border bg-surface-2 px-5 py-2.5 text-xs font-medium uppercase tracking-wide text-muted md:grid"
        >
          <span>Paciente</span>
          <span>DNI</span>
          <span>Teléfono</span>
          <span>Obra social</span>
        </li>
        {items.map((p, i) => (
          <li
            key={p.id}
            style={{ animationDelay: `${Math.min(i, 8) * 25}ms` }}
            className="grid items-center gap-1 border-b border-border px-5 py-3.5 transition-colors last:border-b-0 hover:bg-surface-2 motion-safe:animate-[aparecer_220ms_var(--ease-suave)_both] md:grid-cols-[2fr_1fr_1.2fr_1.4fr] md:gap-4"
          >
            <span className="flex min-w-0 items-center gap-3">
              <Avatar nombre={p.nombre} apellido={p.apellido} tamano="sm" />
              <Link
                className="truncate font-medium text-foreground hover:text-primary hover:underline"
                to={`/pacientes/${p.id}`}
              >
                {p.apellido}, {p.nombre}
              </Link>
            </span>
            <span className="text-sm tabular-nums">
              <span className="text-muted md:hidden">DNI </span>
              {p.dni}
            </span>
            <span className="text-sm tabular-nums text-muted">{p.telefono ?? "Sin teléfono"}</span>
            <span className="truncate text-sm text-muted">
              {p.obra_social_nombre ?? "Sin obra social"}
            </span>
          </li>
        ))}
      </ul>
      {falla && (
        <p role="alert" className="mt-2 text-danger">
          {falla}
        </p>
      )}
      {cursor !== null && (
        <Button variante="secondary" className="mt-4" cargando={cargando} onClick={cargarMas}>
          Cargar más
        </Button>
      )}
    </div>
  );
}

export function Component() {
  const { buscar, corta, resultado } = useLoaderData() as Datos;
  const revalidator = useRevalidator();
  return (
    <section className="space-y-6">
      <title>Pacientes · Turnos Odontología</title>
      <PageHeader
        titulo="Pacientes"
        descripcion="Fichas, historia clínica y datos de contacto de la clínica."
      />
      <div className="rounded-[14px] border border-border bg-surface p-4 shadow-xs">
        <Form method="get" className="flex flex-wrap items-end gap-3" role="search">
          <div className="min-w-0 flex-1 basis-72">
            <label className="block text-[13px] font-medium" htmlFor="buscar">
              Buscar paciente
            </label>
            <div className="relative mt-1.5">
              <Search
                aria-hidden
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
              />
              <input
                id="buscar"
                name="buscar"
                type="search"
                defaultValue={buscar}
                aria-describedby="buscar-ayuda"
                className="h-10 w-full rounded-lg border border-border-control bg-surface pl-9 pr-3 text-sm shadow-xs focus:border-primary focus:outline-none focus:ring-3 focus:ring-focus"
              />
            </div>
          </div>
          <Button type="submit">Buscar</Button>
        </Form>
        <p id="buscar-ayuda" className="mt-2 text-xs text-muted">
          Nombre, DNI o teléfono
        </p>
      </div>
      <div>
        {corta ? (
          <p role="status" className="text-sm text-muted">
            Escribí al menos 3 caracteres para buscar.
          </p>
        ) : resultado.tipo === "ok" ? (
          <Lista key={buscar} buscar={buscar} inicial={resultado.datos} />
        ) : (
          <EstadoSeccion
            estado={{
              tipo: "error",
              mensaje:
                resultado.tipo === "error" ? resultado.mensaje : "No pudimos cargar los pacientes",
              onReintentar: () => void revalidator.revalidate(),
            }}
          />
        )}
      </div>
    </section>
  );
}
