import { NavLink, Outlet, useNavigate } from "react-router";

import { rolesLegibles } from "./roles";
import { cerrarSesion, useSesion } from "./session";

const enlace = "rounded px-2 py-1 aria-[current=page]:font-semibold aria-[current=page]:underline";

export function AppLayout() {
  const me = useSesion();
  const navigate = useNavigate();

  async function salir(): Promise<void> {
    await cerrarSesion();
    await navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <a
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:bg-background focus:p-2"
        href="#contenido"
      >
        Saltar al contenido
      </a>
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="font-semibold">Turnos Odontología</span>
          <nav aria-label="Principal" className="flex gap-2">
            <NavLink className={enlace} to="/pacientes">
              Pacientes
            </NavLink>
          </nav>
          {me && (
            <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <span>
                <span>{me.email}</span> · <span className="text-muted">{rolesLegibles(me)}</span>
              </span>
              <button
                className="rounded border border-border px-3 py-1"
                type="button"
                onClick={salir}
              >
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </header>
      <main id="contenido" className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
