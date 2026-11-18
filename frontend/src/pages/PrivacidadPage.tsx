import { Link } from "react-router";
import { PaginaLegal } from "@/features/legal/PaginaLegal";
import { PRIVACIDAD } from "@/features/legal/textos";

/** Política de privacidad pública (RN-CU-01): ubicación declarada, sin datos reales. */
export function PrivacidadPage() {
  return (
    <PaginaLegal
      titulo="Política de privacidad"
      texto={PRIVACIDAD}
      pie={
        <>
          Mirá cómo cumplimos la normativa en{" "}
          <Link className="font-medium text-primary underline" to="/cumplimiento">
            cumplimiento
          </Link>
          .
        </>
      }
    />
  );
}
