# Design System Master — Turnos Odontología

> **Lógica:** al construir una página, mirar primero `design-system/turnos-odontologia/pages/<pagina>.md`; si existe, sus reglas **pisan** este archivo. Si no, aplicar este archivo.

**Proyecto:** Turnos Odontología (SaaS de gestión de clínica odontológica, AR)
**Generado:** 2026-11-17 con `ui-ux-pro-max` 2.13.0 (`--design-system "medical clinic healthcare app minimal"`, dials variance 6 / motion 5 / density 6), y **curado a mano** (ver "Procedencia").
**Vibe acordado con el usuario:** clínico moderno premium (referencias: Linear, Cal.com, Doctolib). Limpio, con aire, un acento con carácter y microinteracciones suaves. Pensado también para el video de demo.

---

## Procedencia (qué viene de la base de datos y qué se ajustó)

| Decisión | Origen | Ajuste |
|---|---|---|
| Paleta teal + verde salud | `colors.csv` · "Medical Clinic" / "Healthcare App" | Los tonos de acción se oscurecen para que el texto blanco llegue a AA (el `#0891B2` original da 3,68:1). Los bordes cian saturados pasan a slate neutro |
| Figtree (títulos) + Noto Sans (cuerpo) | `typography.csv` · "Medical Clean" | — |
| Estilo **Minimalism & Swiss** | `styles.csv` · "healthcare clinical SaaS minimal" | Reemplaza a *Neumorphism*, que propuso el generador: la base lo marca con `accessibility risk: high` (relieves de bajo contraste). No corresponde para un sistema de salud |
| Patrón de página | El generador propuso "Hero + Testimonials" (landing) | Solo aplica a la home pública (`/`). El resto es **app**: shell con sidebar y contenido |
| Motion | Generador: stagger con `back.out` | Sin overshoot en UI de datos (agenda, tablas): la propia base lo desaconseja. `ease-out` corto y spring suave solo en paneles |

Contrastes medidos (WCAG 2.1): blanco sobre `#0E7490` = 5,36 · blanco sobre `#0F766E` = 5,47 · `#475569` sobre blanco = 7,58 · `#64748B` sobre `#F8FAFC` = 4,55 · `#0F172A` sobre `#F8FAFB` = 17,05.

---

## Color (tokens semánticos)

Fondo casi blanco con matiz frío, superficies blancas y un solo color de marca (teal). El acento cálido (coral) se reserva para "ahora", novedades y la reserva pública; nunca para errores.

| Rol | Hex | Token CSS | Uso |
|---|---|---|---|
| Background | `#F7FAFA` | `--background` | Fondo de la app |
| Surface | `#FFFFFF` | `--surface` | Cards, paneles, tablas |
| Surface-2 | `#F1F5F6` | `--surface-2` | Zonas rehundidas, hover de filas, header de tabla |
| Foreground | `#0F172A` | `--foreground` | Texto principal |
| Muted | `#5B6B7F` | `--muted` | Texto secundario (≥ 4,5:1 sobre blanco) |
| Border | `#E3E8EE` | `--border` | Divisores, bordes de inputs |
| Border-strong | `#CBD5E1` | `--border-strong` | Inputs en hover |
| **Primary** | `#0E7490` | `--primary` | Botón principal, links, foco, selección |
| Primary-hover | `#155E75` | `--primary-hover` | Hover y active |
| Primary-soft | `#E6F6F9` | `--primary-soft` | Fondos de selección, chips activos |
| On-primary | `#FFFFFF` | `--primary-foreground` | Texto sobre primary |
| Accent (coral) | `#E8613C` | `--accent` | Indicador "ahora", destacados, CTA de la reserva pública |
| Accent-soft | `#FDEEE8` | `--accent-soft` | — |
| Success | `#15803D` / `#EAF7EE` | `--success` / `--success-soft` | Asistido, guardado |
| Warning | `#A16207` / `#FEF6E1` | `--warning` / `--warning-soft` | Sobreturno, avisos |
| Danger | `#C6282D` / `#FDECEC` | `--danger` / `--danger-soft` | Errores, cancelar |
| Focus ring | `#0E7490` al 35 % | `--focus` | Anillo de foco de 3 px |

**Estados del turno** (badges con punto de color + texto; nunca solo color):

| Estado | Color |
|---|---|
| reservado | slate (neutro) |
| confirmado | primary |
| asistido | success |
| ausente | warning |
| cancelado | danger (tachado suave) |
| sobreturno (marca) | borde punteado warning + etiqueta "Sobreturno" |

Convención clínica del odontograma (no se cambia): rojo = a realizar, azul = existente.

### Modo oscuro (C-20)

Tema por preferencia del sistema (`prefers-color-scheme`) o elegido con el botón de tema (Claro / Oscuro / Sistema), guardado en `localStorage["tema"]` (solo la preferencia, nunca credenciales). El atributo `data-theme` va en `<html>` y un script inline en `index.html` lo aplica antes de pintar (sin parpadeo). Mismos tokens, otros valores:

| Rol | Oscuro |
|---|---|
| Background / Surface / Surface-2 | `#0B1215` / `#111A1E` / `#162127` |
| Foreground / Muted | `#E6EDF0` / `#93A3AD` |
| Border / Border-control | `#24323A` / `#5F7480` |
| Primary / On-primary | `#22A3C4` / `#0B1215` (texto oscuro sobre teal claro) |
| Accent / Danger / Success / Warning | `#FF8A65` / `#F87171` / `#4ADE80` / `#FBBF24` |

- `--border-control` (claro `#808FA0`) es el borde de inputs y selects: ≥ 3:1 sobre la superficie en ambos temas (WCAG 1.4.11).
- La grilla del odontograma se muestra siempre sobre "papel" blanco, también en oscuro, con los mismos rojo y azul.
- Contraste medido (C-20 `verify.md`): todos los pares de texto ≥ 4,5:1 y los bordes de control ≥ 3:1, en claro y oscuro.

