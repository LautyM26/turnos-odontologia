# Design — clinica-frontend (C-10)

## Context

Motivación y alcance: ver `proposal.md`. Requisitos: `specs/web-session`, `specs/patients-web`, `specs/clinical-record-web`, `specs/odontogram-web`, `specs/evolutions-web` y el delta de `specs/platform-config`.

Estado observado del frontend (`frontend/`, scaffold C-01):

- React 19.3, Vite 8, TypeScript 6 (`strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`), Tailwind v4 CSS-first (tokens en `src/styles.css`), Biome 2 (preset recommended + dominio react), Vitest 4.1 con `jsdom` y `globals: false`. `react-router` 7.18 (lockfile) usado en **modo declarativo** (`<BrowserRouter>` + `<Routes>`).
- No hay Testing Library instalada, ni login, ni layout, ni `features/*` con código (carpetas vacías).
- `src/shared/api/client.ts` ya guarda el access **en memoria** y manda `credentials: "include"`, pero:
  1. pone siempre `Content-Type: application/json` (rompe `multipart`),
  2. arma `ApiError` con `statusText` y pierde el `detail` del backend,
  3. manda `X-Clinica-Id: ""` si `VITE_CLINICA_ID` no está → el backend responde `422 Tenant inválido` (`require_tenant_checked` en `backend/app/api/deps.py`; sin header usa el `tenant_id` del JWT).
- Convenciones del README del frontend (C-01): sin `useMemo`/`useCallback`/`memo`/`forwardRef` (React Compiler), componentes PascalCase, tokens semánticos, `Promise.all`/`fetchAll` para cargas independientes, datos sintéticos.

Contrato backend que se consume (no se modifica):

| Endpoint | Fuente | Notas para la UI |
|---|---|---|
| `POST /api/auth/login`, `/refresh`, `/logout`, `GET /api/auth/me` | C-03 (`openspec/specs/auth`) | Access 15 min; refresh en cookie HttpOnly `Path=/api/auth`, rotación con blacklist (un refresh ya rotado → `401`); login con rate limit 5/60 s → `429`. `me` = `{sub, email, tenant_id, roles}` |
| `GET/POST /api/pacientes`, `GET/PATCH /api/pacientes/{id}` | C-08 (`patients`) | Staff completo. Búsqueda `dni`/`telefono`/`q` (≥ 3), `Pagina{items,next_cursor}`, `limit` ≤ 200. `PATCH` parcial, `riesgo_ausencia` prohibido (422), DNI duplicado → 409 |
| `GET/PUT /ficha`, `GET /ficha/versiones` | C-08 (`clinical-record`) | `version_esperada`, 409 desfasada, 403 sin consentimiento (`"Falta el consentimiento de datos del paciente"`) |
| `GET/POST /adjuntos`, `GET /adjuntos/{id}/contenido` | C-08 | Solo campo `file`; 415 tipo, 413 tamaño (default 10 MiB), 422 vacío; descarga `attachment` autenticada. Metadatos sin nombre original |
| `GET/POST /odontograma`, `GET /odontograma/actual` | C-09 (`openspec/specs/odontogram`, archivado en `openspec/changes/archive/2026-11-17-odontograma-evolucion/`) | `OdontogramaIn{version_esperada, denticion, piezas{ "16": {estado?, caras{V..O}} }}`, marca `{codigo, registro}`; 409 desfasada; `version = 0` sin odontograma |
| `GET/POST /evoluciones`, `GET /evoluciones/{id}` | C-09 (`clinical-evolutions`) | Cuerpo solo `texto`, `pieza_fdi`, `corrige_a_id`, `motivo_correccion`; salida con `autor_usuario_id`, `profesional_id`, `fecha_hora`, `corregida_por_id`; 409 ya corregida; 403 si no es el autor |
| `GET /historia` | C-09 (`clinical-record` delta) | `{ficha, odontograma, evoluciones[≤50], next_cursor}`; **un** evento de auditoría |
| `GET /api/catalogo/profesionales` | C-04 | Staff completo; `{id, nombre, usuario_id, …}` para mostrar autores |

