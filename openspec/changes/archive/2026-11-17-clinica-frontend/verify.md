# Verify — clinica-frontend (C-10)

Fecha: 2026-11-17. Gobernanza MEDIO. Todo en `frontend/` salvo el seed (`backend/scripts/seed_demo_clinica.py`) y el E2E (`scripts/e2e/clinica_demo.py`).

## Gates (11.1)

| Gate | Resultado |
|------|-----------|
| `npm test` | 14 archivos, **202 tests** en verde (183 de C-10 + 8 de C-01 + 11 de C-18 `legal.test.tsx` que corre el otro agente) |
| `npx tsc --noEmit` | sin errores |
| `npm run build` | limpio (rutas clínicas en chunks `lazy`) |
| `npx biome check .` | limpio (64 archivos) |
| `any` explícito / acceso a `localStorage`/`sessionStorage` en `src/` | 0 / 0 (el test de C-01 lo audita) |
| `ruff check backend/scripts` | limpio |

## Escenario de cada spec -> test

| Spec | Escenarios -> test |
|------|--------------------|
| `web-session` | Login, vuelve a la ruta, 401, 429, botón deshabilitado, `?expirada=1`: `tests/app-shell.test.tsx` (LoginPage). Ruta protegida / públicas / /login con sesión / recarga por refresh / sesión expirada: `app-shell` (rutas). Token solo en memoria: `tests/client.test.ts` (auditoría del fuente). Renovación, 3×401 -> 1 refresh, refresh rechazado: `tests/client-http.test.ts`, `tests/session.test.ts`. Logout y logout con backend caído, roles legibles (incluido multi-rol): `app-shell` (AppLayout). `redirectTo` externo: `session.test.ts`, `app-shell`. |
| `platform-config` | 4 escenarios de tenant: `tests/client-http.test.ts` + `tests/client.test.ts` (existentes de C-01). |
| `patients-web` | Listado, más de una página, vacío, error + Reintentar, búsqueda q/dni, texto corto, sin resultados, encabezado con/sin consentimiento, 404, PATCH parcial, 409/422, obligatorio vacío, riesgo solo lectura, consentimiento otorgar/cancelar/revocar: `tests/pacientes.test.tsx`. |
| `clinical-record-web` | Pestañas enlazables y deep link, carga en paralelo, historia 500, recepción sin acceso (ficha, odontograma, evoluciones, adjuntos), recepción edita contacto, admin sin escritura, sin consentimiento (ficha/odontograma/evoluciones/adjuntos), 403 de consentimiento al guardar, ficha v0/v1/409/versiones, adjuntos listado/descarga/subida/415/413/422: `tests/ficha.test.tsx`, `pacientes.test.tsx`, `odontograma-ui.test.tsx`, `evoluciones.test.tsx`, `adjuntos.test.tsx`. |
| `odontogram-web` | 32/20/52 piezas, versión 0, selector de dentición con/sin descarte, marcado por cara/pieza, ausente con caras, Sin marca, teclado + foco, tabla de hallazgos, guardado, sin cambios, 422, 409 + recarga, aviso de salida, historial: `tests/odontograma-modelo.test.ts` (FDI + reducer) y `tests/odontograma-ui.test.tsx`. |
| `evolutions-web` | Timeline, paginación, vacío, sin Editar/Eliminar, auditoría del fuente (sin PUT/PATCH/DELETE), alta, texto vacío, 422, doble envío, corrección (+1 entrada, original "Corregida"), sin motivo, 409, quién puede corregir, cadena con foco: `tests/evoluciones.test.tsx`. |

## Auditoría `web-design-guidelines` (11.2)

Revisión manual de `features/auth`, `features/clinica`, `shared/ui` contra los criterios de la skill:

| Hallazgo | Resolución |
|----------|------------|
| Sin `<title>` por pantalla (SPA con un solo título) | Corregido: `<title>` en Login, Pacientes y Paciente (test "Título del documento") |
| Texto largo de evoluciones podía desbordar | Corregido: `break-words` |
| Cabecera `<header aria-label>` inválida para Biome | Corregido: `<section aria-label>` |
| Región del odontograma con scroll horizontal en 360 px | OK: cada pieza es un botón enfocable; E2E verifica `scrollWidth == clientWidth` (360) |
| Foco visible, skip link, `aria-current`, `role=alert/status`, labels visibles, `prefers-reduced-motion`, contraste AA de tokens, no depender del color (trama + símbolo + tabla de hallazgos) | OK |
| Botones secundarios de ~28 px de alto (< 44 px) | **Pendiente menor**: no se cambió para no abrir diseño; las piezas del odontograma sí cumplen (44x40) |

