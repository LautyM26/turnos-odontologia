/** Une clases condicionales (sin dependencias: alcanza para nuestros componentes). */
export function cx(...clases: (string | false | null | undefined)[]): string {
  return clases.filter(Boolean).join(" ");
}
