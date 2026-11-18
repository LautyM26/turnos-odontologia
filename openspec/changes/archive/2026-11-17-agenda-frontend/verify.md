# Verify — agenda-frontend (C-07)

Fecha: 2026-11-17. Resultado: **VERDE, revisado y archivado** el 2026-11-17.

## Entorno

- Windows 11, Docker Desktop (WSL2), PostgreSQL `postgres:16-alpine` vía testcontainers; Python 3.12.10, pytest 9.2, ruff 0.17.5.
- Frontend: Vite 8, React 19, TypeScript estricto, vitest 4, biome 2, `lucide-react` 0.469 (única dependencia nueva).
- Playwright (Python, Chromium) para la evidencia en navegador real.
- Diseño D1–D10 aprobado por el usuario el 2026-11-17. Base: `main` en `2fab30d` (incluye C-15/C-16/C-17 del equipo).
- Skills usadas:
  - `graphify`: grafo del frontend, local, no versionado;
  - `ui-ux-pro-max`: sistema de diseño en `design-system/turnos-odontologia/MASTER.md`;
  - `design-taste-frontend`: design read, dials 5/4/6 y checklist;
  - `dominio-agenda`;
  - Context7: no hizo falta, porque no se usó ninguna API de librería nueva más allá de `lucide-react`.

## Comandos

```
.venv/Scripts/python -m pytest backend/tests -q
.venv/Scripts/ruff check backend
cd frontend && npx tsc --noEmit && npm run build && npx vitest run
openspec validate agenda-frontend --strict
```

## Resultados

- **Backend, suite completa:** **1576 passed, 0 failed** (13 min 48 s). `ruff check backend` limpio.
- **Frontend:** `tsc --noEmit` limpio, `npm run build` OK y `vitest run` **249 passed** (19 archivos). Antes eran 215, así que hay **34 tests nuevos**. La suite se corrió 2 veces seguidas en verde.
- **biome:** los archivos nuevos de C-07 pasan sin errores. El `npm run lint` del repo entero sigue con los errores de finales de línea CRLF de la copia de trabajo en Windows (deuda previa, ver verify de C-06).

| Archivo | Tests | Cubre |
|---|---|---|
| backend · integration/test_agenda_lectura_api.py | 9 | "Día de la recepción" (orden, nombres, sobreturno, sin DNI ni contacto), filtros por profesional y sillón, cancelado incluido y baja excluida, ventana inválida 422 (turnos y bloqueos), bloqueos por alcance, odontólogo con su agenda 200, otra 403 y sin `profesional_id` 422, sin token 401, aislamiento A/B |
| frontend · tests/agenda.test.tsx | 13 | día por sillón con estado y sobreturno; **carga en paralelo** (regla 13); bloqueo sin alta; recarga cada 60 s; semana por deep-link; cambio de vista en la URL; alta con paciente existente (cuerpo exacto, recarga, `aria-live`); alta rápida de paciente; 409 con alternativas que cambian hora y sillón; cancelar con confirmación; 422 en el detalle; odontólogo con su agenda fija y sin alta; odontólogo sin acciones antes del inicio |
| frontend · tests/agenda-tiempo.test.ts | 9 | zona AR con día UTC distinto, `instanteLocal`, ventana del día, semana de lunes a domingo, suma de días entre meses, rango visible con default 08–20 y sobreturno fuera de franja, carriles (superpuestos y contiguos), transiciones visibles por rol |
| frontend · tests/ui-componentes.test.tsx | 10 | Field (label, ayuda y error con `aria-describedby`), Button `cargando`, Drawer (título accesible, cerrar y Escape), EstadoBadge (5 estados) |
| frontend · tests/app-shell.test.tsx | +2 | navegación "Agenda" y menú móvil (`aria-expanded`, Escape) |

### Ajustes a tests existentes del equipo (sin cambiar su intención)

