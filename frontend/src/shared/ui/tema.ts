/**
 * Tema claro / oscuro (C-20 D1). "sistema" = sigue `prefers-color-scheme` (sin atributo).
 * La elección es solo una preferencia de UI en localStorage: ningún dato personal ni secreto.
 * El script inline de index.html aplica el mismo atributo antes del primer pintado.
 */

import { useCallback, useState } from "react";

export type Tema = "claro" | "oscuro" | "sistema";

const CLAVE = "tema";

export function leerTema(): Tema {
  try {
    const valor = window.localStorage.getItem(CLAVE);
    return valor === "claro" || valor === "oscuro" ? valor : "sistema";
  } catch {
    return "sistema";
  }
}

export function aplicarTema(tema: Tema): void {
  const raiz = document.documentElement;
  if (tema === "sistema") {
    raiz.removeAttribute("data-theme");
  } else {
    raiz.setAttribute("data-theme", tema === "oscuro" ? "dark" : "light");
  }
  try {
    if (tema === "sistema") {
      window.localStorage.removeItem(CLAVE);
    } else {
      window.localStorage.setItem(CLAVE, tema);
    }
  } catch {
    // storage no disponible (modo privado estricto): el tema vale solo para esta vista
  }
}

export function useTema(): [Tema, (tema: Tema) => void] {
  const [tema, setTema] = useState<Tema>(leerTema);
  const cambiar = useCallback((nuevo: Tema) => {
    aplicarTema(nuevo);
    setTema(nuevo);
  }, []);
  return [tema, cambiar];
}
