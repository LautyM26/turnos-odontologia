import { cx } from "./cx";

/** Placeholder con la forma del contenido final (sin spinners de pantalla completa). */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cx(
        "rounded-md bg-[linear-gradient(90deg,var(--surface-2)_25%,var(--border)_50%,var(--surface-2)_75%)]",
        "bg-[length:200%_100%] motion-safe:animate-[brillo_1.6s_linear_infinite]",
        className,
      )}
    />
  );
}