- `odontograma-ui.test.tsx`: "sin SVG" pasó a `svg:not(.lucide)`. El test verifica que no se dibuje el odontograma; los íconos de interfaz (Lucide) no son gráficos clínicos.
- `tests/setup.ts`: `asyncUtilTimeout` de 3 s. Las rutas con `lazy` de C-10 y C-07 superaban 1 s con la suite en paralelo y fallaban de forma intermitente; dos corridas seguidas quedaron en verde.
- Durante el trabajo se pisó por error `tests/ui-base.test.tsx` (de C-10) con un archivo nuevo. **Se restauró desde git** y el test nuevo se renombró a `ui-componentes.test.tsx`.

## Pruebas de mutación

- **Backend:** sin `require_own_agenda` en `/api/agenda/turnos` y `/bloqueos`, falla `test_odontologo_su_agenda_otra_y_sin_profesional`.
- **Frontend:** reemplazando el `Promise.all` de `useAgenda` por llamadas secuenciales, falla `carga turnos, bloqueos y horarios en paralelo (regla dura 13)`.

En ambos casos se restauró el código.

## Prueba manual y evidencia (uvicorn + Vite + Chromium real)

**Datos:** `backend/scripts/seed_demo_agenda.py` (nuevo, idempotente), sintético y con `es_seed`. Carga 3 sillones, 3 profesionales con horario, 12 pacientes ficticios, un bloqueo de sillón y uno de profesional, y **60 turnos de la semana creados con el motor real**. Una segunda corrida crea 0.

Recorrido como **recepción** (capturas en `evidencias/`):

1. `01-dia.png`: miércoles por sillón, con el bloqueo "Mantenimiento del equipo" en el box, el sobreturno punteado, turnos online (ícono) y WhatsApp, y el resumen del día (turnos, confirmados, online, sobreturnos).
2. `02-detalle.png`: detalle del sobreturno con su motivo y las acciones permitidas.
3. `03-semana.png`: semana del profesional, con hoy realzado.
4. `04-alta-busqueda.png`: búsqueda de paciente en el panel de alta.
5. `05-alta-409-alternativas.png`: horario tomado con 6 alternativas reales.
6. `06-turno-creado.png`: el turno elegido de las alternativas aparece en la grilla resaltado.
7. `07-movil-dia.png` y `08-movil-menu.png`: 390 px, grilla scrolleable y menú lateral.

**Revisión visual contra el `MASTER.md`**, con lo que se corrigió:

- Los encabezados de columna salían todos en teal en la vista Día. Ahora el realce es solo para hoy en la vista Semana.
- En turnos de 30 min se cortaba la tercera línea. La prestación ahora se muestra solo si entra (≥ 60 px).
- Fuera del horario, el scroll inicial iba al final. Ahora va al primer turno.
- Los turnos cancelados ocupaban carriles y apretaban la grilla. Ahora van atenuados detrás, sin reservar carril.

**Checklist de `design-taste-frontend` y `MASTER.md`:** cero em-dash en la UI; un acento (teal) más el coral reservado a "ahora" y "online"; radios coherentes (6/10/14/20); contraste AA en los botones; labels visibles y errores junto al campo; estados de carga (skeleton), vacío y error; motion motivado (entrada de panel, cambio de vista, resaltado del turno creado), sin overshoot y respetando `prefers-reduced-motion`; íconos de una sola familia (Lucide, aprobado en D3); sin emojis.

**Pendiente de diseño (C-20):** modo oscuro y rediseño de las pantallas de C-10/C-06, que hoy solo heredan los tokens y el shell.

## Trazabilidad

- README: agenda, tests y seed de demo. `docs/CONTINUAR.md`: C-07 y C-20. `CHANGES.md`: ficha **C-20 `rediseno-visual`**. KB `04`: sin cambios de modelo (confirmado).
- `dominio-agenda`: sección 4 (agenda del staff) y trazabilidad de la regla 13; copias sincronizadas. `verificar.py dominio-agenda RN-AG RN-TU`: **OK** después del archive.

## Archivo

- Revisado por el usuario el 2026-11-17 y archivado como `2026-11-17-agenda-frontend`: `agenda-view` (3 requirements) y `agenda-web` (7) creadas, `web-session` +1. `openspec validate --specs`: 34/34.
- Decisión del usuario: la pantalla pública `/reprogramar/{token}` (C-17) pasa a **C-20**.
