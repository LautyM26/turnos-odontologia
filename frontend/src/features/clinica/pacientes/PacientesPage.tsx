import { useState } from "react";
import { Form, Link, type LoaderFunctionArgs, useLoaderData, useRevalidator } from "react-router";

import { requireSession } from "@/features/auth/session";
import { apiFetch } from "@/shared/api/client";
import { cargarSeguro, type Resultado } from "@/shared/api/resultado";
import { EstadoSeccion } from "@/shared/ui/EstadoSeccion";

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
      <div>
        <p>No hay pacientes que coincidan con «{buscar.trim()}»</p>
        <Link className="underline" to="/pacientes">
          Limpiar búsqueda
        </Link>
      </div>
    );
  }
  return (
    <div>
      <ul className="divide-y divide-border rounded-md border border-border">
        <li
          aria-hidden="true"
          className="hidden grid-cols-4 gap-2 bg-surface px-3 py-2 text-sm font-medium md:grid"
        >
          <span>Paciente</span>
          <span>DNI</span>
          <span>Teléfono</span>
          <span>Obra social</span>
        </li>
        {items.map((p) => (
          <li key={p.id} className="grid gap-1 px-3 py-3 md:grid-cols-4 md:gap-2">
            <Link className="font-medium underline" to={`/pacientes/${p.id}`}>
              {p.apellido}, {p.nombre}
            </Link>
            <span>
              <span className="text-muted md:hidden">DNI </span>
              {p.dni}
            </span>
            <span>{p.telefono ?? "—"}</span>
            <span>{p.obra_social_nombre ?? "—"}</span>
          </li>
        ))}
      </ul>
      {falla && (
        <p role="alert" className="mt-2 text-danger">
          {falla}
        </p>
      )}
      {cursor !== null && (
        <button
          type="button"
          className="mt-3 rounded border border-border px-3 py-1"
          disabled={cargando}
          onClick={cargarMas}
        >
          Cargar más
        </button>
      )}
    </div>
  );
}

export function Component() {
  const { buscar, corta, resultado } = useLoaderData() as Datos;
  const revalidator = useRevalidator();
  return (
    <section>
      <title>Pacientes · Turnos Odontología</title>
      <h1 className="text-2xl font-semibold">Pacientes</h1>
      <Form method="get" className="mt-4 flex flex-wrap items-end gap-2" role="search">
        <div>
          <label className="block text-sm font-medium" htmlFor="buscar">
            Buscar paciente
          </label>
          <input
            id="buscar"
            name="buscar"
            type="search"
            defaultValue={buscar}
            aria-describedby="buscar-ayuda"
            className="mt-1 w-72 max-w-full rounded-md border border-border px-3 py-2"
          />
        </div>
        <button type="submit" className="rounded bg-primary px-4 py-2 text-primary-foreground">
          Buscar
        </button>
      </Form>
      <p id="buscar-ayuda" className="mt-1 text-sm text-muted">
        Nombre, DNI o teléfono
      </p>
      <div className="mt-4">
        {corta ? (
          <p role="status">Escribí al menos 3 caracteres para buscar.</p>
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