RBAC (C-08/C-09, `access-control`): lectura clínica admin + odontólogo; escritura clínica solo odontólogo; recepcionista → `403 "Rol insuficiente"` en todo endpoint clínico; vínculo → `403 "Paciente no vinculado al profesional"`; consentimiento → `403 "Falta el consentimiento de datos del paciente"`.

## Goals / Non-Goals

**Goals (de diseño):**

- Un solo mecanismo de sesión y de cliente HTTP que C-07 y C-14 reutilicen sin cambios.
- Lógica clínica (FDI, borrador del odontograma, mapeo de errores, permisos de UI) en **módulos puros** testeables sin DOM; los componentes solo componen.
- Que la UI nunca contradiga al backend: el servidor es la autoridad (roles, consentimiento, versiones); el cliente solo anticipa para dar mejores mensajes.
- Demo grabable: layout coherente, accesible (teclado, foco, contraste AA, sin depender del color) y responsive desde 360 px.

**Non-Goals (de diseño):**

- Sin librería de fetching/caché (TanStack Query, SWR) ni de componentes (MUI, Radix): no hacen falta para 4 pestañas y suman peso y aprendizaje al equipo.
- Sin modo oscuro, i18n ni PWA.
- Sin auto-merge de borradores del odontograma ante 409.

## Decisions

### D1 — Router de datos (`createBrowserRouter` + `RouterProvider`)

Se migra `main.tsx`/`App.tsx` del modo declarativo al **modo datos** de React Router 7:

```
/                         HomePage (pública)
/reservar/:token          ReservarPage (pública)
/cumplimiento             CumplimientoPage (pública)
/comprobantes/:id         ComprobantePage (pública)
/login                    LoginPage        loader: con sesión → redirect /pacientes
(AppLayout)               loader: requireSession() → redirect /login?redirectTo=…
  /pacientes              PacientesPage    loader: búsqueda desde ?buscar=
  /pacientes/:pacienteId  PacienteLayout   loader: Promise.all(paciente, historia, profesionales) por resultado
    index → ficha
    ficha | odontograma | evoluciones | adjuntos
```

- **Por qué**: `useBlocker` (aviso de cambios sin guardar, spec `odontogram-web`) solo funciona con router de datos; los loaders arrancan las cargas en paralelo **antes** de renderizar (regla dura 13) y la redirección de rutas protegidas es un `throw redirect("/login")` estándar.
- Las rutas autenticadas usan `lazy` (import dinámico) para que las páginas públicas (`/reservar`) no carguen el código clínico.
- Alternativas: mantener `<BrowserRouter>` y un componente `<RequireAuth>` (sin `useBlocker`, cargas en efectos con cascada); middleware de rutas de RR 7.9+ (válido, pero un loader en el layout alcanza y es lo más documentado para el equipo).

### D2 — Sesión: store en memoria + refresh single-flight

`src/features/auth/session.ts` (módulo puro + store externo):

- Estado: `identidad: Me | null` (de `/api/auth/me`); el access sigue en `client.ts` (`setAccessToken`).
- `iniciarSesion(email, password)` → `POST /login` → `setAccessToken` → `GET /me`.
- `renovarSesion()` es **single-flight**: una sola promesa en vuelo compartida por todos los llamadores. Imprescindible porque el backend rota y blacklistea el refresh: dos refresh paralelos (p. ej. `StrictMode` montando dos veces, o tres requests con 401) harían que el segundo sea un replay → `401` → logout espurio.
- `requireSession()` (loader): si hay identidad → la devuelve; si no, `renovarSesion()` + `/me`; si falla → `throw redirect("/login?redirectTo=<ruta>")`. `redirectTo` se acepta solo si empieza con `/` y no con `//` (evita open redirect).
- `cerrarSesion()` → `POST /logout` (best effort) → limpia memoria → `/login`.
- Los componentes leen la identidad con `useSyncExternalStore` (`useSesion()`); sin Context ni proveedor extra.
- Nada en `localStorage`/`sessionStorage`; el test de C-01 que audita el fuente sigue vigente.

### D3 — Cliente HTTP endurecido (`src/shared/api/client.ts`)

