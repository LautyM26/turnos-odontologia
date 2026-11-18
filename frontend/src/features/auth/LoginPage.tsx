import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { ApiError } from "@/shared/api/client";
import { Aviso } from "@/shared/ui/Aviso";

import { iniciarSesion, rutaSegura } from "./session";

function mensajeDeLogin(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) {
    return "Email o contraseña incorrectos";
  }
  if (error instanceof ApiError && error.status === 429) {
    return "Demasiados intentos. Esperá un minuto antes de volver a intentar.";
  }
  return "No pudimos ingresar. Revisá tu conexión e intentá de nuevo.";
}

export function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await iniciarSesion(email.trim(), password);
      await navigate(rutaSegura(params.get("redirectTo")), { replace: true });
    } catch (e) {
      setError(mensajeDeLogin(e));
      setPassword("");
      setEnviando(false);
    }
  }

  return (
    <main className="grid min-h-dvh bg-background text-foreground lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <title>Ingresar · Turnos Odontología</title>
      <div className="flex flex-col px-6 py-8 sm:px-10">
        <Link
          to="/"
          className="flex w-fit items-center gap-2.5 rounded-lg"
          aria-label="Turnos Odontología, inicio"
        >
          <span
            aria-hidden
            className="grid size-8 place-items-center rounded-[10px] bg-primary font-heading text-sm font-bold text-primary-foreground shadow-xs"
          >
            T
          </span>
          <span aria-hidden className="font-heading text-[15px] font-semibold">
            Turnos Odontología
          </span>
        </Link>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10 motion-safe:animate-[fundido_260ms_var(--ease-suave)]">
          <h1 className="text-3xl font-semibold">Ingresar</h1>
          <p className="mt-1.5 text-muted">Turnos Odontología · acceso del personal</p>
          {params.get("expirada") === "1" && (
            <Aviso tipo="info" className="mt-5">
              Tu sesión expiró, volvé a ingresar
            </Aviso>
          )}
          <form
            className="mt-8 space-y-5"
            onSubmit={enviar}
            aria-describedby={error ? "login-error" : undefined}
          >
            <div className="flex flex-col gap-1.5">
              <label className="text-[13px] font-medium" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                className="h-11 w-full rounded-lg border border-border-control bg-surface px-3 text-[15px] shadow-xs transition-[border-color,box-shadow] focus:border-primary focus:outline-none focus:ring-3 focus:ring-focus"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-[13px] font-medium" htmlFor="password">
                Contraseña
              </label>
              <input
                id="password"
                className="h-11 w-full rounded-lg border border-border-control bg-surface px-3 text-[15px] shadow-xs transition-[border-color,box-shadow] focus:border-primary focus:outline-none focus:ring-3 focus:ring-focus"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && (
              <Aviso tipo="error" id="login-error">
                {error}
              </Aviso>
            )}
            <button
              className="h-11 w-full cursor-pointer rounded-[10px] bg-primary px-4 font-medium text-primary-foreground shadow-xs transition-[background-color,transform] duration-150 hover:bg-primary-hover active:translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
              type="submit"
              disabled={enviando}
            >
              {enviando ? "Ingresando…" : "Ingresar"}
            </button>
          </form>
          <p className="mt-8 text-sm text-muted">
            ¿Sos paciente?{" "}
            <Link
              className="font-medium text-primary hover:underline"
              to="/reservar/clinica-piloto"
            >
              Reservá tu turno online
            </Link>
          </p>
        </div>
      </div>
      <aside
        aria-hidden
        className="relative hidden overflow-hidden border-l border-border bg-primary-soft lg:block"
      >
        <div className="absolute inset-0 bg-[radial-gradient(70%_60%_at_80%_10%,color-mix(in_srgb,var(--primary)_18%,transparent),transparent_70%)]" />
        <div className="relative flex h-full flex-col justify-center px-12">
          <p className="max-w-[26ch] font-heading text-2xl font-semibold leading-snug">
            La agenda de toda la clínica, por sillón y sin superposiciones.
          </p>
          <div className="mt-8 translate-x-6 overflow-hidden rounded-[18px] border border-border bg-surface shadow-lg">
            <img
              src="/landing/agenda.png"
              alt=""
              width={1440}
              height={900}
              className="block h-auto w-full"
            />
          </div>
        </div>
      </aside>
    </main>
  );
}
