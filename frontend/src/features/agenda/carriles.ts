/**
 * Carriles para turnos superpuestos en una misma columna (sobreturnos, C-07 D6): barrido por
 * inicio; cada grupo de solapamiento reparte el ancho en `total` carriles.
 */

export interface Intervalo {
  id: number;
  inicio: number;
  fin: number;
}

export interface Ubicacion {
  carril: number;
  total: number;
}

export function asignarCarriles(items: Intervalo[]): Map<number, Ubicacion> {
  const orden = [...items].sort((a, b) => a.inicio - b.inicio || a.fin - b.fin || a.id - b.id);
  const salida = new Map<number, Ubicacion>();
  let grupo: { id: number; carril: number }[] = [];
  let finGrupo = -1;
  let carrilesFin: number[] = [];

  const cerrarGrupo = (): void => {
    const total = Math.max(1, carrilesFin.length);
    for (const g of grupo) {
      salida.set(g.id, { carril: g.carril, total });
    }
    grupo = [];
    carrilesFin = [];
  };

  for (const it of orden) {
    if (it.inicio >= finGrupo && grupo.length > 0) {
      cerrarGrupo();
    }
    let carril = carrilesFin.findIndex((fin) => fin <= it.inicio);
    if (carril === -1) {
      carril = carrilesFin.length;
      carrilesFin.push(it.fin);
    } else {
      carrilesFin[carril] = it.fin;
    }
    grupo.push({ id: it.id, carril });
    finGrupo = Math.max(finGrupo, it.fin);
  }
  if (grupo.length > 0) {
    cerrarGrupo();
  }
  return salida;
}
