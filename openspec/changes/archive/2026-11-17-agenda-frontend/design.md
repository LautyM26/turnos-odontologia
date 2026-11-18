# Design — agenda-frontend (C-07)

## Context

Motivación: ver `proposal.md`. Requisitos: `specs/agenda-view`, `specs/agenda-web`, `specs/web-session`. Dirección visual: `design-system/turnos-odontologia/MASTER.md`.

Estado observado:

- **Backend:**
  - `POST /api/turnos` (admin/recepción), `GET /api/turnos/{id}`, `POST /api/turnos/{id}/transicion` (C-05b, el odontólogo solo asistido/ausente en su agenda);
  - `GET /api/agenda/huecos` (C-05c/C-05d, `require_own_agenda`), `GET /api/catalogo/{profesionales,sillones,prestaciones}` (staff) y `GET /api/catalogo/profesionales/{id}/horario` (staff, devuelve `zona_horaria`);
  - `GET /api/pacientes?q=|dni=` y `POST /api/pacientes` (staff).
  - **No hay** listado de turnos por período, y `GET /api/admin/bloqueos` es solo para admin.
  - `huecos.py` ya valida la ventana (`VENTANA_MAXIMA` de 7 días, zona, `hasta > desde`).
- **Frontend (C-10/C-06):**
  - router de datos con `AppLayout` (header superior, `max-w-5xl`), `requireSession` y `useSesion()`; `Me` trae `sub`, `email`, `tenant_id` y `roles`, sin `profesional_id`;
  - `ProfesionalOut.usuario_id` permite resolver en el cliente qué profesional es el del odontólogo;
  - `apiFetch`/`ApiError` (con `campos` por campo del 422) y `mockApi` en los tests;
  - tokens neutros en `styles.css`, `Aviso` y `DialogoConfirmacion` (`<dialog>` nativo);
  - tests de `app-shell` que buscan "Cerrar sesión", el email y los roles.

## Goals / Non-Goals

**Goals:**

- Una agenda usable para el mostrador y lista para el video.
- Una sola representación visual de turno para día y semana.
- Una base visual que C-20 reutiliza sin rehacer.

**Non-Goals:** drag & drop, edición de bloqueos y horarios, websockets, rediseño de pantallas existentes (C-20).

## Decisions

### D1 — Lectura de agenda en el backend: dos endpoints de solo lectura

`backend/app/domain/agenda/agenda_lectura.py`:

- **`turnos_de_ventana(session, clinica_id, desde, hasta, profesional_id, sillon_id)`**
  - Un `SELECT` de `Turno` con JOIN a `Paciente` y `Prestacion`, todo scopeado por `clinica_id`.
  - Filtros: `Turno.is_active` y `rango && tstzrange(desde, hasta)`, más los filtros opcionales. Orden por inicio e id.
  - Devuelve todos los estados (los cancelados se pintan atenuados).
- **`bloqueos_de_ventana(session, clinica_id, desde, hasta, profesional_id)`**
  - Bloqueos activos que se superponen, en tres grupos: de clínica (ambos alcances nulos), de sillón (todos) y de profesional (el pedido, o todos si no se filtra).
- **Validación de ventana:** se extrae a `huecos.validar_ventana(desde, hasta)` para reutilizarla. Es un refactor mínimo y `buscar_huecos` la llama igual.
- **Rutas en `api/agenda.py`** (router existente): `GET /turnos` y `GET /bloqueos`, con `require_own_agenda` (admin/recepción todo; odontólogo con `profesional_id` propio o `403`; sin token `401`), `require_tenant_checked` y `AwareDatetime` en la query.
- **Schemas:** `AgendaTurnoOut` (incluye `paciente_nombre = "Apellido, Nombre"` y `prestacion_nombre`) y `AgendaBloqueoOut` (`alcance` ∈ `clinica | profesional | sillon` más ids).
- **Por qué no ampliar `GET /api/turnos`:** ese router es de escritura y detalle; la agenda es una vista de lectura con otro contrato y otras reglas de rol, y vive junto a `huecos` en `/api/agenda`.

### D2 — Datos personales en la agenda

La agenda muestra solo "Apellido, Nombre" y la prestación. No muestra DNI, contacto ni datos clínicos. Es dato de contacto, que recepción ya ve (C-08); RBAC clínico intacto (regla dura 16).

