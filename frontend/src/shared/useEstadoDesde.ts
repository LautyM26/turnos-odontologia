import { useState } from "react";

/**
 * Estado local inicializado desde datos del loader que se resetea si el loader entrega
 * datos nuevos (p. ej. tras "Reintentar"). Evita useEffect para sincronizar.
 */
export function useEstadoDesde<T>(origen: T): [T, (valor: T) => void] {
  const [estado, setEstado] = useState({ origen, valor: origen });
  if (estado.origen !== origen) {
    setEstado({ origen, valor: origen });
    return [origen, (valor) => setEstado({ origen, valor })];
  }
  return [estado.valor, (valor) => setEstado({ origen, valor })];
}
