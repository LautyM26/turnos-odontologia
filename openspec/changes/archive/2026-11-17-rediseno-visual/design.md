# Design — rediseno-visual (C-20)

## Context

Motivación: ver `proposal.md`. Requisitos: `specs/product-landing`, `specs/visual-theme`, `specs/reschedule-web`, `specs/public-booking-web`. Dirección visual: `design-system/turnos-odontologia/MASTER.md`.

Estado observado:

- **C-07 dejó:**
  - tokens en `:root` (`styles.css`) y fuentes;
  - `shared/ui` (Button, Field/Input/Select/Textarea, Card, EstadoBadge, Drawer, Skeleton, EmptyState, Aviso, DialogoConfirmacion);
  - shell con sidebar (`AppLayout`), `PublicLayout` mínimo.
- **Pantallas por rediseñar:**
  - `LoginPage` (99 líneas);
  - pacientes: `PacientesPage`, `PacienteLayout`, `DatosPaciente`, `AnamnesisSeccion`, `FichaTab`;
  - `OdontogramaTab` / `OdontogramaGrafico` / `PanelPieza`;
  - `EvolucionesTab` / `FormularioEvolucion`;
  - `AdjuntosTab`;
  - reserva (`ReservarPage`, `ReservaPage`);
  - pages: `HomePage` (placeholder), `CumplimientoPage`, `PrivacidadPage`, `ComprobantePage`, `NoEncontrada`.
- **Tests** (vitest con `mockApi` + router en memoria): buscan por texto, rol y label. Hay un test que prohíbe clases Tailwind interpoladas (`bg-${…}`) y otro que verifica la convención de colores del odontograma (DC-3).
- **Backend C-17:**
  - `GET /api/public/reservas/{token}/opciones`: hasta 3 `{inicio, fin}`; 404 si el token es inválido, 422 si el turno no es reprogramable;
  - `POST /api/public/reservas/{token}/reprogramar {inicio}`: 200 con el comprobante; 409 con `{detail, alternativas[]}`; 429 por rate limit.

## Goals / Non-Goals

**Goals:** coherencia visual total, modo oscuro sin parpadeo, una landing que abra el video, `/reprogramar` funcional. Todo sin tocar comportamiento ni backend.

**Non-Goals:** lógica clínica o del odontograma, nuevos permisos, logo definitivo, librerías nuevas.

## Decisions

### D1 — Modo oscuro con tokens y `data-theme`

- **`styles.css`:**
  - el bloque `:root` (claro) se mantiene;
  - se agrega `:root[data-theme="dark"]` y el mismo bloque dentro de `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { … } }`.
- **Paleta oscura:**
  - fondo `#0b1215`, superficies `#111a1e` y `#162127`, texto `#e6edf0`, muted `#93a3ad` (≥ 4,5:1 sobre las superficies);
  - borde `#24323a`, primary `#22a3c4` con texto oscuro en el botón (≥ 4,5:1);
  - danger, success y warning aclarados.
- **Odontograma:** `--odo-a-realizar` y `--odo-existente` se aclaran en oscuro y se mantienen rojo y azul (DC-3).
- **`shared/ui/tema.ts`:**
  - `leerTema()`, `aplicarTema(tema)`, `useTema()`;
  - `localStorage["tema"]` ∈ `claro | oscuro | sistema`, sin datos personales;
  - con "sistema" se quita el atributo.
- **Script inline en `index.html`:** aplica el atributo antes del render (sin flash), es mínimo y no tiene dependencias.
- **`ToggleTema`:** botón con menú de 3 opciones (`aria-haspopup`, `aria-pressed` en cada opción), en la barra del `AppLayout` y en el header público.
- **Por qué no `dark:` de Tailwind en cada clase:** los componentes ya usan tokens semánticos (`bg-surface`, `text-muted`…). Cambiar los valores del token cubre todas las pantallas sin tocar cada clase.

### D2 — Layout público y landing

- **`PublicLayout`:** header de 64 px (monograma, "Ingresar", toggle de tema), `<main>` y footer con enlaces legales. Lo comparten landing, reserva, comprobante, reprogramación y legales.
- **`HomePage` (landing)**, dials variance 7 / motion 6, con cuatro bloques, cada uno de una familia de layout distinta:
  1. **Hero partido** (texto a la izquierda; a la derecha, la captura de la agenda en un marco con sombra suave y una tarjeta flotante de "Turno confirmado").
  2. **Bento asimétrico de 5 diferenciales:**
     - agenda por sillón, en una celda grande con una captura recortada de la semana;
     - reserva online, con captura del móvil;
     - odontograma;
     - WhatsApp;
     - cumplimiento.
     - Al menos 2 celdas llevan imagen o fondo tintado (anti-slop del taste-skill).
  3. **Franja "Cómo funciona":** 3 pasos con verbo (Reservá, Confirmá, Atendé), sin "Paso 1/2/3".
  4. **CTA final**, más el footer del layout.