### D3 — Base visual: tokens, fuentes e íconos

- **`styles.css`:**
  - se reemplazan los valores de los tokens existentes (`--background`, `--foreground`, `--primary`, `--surface`, `--muted`, `--border`, `--danger`, `--success`, `--warning`, `--focus` y sus `-soft`) por los del `MASTER.md`, y se agregan `--surface-2`, `--border-strong`, `--primary-hover`, `--primary-soft`, `--accent`, `--accent-soft` y sombras;
  - se mantienen los nombres de los tokens para que las pantallas de C-10/C-06 hereden el look sin tocarlas;
  - se agregan `--font-heading` y `--font-sans` y el keyframe `aparecer`, que ya existía.
- **`index.html`:** `preconnect` a Google Fonts y Figtree (600/700) + Noto Sans (400/500/600) con `display=swap`.
- **Íconos:** `lucide-react`, la única dependencia nueva (ESM, tree-shaking por ícono). Sin librerías de componentes ni de motion: se usan `<dialog>` nativo, CSS transitions y keyframes. **Por qué:** `motion` o una librería headless sumarían peso por animaciones que CSS resuelve, y el proyecto ya usa `<dialog>` con foco nativo.

### D4 — Componentes base en `shared/ui`

Se agregan Button (primary, secondary, ghost, danger; sm/md; loading), Field (label + ayuda + error con `aria-describedby`) con Input, Select y Textarea, Card, EstadoBadge (punto + texto, por estado del turno), Drawer (`<dialog>` lateral con foco atrapado y Escape), Skeleton y EmptyState.

`Aviso` y `DialogoConfirmacion` se restylean **sin cambiar props ni roles**: los tests de C-10/C-06 siguen válidos.

### D5 — Shell con sidebar

`AppLayout`:

- **Desktop:** sidebar de 248 px con logotipo, navegación (Agenda con `CalendarDays`, Pacientes con `Users`) y bloque de clínica.
- **Barra superior:** título y "Cerrar sesión" con email y roles, como pide `web-session`.
- **< 1024 px:** la sidebar se oculta y se abre con el botón "Abrir menú" (drawer), que cierra con Escape.
- **Contenido:** `max-w-6xl` en general; la agenda usa ancho completo con `data-ancho="completo"`.
- Destino por defecto tras el login: `/pacientes`, sin cambios (los tests lo verifican).

### D6 — Grilla de la agenda

- **Tiempo en la zona de la clínica:**
  - se toma de `GET /api/catalogo/profesionales/{id}/horario` (`zona_horaria`);
  - los helpers de `features/agenda/tiempo.ts` usan `Intl.DateTimeFormat(..., { timeZone })` para pasar ISO a minutos locales y fecha local, y la fecha local a ventana UTC (`desde`/`hasta`);
  - sin librerías de fechas.
- **Rango visible:** la unión de las franjas del horario de los profesionales mostrados para esos días, redondeada a la hora y con 08:00–20:00 si no hay franjas. Lo que queda fuera de una franja se sombrea.
- **Escala:** 1,6 px por minuto (15 min = 24 px). Los turnos van posicionados en absoluto dentro de su columna (`top = (inicio − rango.inicio) × escala`).
- **Columnas:**
  - Día: sillones activos (los del catálogo) y, con filtro, solo los turnos de ese profesional.
  - Semana: 7 días del profesional elegido (lunes a domingo).
- **Superposiciones** (sobreturnos): asignación de carriles por columna con un barrido simple por orden de inicio; cada turno ocupa `1/n` del ancho.
- **Bloqueos:** franjas con un patrón diagonal (`repeating-linear-gradient` de tokens) y su motivo. Los de clínica cubren todas las columnas, los de sillón su columna y los de profesional sus turnos (vista semana o filtro). La capa de bloqueo intercepta el clic.
- **Línea "ahora":** coral, actualizada cada minuto, solo si la fecha es hoy.
- **Slots clickeables:** botones invisibles de 15 min en cada columna (solo admin/recepción y fuera de bloqueos). Al enfocarlos con teclado muestran "+ Nuevo turno 10:15".

### D7 — Carga, refresco y estado

`useAgenda(fecha, vista, profesionalId)`:

1. Catálogo (sillones, profesionales, prestaciones), cargado una vez.
2. En paralelo con `Promise.all` (regla dura 13): turnos, bloqueos y los horarios de los profesionales relevantes.
3. Refresco con `setInterval` de 60 s y en `visibilitychange` (pestaña visible), cancelando con `AbortController`.

Estado en la URL (`useSearchParams`: `fecha`, `vista`, `profesional`): deep-link y botón atrás.

El odontólogo:

- resuelve su profesional por `usuario_id === me.sub`;
- queda con el filtro fijo;
- la vista y el alta quedan de solo lectura, salvo las transiciones permitidas.

### D8 — Panel de turno

**Alta (admin/recepción):**

- Fecha, hora, sillón y profesional precargados y editables con selects.
- Buscador de paciente con `GET /api/pacientes?q=` y debounce de 250 ms (si el texto son dígitos, `dni=`), con resultados en listbox accesible.
- "Nuevo paciente": alta rápida (nombre, apellido, DNI, email o teléfono) con `POST /api/pacientes`; los 422 van por campo con `ApiError.campos`.
- Select de prestación, que muestra la duración: el fin lo calcula el servidor (regla dura 6).
- Sobreturno: checkbox y motivo obligatorio.
- Si `POST /api/turnos` responde **409**:
  - aviso, recarga de la agenda;
  - `GET /api/agenda/huecos` del mismo profesional, prestación y día;
  - hasta 6 alternativas: primero las posteriores a la hora pedida y después las anteriores, en orden.

**Detalle:**

- Datos del turno y origen (mostrador, enlace o WhatsApp), con acciones según `TRANSICIONES` (C-05b) y el rol.
- Las mismas reglas se replican en `features/agenda/transiciones.ts` **solo para mostrar u ocultar** botones; la API decide (422 o 403 con mensaje).
- Cancelar pide motivo opcional con `DialogoConfirmacion`.

### D9 — Motion

- Drawer: entra con `translateX` de 240 ms `cubic-bezier(.2,.8,.2,1)` y sale con 160 ms.
- Cambio de día o vista: fade con desplazamiento de 8 px en 180 ms.
- Turnos nuevos tras crear: "pulse" suave del borde, una vez.
- Hover de 120 ms.
- Todo respeta el reset global de `prefers-reduced-motion` que ya existe.
- Nada de overshoot en la grilla (anti-patrón del `MASTER.md`).

### D10 — Tests

- **Backend:** `backend/tests/integration/test_agenda_lectura_api.py` (escenarios de `agenda-view`: listado, filtros, cancelado incluido, baja excluida, ventana 422, bloqueos por alcance, RBAC 401/403, aislamiento).
- **Frontend:** `frontend/tests/agenda.test.tsx` y `agenda-tiempo.test.ts` con `mockApi` y `vi.setSystemTime`:
  - render día y semana;
  - bloqueo no clickeable;
  - alta con paciente existente y con alta rápida;
  - 409 con alternativas;
  - transiciones por rol;
  - odontólogo de solo lectura;
  - deep-link;
  - helpers de zona horaria (incluido un día con cambio de fecha UTC).
- **Shell:** `app-shell.test.tsx` sigue verde y se suma "Agenda" en la navegación.

## Risks / Trade-offs

- [Cambiar los valores de los tokens altera todas las pantallas existentes] → Es intencional: el teal y las fuentes nuevas llegan a todo. Los nombres se mantienen, así que nada se rompe; se verifica con los tests de C-10/C-06 y capturas. El rediseño fino es de C-20.
- [Las fuentes externas de Google Fonts requieren red] → `display=swap` con fallback `system-ui`; en producción se puede autohospedar.
- [El polling de 60 s es ineficiente con muchos usuarios] → MVP de una clínica; la mejora natural es SSE o websockets.
- [Las reglas de transición se duplican en el cliente para mostrar botones] → Solo afectan la UI; la API es la fuente de verdad y devuelve 422 o 403.
- [El rango visible depende de horarios cargados] → Hay un default de 08:00–20:00; los turnos fuera del rango (sobreturnos) amplían el rango para no quedar ocultos.

## Migration Plan

Sin migraciones. Despliegue: backend (2 rutas nuevas, solo lectura) y frontend. Rollback: revertir el commit; no hay datos nuevos.