- `ApiError { status, detail: string, campos?: Record<string,string> }`: lee el JSON de error; `detail` string se usa tal cual; `detail` lista (validación 422 de FastAPI) se resume en el primer `msg` y, si trae `loc`, se mapea por campo para los formularios.
- `Content-Type: application/json` solo si el cuerpo es string; con `FormData` lo pone el navegador (boundary).
- Tenant: `VITE_CLINICA_ID` si está configurado; si no, `identidad.tenant_id`; si no hay ninguno, **no** se manda el header (delta `platform-config`).
- `401` en un endpoint que no sea `/api/auth/*` → `renovarSesion()` → reintento **una** vez; si el refresh falla → `alExpirarSesion()` (callback registrado por el router) navega a `/login?expirada=1`.
- `apiFetchBlob()` para descargar adjuntos con `Authorization` (no se puede con un `<a href>`), luego `URL.createObjectURL` + `<a download>` temporal + `revokeObjectURL`.
- `204`/cuerpo vacío → `undefined`.

### D4 — Resultados por sección y mapeo de errores

- `cargarSeguro<T>(promesa): Promise<Resultado<T>>` con `Resultado = {tipo:"ok",datos} | {tipo:"sin-acceso"} | {tipo:"sin-consentimiento"} | {tipo:"no-encontrado"} | {tipo:"error",mensaje}`. El loader del paciente hace `Promise.all([cargarSeguro(paciente), cargarSeguro(historia), cargarSeguro(profesionales)])`: en paralelo y sin que un 403 de la historia tire abajo la página (spec "Carga clínica en paralelo").
- `clasificarError(ApiError)`: `403` con `detail === "Falta el consentimiento de datos del paciente"` → `sin-consentimiento`; otro `403` → `sin-acceso`; `404` → `no-encontrado`. La constante del texto vive en un solo módulo con test.
- Componente `EstadoSeccion` (cargando / vacío / error con "Reintentar" / sin acceso / sin consentimiento) reutilizado por las 4 pestañas.

### D5 — Datos del paciente compartidos y mutaciones locales

- `PacienteLayout` recibe los resultados del loader y los pasa a las pestañas con `useOutletContext` tipado (estado local inicializado desde el loader).
- Las mutaciones actualizan el estado local con la entidad que devuelve el servidor (versión de ficha, versión de odontograma, evolución nueva) en vez de recargar todo: menos requests y menos eventos de auditoría de lectura.
- "Reintentar"/"Recargar versión vigente" usan `useRevalidator()` o un `GET` puntual (`/odontograma/actual`, `/evoluciones`).
- Formularios con `useActionState` de React 19: el estado `pending` deshabilita el botón (evita doble envío, spec `evolutions-web`) y el error queda junto al formulario.

### D6 — Odontograma: modelo puro + piezas como botones con SVG

Módulos puros en `src/features/clinica/odontograma/`:

- `fdi.ts`: `PERMANENTES` (32), `TEMPORALES` (20), `piezasDe(denticion)`, orden de dibujo por arcada (superior 18→11 | 21→28; inferior 48→41 | 31→38; temporales 55→51 | 61→65 y 85→81 | 71→75), `esPiezaFdi(n)`; catálogos DC-3 con etiquetas en castellano.
- `borrador.ts` (reducer puro): `marcarCara`, `marcarPieza` (ausente/extraída limpia caras), `quitarMarca`, `cambiarDenticion` (devuelve las piezas que se descartarían para pedir confirmación), `aPayload` (omite piezas vacías), `hayCambios(borrador, vigente)`, `hallazgos(piezas)` (filas de la tabla textual).

Dibujo:

