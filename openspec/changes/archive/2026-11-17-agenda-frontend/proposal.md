# Proposal — agenda-frontend (C-07)

## Why

La recepción no tiene una pantalla de agenda. El motor existe: alta con anti-solapamiento (C-05), estados (C-05b), huecos y sobreturnos (C-05c), horario (C-05d) y reserva online (C-06). Pero hoy un turno solo se ve por id en la API. US-001 y US-002 (lado UI) piden ver el día y la semana por profesional y por sillón, dar turnos en el mostrador y gestionar su estado.

La API tampoco permite **listar** los turnos de un período, y los bloqueos solo los lee el admin. Sin eso no hay agenda posible. C-07 también es la primera pantalla construida con el sistema de diseño nuevo (`design-system/turnos-odontologia/MASTER.md`), así que trae la base visual compartida.

## What Changes

**Backend (solo lectura, sin cambios de modelo ni migraciones):**

- `GET /api/agenda/turnos?desde&hasta[&profesional_id][&sillon_id]`: turnos de la ventana (hasta 7 días) con nombre del paciente y de la prestación, estado, origen y marca de sobreturno. Admin y recepción ven toda la clínica; el odontólogo, solo su agenda (`profesional_id` obligatorio y propio).
- `GET /api/agenda/bloqueos?desde&hasta[&profesional_id]`: bloqueos activos de la ventana (de clínica, de profesional y de sillón), para pintarlos como no reservables. Mismas reglas de rol.

**Frontend:**

- **Base visual compartida:**
  - tokens del `MASTER.md` en `styles.css`;
  - Figtree + Noto Sans;
  - íconos `lucide-react`;
  - componentes base en `shared/ui`: Button, Field/Input/Select, Card, Badge de estado, Drawer, Skeleton, EmptyState;
  - restyle de `Aviso` y `DialogoConfirmacion` sin cambiar su API.
- **Shell autenticado** con sidebar (Agenda, Pacientes) y barra superior. La barra conserva identidad, roles y "Cerrar sesión", como pide `web-session`.
- **`/agenda`:**
  - vista **Día** con una columna por sillón y filtro por profesional;
  - vista **Semana** con 7 columnas del profesional elegido;
  - eje de horas y franjas fuera de horario sombreadas;
  - bloqueos superpuestos y no clickeables;
  - línea "ahora";
  - badges de estado y origen (mostrador, enlace o WhatsApp) y marca de sobreturno.
- **Drawer de turno:**
  - **Alta** desde un hueco: buscador de paciente por nombre o DNI más **alta rápida** con `POST /api/pacientes`; prestación; sobreturno con motivo si el rol lo permite.
  - **Detalle** con las transiciones permitidas por rol (confirmar, asistido, ausente, cancelar).
  - Ante un **409**, se ofrecen huecos alternativos del mismo profesional y día.
- **Datos frescos:** carga en paralelo (`Promise.all`) de turnos, bloqueos y horarios; recarga al volver a la pestaña y cada 60 s; deep-link `/agenda?fecha=…&vista=…&profesional=…`, preparado para C-17.

### Decisiones tomadas con el usuario (2026-11-17)

1. Día por sillón con filtro de profesional, y semana por profesional.
2. Alta con buscador y alta rápida de paciente.
3. Recarga al enfocar y cada 60 s (sin websockets).
4. Estética clínica moderna premium, según el `MASTER.md`. El rediseño de las pantallas existentes de C-10/C-06 queda para **C-20 `rediseno-visual`**. Acá solo cambian los tokens globales y el shell, que todas heredan.

## Non-goals

- Arrastrar y soltar para reprogramar. La reprogramación por enlace ya es de C-17, y la del staff no está en la KB.
- Gestión de bloqueos y horarios desde la agenda (se usa la API de admin o C-14).
- Lista de espera en la UI, cobros y seña (C-12/C-14).
- Rediseño de las pantallas de pacientes, ficha, odontograma, evoluciones y reserva pública (C-20).
- Tiempo real por websockets.

## Capabilities

### New Capabilities

- `agenda-view`: lectura de la agenda para el staff (turnos con nombres y bloqueos de una ventana) con las reglas de rol y de tenant.
- `agenda-web`: pantalla `/agenda` (vistas, alta, detalle, transiciones, 409 con alternativas, refresco) y base visual compartida.

### Modified Capabilities

- `web-session`: el layout autenticado suma la navegación lateral con "Agenda".

## Impact

- **Backend:**
  - `backend/app/api/agenda.py` (2 rutas nuevas, el router ya existe);
  - `backend/app/domain/agenda/agenda_lectura.py` (consultas);
  - schemas `AgendaTurnoOut` y `AgendaBloqueoOut`.
  - Sin migración.
- **Frontend:**
  - `frontend/src/styles.css` y `index.html` (fuentes);
  - `frontend/src/shared/ui/*`;
  - `frontend/src/features/auth/AppLayout.tsx`;
  - `frontend/src/features/agenda/*` (nuevo);
  - `frontend/src/router.tsx`;
  - `package.json`: `lucide-react`, la única dependencia nueva.
- **Tests:**
  - backend: integración de los 2 endpoints, con RBAC y aislamiento;
  - frontend: vitest de la agenda (render día y semana, bloqueo no clickeable, 409 con alternativas, roles);
  - los tests existentes del shell siguen verdes.
- Governance: BAJO (CHANGES). La base visual toca todas las pantallas, así que el diseño se revisa antes del apply.
