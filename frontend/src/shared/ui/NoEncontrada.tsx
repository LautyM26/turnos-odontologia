import { Link } from "react-router";

export function Component() {
  return (
    <section>
      <h1 className="text-xl font-semibold">Página no encontrada</h1>
      <p className="mt-2">
        <Link className="underline" to="/pacientes">
          Volver a pacientes
        </Link>
      </p>
    </section>
  );
}