- Cada pieza es un `<button type="button">` real (foco, Enter/Espacio y `aria-label` gratis, sin reglas a11y de Biome en contra) que contiene un `<svg viewBox="0 0 40 40" aria-hidden>` con 5 polígonos: trapecios V/L arriba/abajo, M/D a los lados y cuadrado central O. El `onClick` lee `data-cara` del polígono para preseleccionar la cara.
- Orientación clínica: en la arcada superior la cara de arriba es V y la de abajo L (palatino); en la inferior al revés. M mira a la línea media: en los cuadrantes 1, 4, 5, 8 (izquierda de la pantalla) M es el lado derecho de la pieza; en 2, 3, 6, 7 el izquierdo.
- Colores por token (`--odo-a-realizar` rojo, `--odo-existente` azul, convención clínica de DC-3) más una marca no cromática: `a_realizar` con trama rayada (`<pattern>`); estados de pieza con símbolo (ausente/extraída = X, extracción indicada = X roja, corona = círculo, endodoncia = línea vertical, implante = "I"). Leyenda visible + tabla de hallazgos (spec "accesible y legible sin color").
- Panel de edición en `<dialog>` nativo con `showModal()` (trampa de foco y Escape nativos; devuelve el foco al botón de la pieza). Un `<select>` de estado por cara y uno de pieza, cada uno con radio `existente`/`a realizar`.
- Tamaño mínimo de pieza 40×40 px (objetivo táctil); en < 640 px el odontograma se desplaza horizontalmente dentro de su contenedor con indicación visual, sin scroll horizontal de la página.
- Guardado: `POST` con `version_esperada = vigente.version`; `409` → banner con "Recargar versión vigente" (confirmación) y borrador intacto. `useBlocker(hayCambios)` + `beforeunload` para el aviso de salida.
- Historial: `GET /odontograma` al abrir el desplegable "Versiones"; ver una versión anterior cambia a modo solo lectura con rótulo.

### D7 — Evoluciones

- Estado inicial = `historia.evoluciones` + `historia.next_cursor`; "Cargar anteriores" → `GET /evoluciones?after_id=<cursor>&limit=50`.
- Alta → `POST {texto, pieza_fdi?}` → la evolución devuelta se antepone. Corrección → `POST {texto, pieza_fdi?, corrige_a_id, motivo_correccion}` → se antepone y se setea `corregida_por_id` en la original **solo en memoria** (espejo del campo calculado del servidor; la original nunca se re-envía). `409` → aviso + recarga de la primera página.
- `puedeCorregir(evolucion, identidad)` puro: rol odontólogo ∧ `autor_usuario_id === identidad.sub` ∧ `corregida_por_id === null`.
- Autor legible: `profesional_id → profesionales[].nombre`; si falta, "Profesional #id". Fechas con `Intl.DateTimeFormat("es-AR", {timeZone: "America/Argentina/Buenos_Aires"})`.
- Cada entrada es un `<article>` con `id="evolucion-<id>"`; los enlaces "Ver corrección"/"Corrige a" hacen `scrollIntoView` + `focus()` (`tabIndex={-1}`).
- El módulo `api.ts` de evoluciones solo expone `listar`, `obtener` y `crear` (GET/POST): un test audita que no haya `PUT`/`PATCH`/`DELETE` hacia `/evoluciones`.

### D8 — Ficha, datos administrativos y adjuntos

- Pestaña Ficha con dos secciones: **Datos del paciente** (todo el staff; `PATCH` con solo los campos tocados; solo lectura: riesgo de ausencia, alta, consentimiento registrado por/cuándo) y **Anamnesis** (lectura admin+odontólogo, edición solo odontólogo; `PUT` con `version_esperada`; historial bajo demanda). Campos editables según C-08: nombre, apellido, DNI, email, teléfono, obra social, plan, nro. de afiliado, consentimiento (con confirmación) / anamnesis, alergias, antecedentes.
- Adjuntos: validación previa por MIME (`File.type`) y extensión (`.jpg/.jpeg/.png/.pdf`) y tamaño ≤ 10 MiB (espejo del default `ADJUNTO_MAX_BYTES`; el servidor sigue siendo la autoridad y su 413/415/422 se traduce igual). Subida de a un archivo con `<input type="file" accept=…>` + botón; "Subiendo…" mientras dura.
- Autor de adjuntos/versiones (`subido_por`, `autor_usuario_id`): `profesionales[].usuario_id → nombre`; si es el usuario actual, "Vos"; si no, "Usuario #id".

### D9 — Layout y UX (criterios `web-design-guidelines`)

