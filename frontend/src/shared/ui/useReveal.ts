/**
 * Reveal al entrar en pantalla (C-20 D2): agrega `data-visible` una sola vez a cada elemento
 * con `data-reveal` dentro del contenedor. Sin IntersectionObserver (o con movimiento
 * reducido, vía CSS) el contenido queda visible directamente.
 */

import { useEffect, useRef } from "react";

export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const raiz = ref.current;
    if (!raiz) {
      return;
    }
    const elementos = Array.from(raiz.querySelectorAll<HTMLElement>("[data-reveal]"));
    if (typeof IntersectionObserver === "undefined") {
      for (const el of elementos) {
        el.setAttribute("data-visible", "");
      }
      return;
    }
    const observador = new IntersectionObserver(
      (entradas) => {
        for (const e of entradas) {
          if (e.isIntersecting) {
            e.target.setAttribute("data-visible", "");
            observador.unobserve(e.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 },
    );
    for (const el of elementos) {
      observador.observe(el);
    }
    return () => observador.disconnect();
  }, []);
  return ref;
}