## Tipografía

- **Títulos:** Figtree 600/700, tracking −0,01 a −0,02 em en tamaños grandes.
- **Cuerpo y UI:** Noto Sans 400/500, 15–16 px base, line-height 1,5.
- **Números** (horas, DNI, montos): `font-variant-numeric: tabular-nums`.
- **Escala:** 12 (meta) · 13 (labels) · 15 (cuerpo app) · 16 (formularios públicos) · 18 · 22 · 28 · 36 (hero público).
- Carga: Google Fonts con `display=swap` y `preconnect` en `index.html`.

## Espaciado, radios y elevación

- **Escala de 4 px:** 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64.
- **Radios:** 6 (inputs, badges) · 10 (botones, cards chicas) · 14 (cards, paneles) · 20 (modales y drawers).
- **Sombras** (suaves, con tinte frío, nunca negras puras):
  - `--shadow-xs: 0 1px 2px rgb(15 23 42 / .04)`
  - `--shadow-sm: 0 1px 3px rgb(15 23 42 / .06), 0 1px 2px rgb(15 23 42 / .04)`
  - `--shadow-md: 0 8px 24px -6px rgb(15 23 42 / .10)`
  - `--shadow-lg: 0 24px 48px -12px rgb(15 23 42 / .18)`
- Bordes de 1 px en lugar de sombras fuertes. Profundidad sutil: estilo Swiss con elevación mínima.

## Layout de app

- **Shell:** sidebar fija de 248 px en desktop, colapsable a íconos en < 1024 px y a drawer en móvil.
  - Contenido: logotipo, navegación (Agenda, Pacientes, …), clínica y usuario abajo.
  - Topbar con título de sección, acciones y búsqueda.
- **Contenido:** `max-width` 1280 px en listados; la agenda usa el ancho completo.
- **Responsive:** 375 · 768 · 1024 · 1440. Sin scroll horizontal, salvo dentro de la grilla de la agenda.

## Componentes base (`frontend/src/shared/ui/`)

| Componente | Variantes y notas |
|---|---|
| Button | primary · secondary (borde) · ghost · danger; tamaños sm/md; `loading` con spinner; ícono opcional |
| Input / Select / Textarea / Field | label visible arriba, ayuda y error debajo (`aria-describedby`), alto 40 px (44 px en público) |
| Card / Panel | surface + borde + radio 14; header con título y acciones |
| Badge / EstadoTurno | punto de color + texto; `tabular-nums` en contadores |
| Aviso | se mantiene la API actual (`tipo`, `role` alert/status); nuevo look con ícono |
| DialogoConfirmacion | se mantiene la API (`<dialog>` nativo); radio 20, overlay con blur de 4 px |
| Drawer | panel lateral para el detalle o alta de turno (`<dialog>` o `aside` con foco atrapado) |
| Skeleton | carga de listas y agenda (sin spinners de pantalla completa) |
| EmptyState | ícono + título + texto + acción |
| Avatar | iniciales sobre primary-soft |

**Íconos:** Lucide (`lucide-react`), trazo 1,75, 16/18/20 px. Nunca emojis. En íconos decorativos, `aria-hidden`.

## Motion

- **Duraciones:** 120 ms (hover y color) · 180 ms (entrada de elementos) · 240 ms (paneles y drawers). La salida es más rápida que la entrada.
- **Easing:** `cubic-bezier(.2,.8,.2,1)` (ease-out suave). Spring sin rebote visible solo en drawer y modal.
- **Dónde:** entrada escalonada corta en listas (≤ 6 elementos, 30 ms), drawer de turno, cambio de vista día/semana (fade y desplazamiento de 8 px), confirmación (check animado) y línea "ahora" en la agenda.
- **Dónde no:** tablas densas, odontograma (la precisión manda) y formularios mientras se escribe.
- Siempre se respeta `prefers-reduced-motion`: estado final inmediato (ya hay un reset global en `styles.css`).
- Se anima solo `transform` y `opacity`; nunca `width`, `height` ni `top`.

## Accesibilidad (innegociable, sistema de salud)

- Contraste 4,5:1 en texto y 3:1 en bordes de componentes; foco visible en todo.
- Labels visibles; errores junto al campo; `aria-live` en resultados de acciones.
- Objetivos táctiles ≥ 44 px en la parte pública y en móvil.
- La agenda es navegable con teclado, y los turnos son botones con nombre accesible ("Turno 10:00–10:30, Pérez, confirmado").

## Anti-patrones (no usar)

- Neumorfismo, glassmorphism sobre contenido de datos, neón, gradientes violeta/rosa "de IA".
- Emojis como íconos, `cursor` sin pointer en clickeables, hover que cambia el layout.
- Animaciones con overshoot en UI de datos, motion pesado.
- Grillas de 3 cards iguales "de template" en la home, Inter por defecto, nombres falsos tipo "Acme".
- Datos reales de pacientes en capturas (regla dura 14): solo sintéticos.

## Checklist previo a entregar una pantalla

- [ ] Sin emojis como íconos; todos de Lucide.
- [ ] `cursor-pointer` y estado hover (120–200 ms) en todo lo clickeable.
- [ ] Contraste ≥ 4,5:1 y foco visible.
- [ ] `prefers-reduced-motion` respetado.
- [ ] Probado a 375, 768, 1024 y 1440 px, sin scroll horizontal.
- [ ] Carga con skeleton y vacíos con EmptyState.
- [ ] Textos y roles que usan los tests intactos, o tests actualizados.
- [ ] tsc, build, vitest y biome (sobre LF) en verde.
