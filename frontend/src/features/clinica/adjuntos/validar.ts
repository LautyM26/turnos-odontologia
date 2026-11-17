/** Validación previa de adjuntos (espejo del servidor, que sigue siendo la autoridad). */

/** Default de ADJUNTO_MAX_BYTES del backend: 10 MiB. */
export const MAX_BYTES = 10 * 1024 * 1024;

const TIPOS = new Map([
  ["image/jpeg", [".jpg", ".jpeg"]],
  ["image/png", [".png"]],
  ["application/pdf", [".pdf"]],
]);

export const MENSAJE_TIPO = "Solo se aceptan fotos JPG/PNG o PDF";
export const MENSAJE_TAMANO = "El archivo supera el tamaño máximo permitido";

/** Devuelve el motivo del rechazo, o null si el archivo se puede enviar. */
export function validarArchivo(archivo: File): string | null {
  const extension = archivo.name.slice(archivo.name.lastIndexOf(".")).toLowerCase();
  if (!TIPOS.get(archivo.type)?.includes(extension)) {
    return MENSAJE_TIPO;
  }
  if (archivo.size === 0) {
    return "El archivo está vacío";
  }
  return archivo.size > MAX_BYTES ? MENSAJE_TAMANO : null;
}