## E2E real (11.3)

`scripts/e2e/clinica_demo.py` con Python Playwright (Chromium headless), backend uvicorn + Vite + PostgreSQL 16 real (contenedor descartable, migraciones hasta head, seed de demo). **11/11 pasos OK**, consola sin errores inesperados (solo 401/403/409 deliberados). Capturas en `evidencias/`:

| Paso | Captura |
|------|---------|
| Login | `01-login.png` |
| Listado | `02-pacientes.png` |
| Ficha | `03-ficha.png` |
| Panel de pieza 16 (cara O) | `04-panel-pieza-16.png` |
| Odontograma guardado v1 | `05-odontograma-guardado.png` |
| Conflicto 409 con borrador conservado | `06-conflicto-409.png` |
| Evolución creada / corregida (original "Corregida") | `07-…`, `08-evolucion-corregida.png` |
| Adjunto inválido / PDF subido | `09-…`, `10-adjunto-subido.png` |
| 360 px sin scroll horizontal | `11-odontograma-360px.png` |
| Recepción: Sin acceso clínico | `12-recepcion-sin-acceso-clinico.png` |

Logout + "atrás" vuelve a pedir login: OK. El E2E detectó dos defectos reales, corregidos con el flujo en verde: el índice del paciente re-ejecutaba el loader por la redirección (dos lecturas de historia = 2 eventos de auditoría; ahora `<Navigate>` y test que exige un solo GET) y los loaders hijos pedían datos sin sesión (ahora `await requireSession()` antes).

## Desvíos

- Formularios con `useState`/`onSubmit` + guard de doble envío en vez de `useActionState` (D5): `useActionState` resetea los campos tras la acción y habría perdido el texto en un 422.
- `frontend/.gitignore` y `css.parser.tailwindDirectives` en `biome.json`: Biome no corría (sin archivo de ignore / Tailwind v4).
- `vite.config.ts`: el destino del proxy admite `VITE_PROXY_TARGET` (puerto 8000 ocupado en la máquina durante el E2E).
- Tarea 6.2: los estados "Sin acceso clínico" se verifican en cada pestaña dentro de su archivo de tests (ficha, odontograma, evoluciones, adjuntos).
- Sin consultas nuevas a Context7 (las 4 de D12 alcanzaron).
- Los dos procesos de la primera corrida (uvicorn :8000 y Vite :5173) no pudieron detenerse con `taskkill` por política del entorno; se relanzó en :8010/:5183 y esos sí se detuvieron. Verificar si quedó algo en :5173.

## Tabla TDD

| Tarea | Archivo de test | Capa | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|-------|-----------------|------|------------|-----|-------|-------------|----------|
| 1.1-1.3 | `setup.test.tsx`, `helpers/api.test.ts` | Infra | 8/8 | n/a (infra) | ok | 3+2 casos | ok |
| 2.1-2.3 | `client-http.test.ts` | Unit | 8/8 | 12 fallan (faltan exports) | ok | 12 casos | ok |
| 3.1 | `session.test.ts` | Unit | 20/20 | escrito junto con el código | ok | 10 casos | ok |
| 3.2-3.4 | `app-shell.test.tsx` | Integración | 30/30 | falla (sin router) | ok | 23 casos | ok |
| 4.1-4.4 | `ui-base.test.tsx` | Unit/comp. | 57/57 | falla (sin módulos) | ok | 18 casos | ok |
| 5.1-5.6 | `pacientes.test.tsx` | Integración | 75/75 | 0 tests (sin módulos) | 25/27 -> ok | 27 casos | ok |
| 6.1-6.4 | `ficha.test.tsx` | Integración | 102/102 | escrito con la sección | ok | 14 casos | ok |
| 7.1-7.2 | `odontograma-modelo.test.ts` | Unit | 116/116 | falla (sin módulos) | ok | 16 casos | ok |
| 7.3-7.8 | `odontograma-ui.test.tsx` | Integración | 132/132 | falla (sin componentes) | ok | 23 casos | ok |
| 8.1-8.5 | `evoluciones.test.tsx` | Integración | 155/155 | falla (sin módulos) | ok | 20 casos | ok |
| 9.1-9.3 | `adjuntos.test.tsx` | Unit/comp. | 175/175 | falla (sin módulos) | ok | 15 casos | ok |

Nota honesta: en 3.1 y 6.x el test y el código se escribieron en la misma pasada (sin RED ejecutado por separado); los tests igualmente cubren ≥ 2 casos por comportamiento.
