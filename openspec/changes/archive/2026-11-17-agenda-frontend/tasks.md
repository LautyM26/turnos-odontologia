# Tasks — agenda-frontend (C-07)

> Antes de la tarea 1.1, el usuario aprueba `design.md` (D1–D10): la base visual toca todas las pantallas.
> TDD en cada grupo. Integración del backend solo con testcontainers `postgres:16-alpine` (regla dura 9).

## 1. Lectura de agenda en el backend

- [x] 1.1 `huecos.validar_ventana` (extraída sin cambiar el comportamiento) y `agenda_lectura.py` con `turnos_de_ventana` y `bloqueos_de_ventana` + schemas `AgendaTurnoOut`/`AgendaBloqueoOut` (D1, D2). Verificar que `test_huecos_servicio.py` y `test_huecos_api.py` siguen verdes.
- [x] 1.2 Rutas `GET /api/agenda/turnos` y `GET /api/agenda/bloqueos` (D1). Verificar con `backend/tests/integration/test_agenda_lectura_api.py`:
  - "Día de la recepción": 2 turnos ordenados, nombres, sobreturno;
  - filtro por profesional y por sillón;
  - cancelado incluido y dado de baja excluido;
  - ventana de 8 días o `hasta <= desde` → 422;
  - bloqueos de clínica, profesional y sillón con su alcance;
  - odontólogo con su agenda 200, con otra 403 y sin `profesional_id` 422;
  - sin token 401;
  - aislamiento A/B (0 filas de B).

## 2. Base visual compartida

- [x] 2.1 Tokens del `MASTER.md` en `styles.css` (mismos nombres + nuevos), fuentes en `index.html` y `lucide-react` en `package.json` (D3). Verificar con `npm run build` y que los tests de vitest existentes sigan verdes.
- [x] 2.2 Componentes `shared/ui`: Button, Field/Input/Select/Textarea, Card, EstadoBadge, Drawer, Skeleton y EmptyState; restyle de `Aviso` y `DialogoConfirmacion` con la misma API (D4). Verificar con `frontend/tests/ui-base.test.tsx`:
  - Field asocia label, ayuda y error;
  - Button `loading` deshabilita y anuncia;
  - Drawer atrapa el foco y cierra con Escape;
  - EstadoBadge muestra texto por estado.
- [x] 2.3 Shell con sidebar y navegación "Agenda"/"Pacientes", barra superior con identidad y "Cerrar sesión", menú móvil (D5). Verificar con `app-shell.test.tsx` actualizado: navegación con `aria-current`, "Abrir menú" y Escape, y el resto de los tests intactos.

## 3. Agenda

- [x] 3.1 `features/agenda/tiempo.ts` (zona de la clínica: minutos locales, ventana UTC del día y de la semana, rango visible), `carriles.ts` (superposiciones) y `transiciones.ts` (botones por estado y rol) (D6, D8). Verificar con `frontend/tests/agenda-tiempo.test.ts`: conversión en `America/Argentina/Buenos_Aires` con día UTC distinto, semana de lunes a domingo, rango por franjas con default 08–20, carriles para dos turnos superpuestos y transiciones por rol.
- [x] 3.2 `useAgenda` (catálogo + `Promise.all` de turnos, bloqueos y horarios; refresco cada 60 s y al enfocar; estado en la URL) y `AgendaPage` con toolbar (hoy, anterior/siguiente, fecha, Día/Semana, profesional), grilla día por sillón y semana por profesional, bloqueos, fuera de horario, línea "ahora" y skeleton y vacío (D6, D7). Verificar con `frontend/tests/agenda.test.tsx`:
  - render día con turnos por sillón y badges;
  - semana del profesional;
  - bloqueo que no abre el alta;
  - las 3 cargas salen en paralelo;
  - deep-link `?fecha&vista`;
  - polling con timers falsos.
- [x] 3.3 Panel de alta (buscador + alta rápida + prestación + sobreturno) y 409 con alternativas (D8). Verificar en `agenda.test.tsx`: alta con paciente existente y su aparición en la grilla, alta rápida que crea el paciente y lo elige, 409 con hasta 6 alternativas que al elegirlas actualizan la hora, y odontólogo sin alta.
- [x] 3.4 Panel de detalle con transiciones por rol, cancelar con motivo y 422 con mensaje (D8). Verificar en `agenda.test.tsx`: confirmar, cancelar con diálogo, 422 que muestra el error, y odontólogo que solo ve asistido/ausente desde el inicio.
- [x] 3.5 Ruta `/agenda` en `router.tsx` (hija de `AppLayout`), motion (D9) y accesibilidad (nombres de los turnos, teclado, `aria-live`). Verificar `tsc --noEmit`, `npm run build`, `npx vitest run` y biome sobre los archivos nuevos.

## 4. Integración, evidencia y documentación

- [x] 4.1 Suite backend completa + `ruff check backend`; frontend con build y vitest completos. Prueba de mutación: quitar `require_own_agenda` de `/api/agenda/turnos`, o el `Promise.all`, y verificar que algún test falla. Todo en `verify.md`.
- [x] 4.2 Prueba manual con uvicorn + Vite y seed demo: capturas con Playwright de la agenda día y semana, alta con 409 y alternativas, detalle y confirmación, a 1440 y 390 px, en `evidencias/`; revisión visual contra el checklist del `MASTER.md`.
- [x] 4.3 KB `04` (sin cambios de modelo: confirmar), README (enlace `/agenda`, tests del change) y `docs/CONTINUAR.md` (C-07 hecho, C-20 rediseño en curso). Agregar al roadmap la ficha **C-20 `rediseno-visual`** en `CHANGES.md`.
- [x] 4.4 `dominio-agenda`: la fila de C-07 y su sección 4 (agenda frontend), con las copias sincronizadas. Verificar con `verificar.py dominio-agenda RN-AG RN-TU` → OK después del archive.

## Workflow follow-up

- `/opsx:archive agenda-frontend` tras la revisión humana y con `verify.md` completo.
- Marcar C-07 `[x]` en `CHANGES.md`.