- **AppLayout**: enlace "Saltar al contenido"; barra superior con nombre del producto, navegación ("Pacientes"; "Agenda" la agrega C-07), email + rol(es) y "Cerrar sesión"; `<main id="contenido">` con ancho máximo y gutter de 16 px.
- **/pacientes**: `h1`, formulario de búsqueda con `<label>` visible y ayuda ("Nombre, DNI o teléfono"), resultados en tabla en ≥ 768 px y tarjetas en mobile, "Cargar más", estados vacío/cargando/error.
- **/pacientes/:id**: migas ("Pacientes › Apellido, Nombre"), tarjeta de encabezado con consentimiento como badge con texto (no solo color), navegación de pestañas como enlaces (`NavLink` con `aria-current="page"`), contenido de cada pestaña con `h2`.
- **Mensajes**: éxito en `role="status"` (aria-live polite) junto a la acción; errores en `role="alert"` y asociados al campo con `aria-describedby`; carga con texto "Cargando…" y `aria-busy`.
- **Estilo**: tokens semánticos nuevos en `@theme` (`--color-muted`, `--color-border`, `--color-danger`, `--color-success`, `--color-warning`, `--color-focus`, `--odo-*`) con contraste AA; `focus-visible` siempre visible; tipografía del sistema; sin animaciones salvo transiciones cortas respetando `prefers-reduced-motion`.
- Auditoría final con la skill `web-design-guidelines` sobre los componentes nuevos (tarea dedicada).

### D10 — Tests y verificación

- Dev deps nuevas: `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`. `vite.config.ts` → `test.setupFiles: ["./tests/setup.ts"]`, que importa `@testing-library/jest-dom/vitest`, registra `afterEach(cleanup)` (con `globals: false` Testing Library no limpia sola) y un stub mínimo de `HTMLDialogElement.showModal/close` (jsdom no los implementa).
- `tests/helpers/api.ts`: mock de `fetch` por tabla `método + ruta → respuesta` y fixtures sintéticas tipadas con los mismos tipos que consume la app (contrato C-09 en un solo lugar: `src/features/clinica/tipos.ts`).
- Componentes con rutas se prueban con `createMemoryRouter` + `RouterProvider`.
- Gates: `npm test`, `npx tsc --noEmit`, `npm run build`, `npx biome check .` limpios.
- E2E real con la skill `webapp-testing` (Python Playwright, `with_server.py` levantando backend + frontend) en `scripts/e2e/clinica_demo.py`; capturas en `openspec/changes/clinica-frontend/evidencias/`.

### D11 — Seed de demo sintético

Script nuevo `backend/scripts/seed_demo_clinica.py` (idempotente, no toca `app/`): reutiliza `seed_core` + `seed_catalogo`, crea `odontologo@clinica-piloto.test` (vinculado al profesional seed vía `usuario_id`, requisito de autor en evoluciones) y `recepcion@clinica-piloto.test`, y 3 pacientes `es_seed = true` con nombres obviamente ficticios ("Demo Uno Sintético", DNI 99.000.00x, emails `@ejemplo.test`), uno sin consentimiento. Contraseñas desde `SEED_DEMO_PASSWORD` con fallback dev-only documentado (mismo patrón que `SEED_ADMIN_PASSWORD`). Los usuarios seed se identifican por el dominio `@clinica-piloto.test` (la tabla `usuario` no tiene `es_seed`).

### D12 — Evidencia de Context7 (MCP) y qué se adoptó

Consultas del 2026-11-17, sin secretos, datos de pacientes ni código privado:

| # | Herramienta | Consulta | Resultado | Adoptado |
|---|---|---|---|---|
| 1 | `resolve-library-id` | "React Router" (data mode, loaders, rutas protegidas) | `/remix-run/react-router` (High, 3067 snippets) | Biblioteca para la consulta 2 |
| 2 | `query-docs` `/remix-run/react-router` | createBrowserRouter: redirect a /login desde loader/middleware sin sesión + `useBlocker` para cambios sin guardar | `throw redirect("/login")` en loader (modo data), middleware `authMiddleware` en el layout protegido, `useBlocker(isDirty)` con estados `blocked/proceeding` y `proceed()/reset()` | D1 (router de datos, guard en el loader del layout en vez de comparar pathnames), D6 (`useBlocker` + diálogo de confirmación). Middleware descartado: el loader alcanza |
| 3 | `resolve-library-id` | "Vitest" (setup con jsdom + Testing Library) | `/vitest-dev/vitest` con versión `v4.1.6` (instalado 4.1.11) | Biblioteca para la consulta 4 |
| 4 | `query-docs` `/vitest-dev/vitest/v4.1.6` | `setupFiles` con matchers de jest-dom y cleanup con `globals: false` | Con globals desactivados Testing Library **no** hace cleanup automático; registrar `afterEach(cleanup)` y `expect.extend`/matchers en `setupFiles` | D10 (`tests/setup.ts` con `@testing-library/jest-dom/vitest` + `afterEach(cleanup)`, se mantiene `globals: false`) |

