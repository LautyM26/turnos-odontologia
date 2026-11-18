import { Link } from "react-router";
import { PaginaLegal } from "@/features/legal/PaginaLegal";
import { CUMPLIMIENTO } from "@/features/legal/textos";

/** Página pública de cumplimiento (RN-CU-05): textos estáticos, no depende de la API. */
export function CumplimientoPage() {
  return (
    <PaginaLegal
      titulo="Cumplimiento y privacidad"
      texto={CUMPLIMIENTO}
      pie={
        <>
          Leé también la{" "}
          <Link className="font-medium text-primary underline" to="/privacidad">
            política de privacidad
          </Link>
          .
        </>
      }
    />
  );
}
