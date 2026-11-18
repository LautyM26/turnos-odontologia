import { cx } from "./cx";

/** Iniciales sobre primary-soft (C-20 D3). Decorativo: el nombre siempre está en texto al lado. */
export function Avatar({
  nombre,
  apellido,
  tamano = "md",
  className,
}: {
  nombre: string;
  apellido?: string;
  tamano?: "sm" | "md" | "lg";
  className?: string;
}) {
  const iniciales = `${(apellido ?? "").charAt(0)}${nombre.charAt(0)}`.toUpperCase() || "?";
  return (
    <span
      aria-hidden
      className={cx(
        "inline-grid shrink-0 place-items-center rounded-full bg-primary-soft font-heading font-semibold text-primary-hover",
        tamano === "sm" && "size-8 text-xs",
        tamano === "md" && "size-10 text-sm",
        tamano === "lg" && "size-14 text-lg",
        className,
      )}
    >
      {iniciales}
    </span>
  );
}