## Decisiones tomadas (aprobación delegada del usuario, 2026-11-16)

El usuario delegó por escrito (2026-11-16) las decisiones de producto/UX de C-09, C-10, C-18 y C-19. Se eligió en cada caso lo más consistente con la KB y las reglas duras.

| # | Pregunta | Opciones | Elegida | Por qué |
|---|---|---|---|---|
| DF-1 | ¿Dónde vive el login/shell de sesión, si C-07 todavía no existe? | (a) C-10 lo construye en `features/auth` y C-07 lo reutiliza; (b) esperar a C-07; (c) duplicar | **(a)** | C-10 no se puede usar ni demostrar sin sesión; C-07 es de otro integrante y está más atrás en su cadena. Se anota en `CHANGES.md` (C-07 lo reutiliza). |
| DF-2 | ¿Router declarativo o de datos? | (a) data router; (b) `<BrowserRouter>` + `<RequireAuth>` | **(a)** | `useBlocker` y loaders paralelos lo requieren; mismo paquete ya instalado (D1). |
| DF-3 | ¿Librería de fetching? | (a) ninguna (loaders + estado local); (b) TanStack Query | **(a)** | Alcance chico, sin dependencias nuevas de runtime, menos curva para el equipo. |
| DF-4 | ¿Recepción ve las pestañas clínicas? | (a) visibles con mensaje "Sin acceso clínico" a partir del 403 del servidor; (b) ocultarlas por rol | **(a)** | Hace visible la regla dura 16 (y la demo), la autoridad sigue siendo el backend y no se filtra nada clínico. |
| DF-5 | ¿Admin sin rol odontólogo? | (a) lectura sin controles de escritura; (b) mostrar controles y dejar que falle | **(a)** | Coincide con `access-control` (escritura solo odontólogo); evita errores evitables. |
| DF-6 | ¿Alta de pacientes en C-10? | (a) no (mostrador/C-07; demo con seed); (b) sí | **(a)** | El roadmap de C-10 pide listado/búsqueda; el alta es de mostrador. Menos alcance, sin pisar a C-07. |
| DF-7 | ¿Se edita el consentimiento de datos desde la Ficha? | (a) sí, con confirmación que explica el efecto; (b) solo lectura hasta C-18 | **(a)** | El endpoint C-08 ya existe y es la única forma de destrabar la carga clínica en la demo; la firma formal es C-18. |
| DF-8 | Editor del odontograma | (a) diálogo por pieza con la cara preseleccionada; (b) paleta "herramienta activa" + clic en caras | **(a)** | Accesible por teclado y simple de testear; la paleta rápida queda como mejora posterior. |
| DF-9 | Trazabilidad "quién/cuándo" de cada marca (CHANGES C-10) | (a) por versión (autor + fecha + historial); (b) por marca, calculada comparando versiones | **(a)** | El backend guarda snapshots (DC-1); el versionado fino por marca es F2 (RN-CL-03). |
| DF-10 | ¿Qué hacer ante 409 del odontograma? | (a) conservar borrador + "Recargar versión vigente" manual; (b) recargar automáticamente; (c) merge | **(a)** | No pierde trabajo sin avisar ni pisa el de otro; el merge clínico automático es riesgoso. |
| DF-11 | ¿La corrección parte del texto original? | (a) sí, editable, con motivo obligatorio; (b) texto vacío | **(a)** | Corregir suele ser cambiar un detalle; el motivo deja la traza (Ley 26.529). |
| DF-12 | Pestañas: ¿ARIA `tablist` o enlaces? | (a) enlaces con `aria-current` y URL propia; (b) `tablist` | **(a)** | Son rutas: deep link, botón atrás y lectores de pantalla funcionan sin JS extra. |
| DF-13 | Header `X-Clinica-Id` | (a) `VITE_CLINICA_ID` si existe, si no el `tenant_id` de la sesión, nunca vacío; (b) solo env | **(a)** | Corrige el `422` por header vacío y respeta la regla dura 12 (no es secreto). Delta `platform-config`. |
| DF-14 | Nombre del autor | (a) profesional por `profesional_id`/`usuario_id` del catálogo, "Vos" si es el usuario actual, si no "Usuario #id"; (b) mostrar ids | **(a)** | Legible sin endpoint nuevo de usuarios; usa `GET /api/catalogo/profesionales` (staff completo). |
| DF-15 | Zona horaria de fechas | (a) `America/Argentina/Buenos_Aires`; (b) la del navegador | **(a)** | SaaS AR; la hora clínica no debe variar por la configuración del equipo. |
| DF-16 | Link "generar presupuesto" | (a) excluido; (b) botón deshabilitado "Próximamente" | **(a)** | El backend de C-11 no existe; un botón muerto confunde en la demo. |
| DF-17 | Herramienta E2E | (a) Python Playwright vía skill `webapp-testing`; (b) `@playwright/test` como dependencia del frontend | **(a)** | Es la skill adoptada en el registry; no agrega dependencias al `package.json`. |
| DF-18 | Seed de demo | (a) script nuevo `backend/scripts/seed_demo_clinica.py` con passwords por env; (b) SQL suelto; (c) crear por API | **(a)** | No existe endpoint de alta de usuarios; reutiliza los seeds existentes sin modificarlos; idempotente (regla dura 14). |
| DF-19 | Panel de edición de pieza | (a) `<dialog>` nativo modal; (b) panel lateral propio | **(a)** | Trampa de foco, Escape y `inert` del resto nativos; menos código. |

