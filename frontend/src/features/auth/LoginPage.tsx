import { type FormEvent, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

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
    <main className="mx-auto max-w-sm px-4 py-12">
      <title>Ingresar · Turnos Odontología</title>
      <h1 className="text-2xl font-semibold">Ingresar</h1>
      <p className="mt-1 text-muted">Turnos Odontología · acceso del personal</p>
      {params.get("expirada") === "1" && (
        <Aviso tipo="info" className="mt-4">
          Tu sesión expiró, volvé a ingresar
        </Aviso>
      )}
      <form
        className="mt-6 space-y-4"
        onSubmit={enviar}
        aria-describedby={error ? "login-error" : undefined}
      >
        <div>
          <label className="block text-sm font-medium" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            className="mt-1 w-full rounded-md border border-border px-3 py-2"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-sm font-medium" htmlFor="password">
            Contraseña
          </label>
          <input
            id="password"
            className="mt-1 w-full rounded-md border border-border px-3 py-2"
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
          className="w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground disabled:opacity-60"
          type="submit"
          disabled={enviando}
        >
          {enviando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </main>
  );
}
