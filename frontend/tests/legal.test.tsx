/** Páginas legales públicas (C-18, RN-CU-01/05): textos base, avisos y marcadores sin datos reales. */
import { readFileSync } from "node:fs";
import { renderToString } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { AVISO_LEGAL, CUMPLIMIENTO, PRIVACIDAD } from "@/features/legal/textos";
import { CumplimientoPage } from "@/pages/CumplimientoPage";
import { PrivacidadPage } from "@/pages/PrivacidadPage";
import { rutas } from "@/router";

function renderEn(ruta: string): string {
  return renderToString(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/cumplimiento" element={<CumplimientoPage />} />
        <Route path="/privacidad" element={<PrivacidadPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const sinEtiquetas = (html: string) =>
  html
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ");

describe("/cumplimiento", () => {
  const texto = sinEtiquetas(renderEn("/cumplimiento"));

  it("muestra el título, la versión y las cuatro leyes con su explicación", () => {
    expect(texto).toContain("Cumplimiento y privacidad");
    expect(texto).toContain(`Versión ${CUMPLIMIENTO.version}`);
    for (const ley of ["26.529", "25.326", "25.506", "27.706"]) {
      expect(texto).toContain(ley);
    }
    expect(CUMPLIMIENTO.secciones.length).toBeGreaterThanOrEqual(4);
    for (const seccion of CUMPLIMIENTO.secciones) {
      expect(texto).toContain(seccion.titulo);
    }
  });

  it("muestra el aviso de validación legal y enlaza a /privacidad", () => {
    expect(AVISO_LEGAL).toBe("Texto base a validar con asesoría legal");
    expect(texto).toContain(AVISO_LEGAL);
    expect(renderEn("/cumplimiento")).toContain('href="/privacidad"');
  });

  it("declara cómo se cumple: HC append-only, consentimientos, receta ReNaPDiS y exportación", () => {
    for (const clave of ["append-only", "constancia", "renapdis", "exportación"]) {
      expect(texto.toLowerCase()).toContain(clave);
    }
  });
});

describe("/privacidad", () => {
  it.each(["/privacidad", "/privacidad/"])(
    "%s muestra la ubicación de los datos y el aviso",
    (ruta) => {
      const texto = sinEtiquetas(renderEn(ruta));
      expect(texto).toContain("Dónde se guardan tus datos");
      expect(texto).toContain(AVISO_LEGAL);
      expect(texto).toContain(`Versión ${PRIVACIDAD.version}`);
      expect(texto).toContain("[A completar");
    },
  );

  it("cubre datos sensibles, derechos ante la AAIP y exportación sin retención", () => {
    const texto = sinEtiquetas(renderEn("/privacidad"));
    for (const clave of ["sensibles", "AAIP", "acceso", "rectificación", "supresión", "exportar"]) {
      expect(texto).toContain(clave);
    }
  });

  it("el responsable, el CUIT y el contacto son marcadores, no datos", () => {
    const texto = sinEtiquetas(renderEn("/privacidad"));
    expect(texto).toMatch(/\[A completar[^\]]*responsable/i);
    expect(texto).toMatch(/\[A completar[^\]]*CUIT/i);
    expect(texto).toMatch(/\[A completar[^\]]*contacto/i);
  });
});

describe("textos legales sin datos reales (regla dura 14)", () => {
  const todo = JSON.stringify([CUMPLIMIENTO, PRIVACIDAD]);

  it("no contienen números de 7 u 8 dígitos ni teléfonos", () => {
    expect(todo).not.toMatch(/\d{7,}/);
    expect(todo).not.toMatch(/\+\d/);
    expect(todo).not.toMatch(/\b\d{2}-\d{8}-\d\b/);
  });

  it("tienen versión y fecha visibles", () => {
    for (const doc of [CUMPLIMIENTO, PRIVACIDAD]) {
      expect(doc.version).toMatch(/^\d+\.\d+$/);
      expect(doc.fecha).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    }
  });
});

describe("páginas legales estáticas", () => {
  it("no hacen llamadas a la API (se ven completas sin backend)", () => {
    for (const archivo of [
      "src/pages/CumplimientoPage.tsx",
      "src/pages/PrivacidadPage.tsx",
      "src/features/legal/textos.ts",
    ]) {
      const fuente = readFileSync(archivo, "utf8");
      expect(fuente).not.toMatch(/fetch\(/);
      expect(fuente).not.toMatch(/shared\/api/);
    }
  });

  it("/privacidad es una ruta pública (fuera del layout con sesión)", () => {
    const publicas = rutas.filter((r) => r.loader === undefined && r.path === undefined);
    const hijas = publicas.flatMap((r) => r.children ?? []);
    expect(hijas.map((r) => r.path)).toEqual(
      expect.arrayContaining(["/cumplimiento", "/privacidad"]),
    );
  });
});