## Risks / Trade-offs

- [C-09 se implementa en paralelo y su contrato podría cambiar] → Los tipos del contrato viven en un solo archivo (`src/features/clinica/tipos.ts`) copiados de `backend/app/domain/clinica/schemas.py` y de las specs de C-09; los tests unitarios usan fixtures con esos tipos; el E2E (que necesita C-09 corriendo) va al final del plan y, si C-09 no está archivado, se marca como bloqueado en `verify.md` en lugar de simularse.
- [Detectar "sin consentimiento" por el texto del `detail`] → Es frágil ante un cambio de texto: se centraliza en una constante con test que la compara con `CONSENTIMIENTO_FALTANTE` de `backend/app/api/pacientes.py`. Mejora futura: un código de error estable en el backend (fuera de alcance).
- [Cookie de refresh con `Secure` en desarrollo HTTP] → `localhost` es contexto seguro y el proxy de Vite sirve todo en el mismo origen; aun así el README documenta `COOKIE_SECURE=false` para dev.
- [Rate limit de login (5/60 s) durante E2E y demo] → El script E2E hace como máximo 3 logins y reutiliza contextos de navegador.
- [Replay de refresh por montajes dobles de `StrictMode`] → `renovarSesion()` single-flight con test explícito de tres 401 simultáneos.
- [jsdom no implementa `<dialog>` ni `scrollIntoView`] → Stubs en `tests/setup.ts`; el comportamiento real se verifica en el E2E.
- [Conflictos con C-07 (Matheo) en `main.tsx`, `App.tsx`, layout] → C-10 deja el árbol de rutas con un punto de extensión claro (hijos de `AppLayout`) y la nota en `CHANGES.md`; C-07 solo agrega su ruta `/agenda` y el ítem de navegación.
- [`CHANGES.md` editado por otros agentes en paralelo] → Ediciones puntuales solo en las fichas C-10 y C-07.
- [Bundle] → Rutas clínicas con `lazy`; sin dependencias de runtime nuevas.

## Migration Plan

- Sin migraciones de base de datos. El cambio de router es interno al frontend: las rutas públicas existentes conservan sus URLs (test de humo por ruta).
- Despliegue: `npm run build` genera el estático; el backend no cambia. Variables: `VITE_API_BASE_URL` (opcional, proxy en dev) y `VITE_CLINICA_ID` (opcional desde este change).
- Rollback: revertir el commit del frontend; el backend sigue funcionando igual porque C-10 no lo modifica (el script de seed es independiente).

## Open Questions

- Texto definitivo y logo del producto para la barra superior (se usa "Turnos Odontología" del `index.html`; cambiarlo no afecta specs ni tareas).