- **Capturas reales:** `frontend/public/landing/{agenda.png, semana.png, reserva-movil.png, odontograma.png}` (PNG optimizado, ≤ 250 KB c/u), tomadas con Playwright sobre la base de demo (`seed_demo_agenda.py`, datos sintéticos). Llevan `width`/`height` declarados (CLS) y `loading="lazy"` salvo el hero.
- **Reveal al scroll:** hook `useReveal()` con `IntersectionObserver` (una sola vez) que agrega `data-visible`. CSS con `transition` de `opacity` y `transform` y escalonado por `--i`. Con `prefers-reduced-motion`, visible sin transición.
- **Por qué sin Motion ni GSAP:** el alcance (reveal y escalonado) lo cubre CSS + IntersectionObserver, sin sumar ~30 KB y sin riesgo de scroll-jank.
- **Copy:** concreto y sin em-dash, con métricas solo si son reales (no se inventan porcentajes).

### D3 — Componentes nuevos en `shared/ui`

- **`PageHeader`:** título, descripción opcional, acciones y migas opcionales. Encabezado común de las pantallas de la app.
- **`Tabs`:** navegación con `NavLink` estilizada (subrayado animado con `transform`), para las pestañas del paciente. Se conservan `aria-current="page"` y los nombres actuales.
- **`ToggleTema`:** ver D1.
- **`Avatar`:** iniciales sobre `primary-soft`, para pacientes y profesionales.

### D4 — Pantallas de la app (motion 4)

- **Login:** split en desktop (formulario a la izquierda; a la derecha, un panel con la captura de la agenda sobre `primary-soft`), una columna en móvil; mismos labels, mensajes y flujo.
- **Pacientes:**
  - `PageHeader` con buscador y "Nuevo paciente";
  - lista en tabla responsiva (desktop) o tarjetas (móvil), con Avatar, DNI tabular y obra social;
  - skeleton y EmptyState.
- **Layout del paciente:** cabecera con Avatar, nombre, DNI, contacto y badge de consentimiento; `Tabs` para Ficha, Odontograma, Evoluciones y Adjuntos.
- **Ficha y anamnesis:** Cards con `CardHeader` y `Field`; versiones como línea de tiempo compacta.
- **Odontograma (restyle):**
  - Card contenedora, toolbar de dentición con segmentado y leyenda con chips de color + texto;
  - `PanelPieza` con el estilo del Drawer;
  - **sin tocar** `OdontogramaGrafico` ni `borrador.ts`; solo clases de contenedor y colores vía tokens.
- **Evoluciones:** timeline vertical con hitos (fecha, autor, texto), correcciones marcadas y formulario en Card.
- **Adjuntos:** grilla de tarjetas con ícono por tipo y tamaño, zona de subida con borde punteado y estados.
- **Reserva pública y comprobante:** se reutiliza la estructura de C-06, más el header y footer públicos, pasos visibles y "Reprogramar" en el comprobante (D5).
- **Legales, comprobantes y 404:** tipografía editorial legible (máx. 70ch), índice de secciones y EmptyState en 404.
- **Regla:** cada componente conserva sus textos, roles y labels. Si un test busca un texto que cambia por diseño, se actualiza el test con la misma intención y se deja anotado en `verify.md`.

### D5 — `/reprogramar/{token}`

- **`features/reserva/api.ts`:**
  - `opcionesReprogramacion(token)`;
  - `reprogramar(token, inicio)`: el 409 trae `alternativas` y `leerError` lo expone como un `ApiError` con un payload extra, mediante un fetch propio que conserva el body.
- **`ReprogramarPage`:**
  - en paralelo con `Promise.all`: `obtenerReserva(token)` (turno actual) y `opcionesReprogramacion(token)`;
  - opciones como tarjetas seleccionables con día y hora en la zona de la clínica; "Confirmar cambio";
  - éxito: "Turno reprogramado" más un enlace al comprobante;
  - 409: aviso y reemplazo de las opciones por `alternativas`;
  - 422 / 404 / 429: mensajes claros.
- **Ruta pública** en `router.tsx` bajo `PublicLayout`.
- **`ReservaPage`:** el botón "Reprogramar" (Link) aparece si `cancelable`.

### D6 — Tests

- **Se mantienen:** todas las suites existentes. Las que dependan de textos que el diseño cambia se ajustan sin cambiar su intención (registro en `verify.md`).
- **Nuevos:**
  - `tema.test.tsx`: sistema por defecto; elegir claro u oscuro aplica `data-theme` y persiste; "sistema" quita el atributo;
  - `landing.test.tsx`: CTAs y destinos, imágenes con alt, cero pedidos a `/api`;
  - `reprogramar.test.tsx`: opciones, confirmación OK, 409 con alternativas, 422, 404, link desde el comprobante.
- **Evidencia:** capturas Playwright en claro y oscuro, desktop y móvil, de las pantallas principales.

## Risks / Trade-offs

- [El rediseño toca muchas pantallas de C-10 y los tests de tu compañero] → Se conserva cada texto, rol y label; los cambios de test se registran. Se corren todas las suites tras cada grupo.
- [El modo oscuro puede dejar contrastes malos en lugares olvidados] → Todo pasa por tokens; se revisa con capturas en oscuro de cada pantalla y se mide el contraste de los pares críticos.
- [Las capturas de la landing quedan viejas si cambia la UI] → Hay un script de captura (`scripts/e2e/capturas_landing.py`) para regenerarlas.
- [`localStorage` del tema] → Solo preferencia de UI, no datos personales ni secretos (regla 12). Con try/catch si el storage no está disponible.

## Migration Plan

Solo frontend. Sin migraciones ni cambios de API. Rollback: revertir el commit.
