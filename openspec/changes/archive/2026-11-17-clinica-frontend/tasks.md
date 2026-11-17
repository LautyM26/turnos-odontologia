# Tasks — clinica-frontend (C-10)

> Governance MEDIO: implementar por grupos y reportar al cierre de cada uno las decisiones no obvias. Las decisiones de producto/UX ya están tomadas en `design.md` §"Decisiones tomadas" (DF-1…DF-19).
> Strict TDD en **cada** tarea: RED (test que falla por la razón correcta) → GREEN (mínimo código) → TRIANGULATE (≥ 2 casos por comportamiento) → REFACTOR con la suite en verde. Comandos desde `frontend/`: `npm test`, `npx tsc --noEmit`, `npx biome check .`.
> Reglas duras: 11 (sin `any`, PascalCase, tsc estricto), 12 (solo `VITE_*`, sin tokens en storage), 13 (cargas independientes con `Promise.all`), 14 (solo datos sintéticos), 15 (sin editar/borrar HC en la UI), 16 (403 de recepción manejado).
> No tocar `backend/app/` ni `openspec/changes/archive/2026-11-17-odontograma-evolucion/` (C-09, archivado; specs en `openspec/specs/`). En `CHANGES.md` editar solo las fichas C-10 y C-07.
> Skills a cargar: `typescript-dev`, `vercel-react-best-practices`, `vitest`, `web-design-guidelines`, `webapp-testing`, `dominio-clinica`.

## 1. Setup de tests y safety net

- [x] 1.1 Safety net: `npm install` en `frontend/` y `npm test` → registrar la línea base de tests de C-01 en verde (`tests/client.test.ts`). Si algo falla, frenar y reportarlo como falla preexistente.
- [x] 1.2 Agregar dev deps `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`; crear `tests/setup.ts` (jest-dom para Vitest, `afterEach(cleanup)`, stubs de `HTMLDialogElement.showModal/close` y `Element.scrollIntoView`) y `test.setupFiles` en `vite.config.ts` (D10). Verificar con un test de humo que renderiza un componente y usa `toBeInTheDocument`, y con `npm test` en verde.
- [x] 1.3 Crear `tests/helpers/api.ts` (mock de `fetch` por tabla método + ruta → respuesta, con registro de llamadas y de tiempos de inicio) y `tests/helpers/fixtures.ts` con pacientes, ficha, odontograma y evoluciones **sintéticos** tipados con `src/features/clinica/tipos.ts` (contrato C-08/C-09 en un solo archivo, `design.md` §Risks). Verificar con un test del helper (ruta no mockeada → error explícito) en verde.

## 2. Cliente HTTP (delta `platform-config`)

- [x] 2.1 RED/GREEN en `tests/client.test.ts`: `X-Clinica-Id` desde `VITE_CLINICA_ID`; si no está, desde el `tenant_id` de la sesión; sin ninguno, **sin** header (nunca vacío). Verificar los 4 escenarios del delta `platform-config` en verde, incluidos los dos existentes de C-01.
- [x] 2.2 RED/GREEN: `ApiError` con `detail` del JSON (string) y resumen de la lista de validación 422 con mapeo por campo (`loc`); `Content-Type` JSON solo con cuerpo string, nunca con `FormData`; `204` → `undefined`; `apiFetchBlob` para descargas. Verificar con tests de cada caso en verde.
- [x] 2.3 RED/GREEN: `401` fuera de `/api/auth/*` → una renovación + un reintento; refresh fallido → callback de sesión expirada, sin bucle; tres requests con `401` simultáneos → **una sola** llamada a `/api/auth/refresh` (D2/D3, spec `web-session` "Renovación silenciosa y reintento único"). Verificar con tests en verde.

## 3. Sesión, router y layout (spec `web-session`)

- [x] 3.1 RED/GREEN: `src/features/auth/session.ts` — `iniciarSesion`, `renovarSesion` single-flight, `requireSession`, `cerrarSesion`, `useSesion` (`useSyncExternalStore`) y validación de `redirectTo` (solo rutas internas; `//evil` y `https://…` → `/pacientes`). Verificar con tests unitarios en verde y con el test existente que audita que no hay accesos a `localStorage`/`sessionStorage`.
- [x] 3.2 RED/GREEN: migrar `src/main.tsx`/`src/App.tsx` a `createBrowserRouter` + `RouterProvider` con el árbol de D1 (públicas, `/login`, `AppLayout` protegido, rutas clínicas `lazy`). Tests con `createMemoryRouter`: `/pacientes` sin sesión → `/login?redirectTo=…`; `/cumplimiento`, `/`, `/reservar/x`, `/comprobantes/1` sin sesión → se muestran; con sesión `/login` → `/pacientes`. Verificar en verde.
- [x] 3.3 RED/GREEN: `LoginPage` — labels visibles, `autocomplete`, envío, `401` → "Email o contraseña incorrectos" (conserva email, limpia contraseña), `429` → mensaje de espera, botón deshabilitado mientras envía, vuelta a `redirectTo`, aviso `?expirada=1`. Verificar con tests de los 4 escenarios de "Ingreso del staff" en verde.
- [x] 3.4 RED/GREEN: `AppLayout` — enlace "Saltar al contenido", navegación "Pacientes" con `aria-current`, email y roles legibles (incluido multi-rol), "Cerrar sesión" que navega a `/login` aunque `/api/auth/logout` falle. Verificar con tests de "Cierre de sesión" e "Identidad y roles visibles" en verde.
- [x] 3.5 Documentar en `frontend/README.md` la sesión (memoria + cookie HttpOnly), el árbol de rutas y cómo C-07 agrega `/agenda` como hijo de `AppLayout`. Verificar que los comandos y rutas citados existen.

## 4. Base de UI compartida

- [x] 4.1 Agregar tokens semánticos en `src/styles.css` (`@theme`: muted, border, danger, success, warning, focus, `--odo-a-realizar`, `--odo-existente`) con contraste AA y `focus-visible` global; respetar `prefers-reduced-motion`. Verificar con `npm run build` limpio y un test que no haya clases dinámicas `bg-${…}` en `src/`.
- [x] 4.2 RED/GREEN: `src/shared/api/resultado.ts` — `cargarSeguro` y `clasificarError` (403 consentimiento por constante igual a `CONSENTIMIENTO_FALTANTE` del backend → `sin-consentimiento`; otro 403 → `sin-acceso`; 404 → `no-encontrado`; resto → `error`). Verificar con tests de cada rama en verde.
- [x] 4.3 RED/GREEN: componentes `EstadoSeccion` (cargando con `aria-busy`, vacío, error con "Reintentar", sin acceso clínico, sin consentimiento), `Aviso` (`role="status"`/`role="alert"`) y `DialogoConfirmacion` (`<dialog>`). Verificar con tests de render y de foco en verde.
- [x] 4.4 RED/GREEN: `src/shared/formato.ts` — fechas `es-AR` en `America/Argentina/Buenos_Aires`, tamaños en KB/MB, nombre de autor (profesional / "Vos" / "Usuario #id", DF-14). Verificar con tests (incluido un instante UTC que cambia de día en AR) en verde.

## 5. Pacientes (spec `patients-web`)

- [x] 5.1 RED/GREEN: `interpretarBusqueda(texto)` puro → `dni` / `telefono` / `q` / "muy corta" (< 3). Verificar con tests de los escenarios de "Búsqueda de pacientes" (incluido `30.123.456` y `pe`) en verde.
- [x] 5.2 RED/GREEN: `PacientesPage` con loader desde `?buscar=` — tabla en desktop y tarjetas en mobile, enlaces al detalle, "Cargar más" con `after_id` sin duplicados, estado vacío con y sin búsqueda, error con "Reintentar". Verificar con tests de los escenarios de "Listado de pacientes paginado" en verde.
- [x] 5.3 RED/GREEN: loader de `PacienteLayout` con `Promise.all(cargarSeguro(paciente), cargarSeguro(historia), cargarSeguro(profesionales))`. Test: las 3 requests empiezan antes de que se resuelva cualquiera; historia `500` no rompe el encabezado; paciente `404` → "Paciente no encontrado" sin pestañas. Verificar en verde (spec `clinical-record-web` "Carga clínica en paralelo", regla dura 13).
- [x] 5.4 RED/GREEN: encabezado del paciente con migas, datos, badge de consentimiento con texto y aviso sin consentimiento. Verificar con tests de "Encabezado del paciente" en verde.
- [x] 5.5 RED/GREEN: formulario "Datos del paciente" — `PATCH` solo con campos tocados, obligatorios (nombre, apellido, DNI), `422`/`409` junto al formulario conservando lo escrito, riesgo de ausencia y alta en solo lectura y nunca enviados. Verificar con tests de "Edición de datos administrativos" en verde.
- [x] 5.6 RED/GREEN: consentimiento con `DialogoConfirmacion` (otorgar/revocar explica el efecto; cancelar no envía) que actualiza encabezado y habilitación de formularios clínicos. Verificar con tests de "Registro del consentimiento de datos" en verde.

## 6. Pestañas, permisos y ficha (spec `clinical-record-web`)

- [x] 6.1 RED/GREEN: pestañas como `NavLink` (`/ficha`, `/odontograma`, `/evoluciones`, `/adjuntos`, índice → ficha) con `aria-current`, operables con teclado, deep link. Verificar con tests de "Pestañas del paciente enlazables" en verde.
- [x] 6.2 RED/GREEN: `permisos.ts` puro (`puedeEscribirClinica` = rol odontólogo; display-only) y estados de acceso en las 4 pestañas: historia `403 "Rol insuficiente"` → mensaje "Sin acceso clínico" sin datos clínicos y con datos administrativos editables; admin sin odontólogo → solo lectura; sin consentimiento → escritura deshabilitada con aviso. Verificar con tests de "Sin acceso clínico para recepción", "Acciones clínicas solo para odontólogo" y "Escritura clínica bloqueada sin consentimiento" en verde.
- [x] 6.3 RED/GREEN: sección Anamnesis — vista de versión vigente (número, autor, fecha; "Sin anamnesis registrada" en versión 0), edición con `PUT` + `version_esperada`, `409` → "La ficha cambió mientras la editabas" + "Recargar versión vigente" sin perder lo escrito, `403` de consentimiento → aviso. Verificar con tests de "Ficha de anamnesis versionada" en verde.
- [x] 6.4 RED/GREEN: "Ver versiones anteriores" (`GET /ficha/versiones`, descendente, solo lectura). Verificar con el test de "Historial de versiones de la ficha" en verde.

## 7. Odontograma (spec `odontogram-web`)

- [x] 7.1 RED/GREEN: `odontograma/fdi.ts` — `piezasDe("permanente")` = 32, `"temporal"` = 20, `"mixta"` = 52, orden de dibujo por arcada (18→11 | 21→28, 48→41 | 31→38, 55→51 | 61→65, 85→81 | 71→75), orientación de caras por cuadrante (V/L arriba-abajo según arcada, M hacia la línea media), catálogo DC-3 con etiquetas. Verificar con tests en verde (bordes 11, 18, 48, 51, 85; inválidos 19, 56, 86).
- [x] 7.2 RED/GREEN: `odontograma/borrador.ts` reducer puro — marcar/quitar cara y pieza, ausente/extraída limpia caras, `cambiarDenticion` devuelve piezas descartadas, `aPayload` omite piezas vacías, `hayCambios`, `hallazgos`. Verificar con tests (≥ 2 casos por función) en verde.
- [x] 7.3 RED/GREEN: `OdontogramaGrafico` — una pieza = `<button>` con SVG de 5 caras y `aria-label` con número y marcas; renderiza **32**, **20** y **52** piezas según dentición; versión 0 → permanente vacía + "Sin odontograma registrado todavía"; colores por token + trama/símbolo no cromático; leyenda y tabla de hallazgos. Verificar con tests de "Piezas según la dentición" y "Odontograma accesible y legible sin color" en verde.
- [x] 7.4 RED/GREEN: `PanelPieza` en `<dialog>` — clic en cara abre con esa cara seleccionada, Enter/Espacio en la pieza abre, Escape cierra y devuelve el foco, estados de pieza y cara con `existente`/`a realizar`, confirmación al marcar ausente con caras. Verificar con tests de "Marcado por pieza y por cara" en verde.
- [x] 7.5 RED/GREEN: selector de dentición con confirmación que nombra las piezas a descartar. Verificar con tests de "Selector de dentición" en verde.
- [x] 7.6 RED/GREEN: guardar — `POST` con `version_esperada` de la versión cargada, botón deshabilitado sin cambios y mientras guarda, `201` → "Versión N · guardada por … el …", `422` → motivo + borrador intacto, `409` → aviso de versión más nueva, borrador visible y "Recargar versión vigente" con confirmación que hace `GET /odontograma/actual`; nunca reintenta solo. Verificar con tests de "Guardado como versión nueva" y "Conflicto de versión del odontograma" en verde.
- [x] 7.7 RED/GREEN: aviso de cambios sin guardar con `useBlocker` (cambiar de pestaña con borrador → confirmar/cancelar) + `beforeunload`. Verificar con el test de "Cambiar de pestaña con borrador" en verde.
- [x] 7.8 RED/GREEN: historial de versiones (`GET /odontograma`) y vista de versión anterior en solo lectura rotulada, sin controles de guardado. Verificar con el test de "Historial de versiones del odontograma" en verde.

## 8. Evoluciones (spec `evolutions-web`)

- [x] 8.1 RED/GREEN: `evoluciones/api.ts` solo con `listar`, `obtener`, `crear`; test que audita el fuente de `src/features/clinica/evoluciones/` y falla si aparece `PUT`/`PATCH`/`DELETE`. Verificar en verde ("Historia sin edición ni borrado").
- [x] 8.2 RED/GREEN: `TimelineEvoluciones` — orden descendente, fecha AR, profesional, pieza, texto; "Cargar anteriores" con `after_id` sin duplicados; vacío "Todavía no hay evoluciones registradas"; **ningún** control Editar/Eliminar. Verificar con tests de "Timeline de evoluciones" y "Sin botones de edición" en verde.
- [x] 8.3 RED/GREEN: `FormularioEvolucion` con `useActionState` — texto obligatorio con contador (≤ 10 000), pieza FDI opcional de lista válida, cuerpo solo `texto`/`pieza_fdi`, doble clic → una sola request, `422` → motivo + texto conservado, `201` → primera en la timeline y formulario vacío. Verificar con tests de "Alta de evolución" en verde.
- [x] 8.4 RED/GREEN: `puedeCorregir` puro + "Corregir" — formulario con texto original y motivo obligatorio (≤ 500); `201` → la timeline tiene **una entrada más**, la nueva muestra "Corrige a…" y motivo, la original conserva su texto y queda "Corregida"; `409` → aviso + recarga de la primera página; sin "Corregir" en evoluciones ajenas o ya corregidas. Verificar con tests de "Corrección como evolución nueva" y "Quién puede corregir" en verde.
- [x] 8.5 RED/GREEN: enlaces de la cadena ("Ver corrección" / "Corrige a") que desplazan y enfocan la evolución destino. Verificar con el test de "Cadena de correcciones visible" en verde.

## 9. Adjuntos (spec `clinical-record-web`)

- [x] 9.1 RED/GREEN: `validarArchivo(file)` puro — JPEG/PNG/PDF por MIME y extensión, ≤ 10 MiB, vacío. Verificar con tests (`.docx` y 10 MiB + 1 byte rechazados; `.jpeg` aceptado) en verde.
- [x] 9.2 RED/GREEN: listado con tipo, tamaño legible, autor, fecha y "Descargar" vía `apiFetchBlob` (sin token en la URL); estado vacío con los tipos aceptados. Verificar con tests de "Listado y descarga de adjuntos" en verde.
- [x] 9.3 RED/GREEN: subida `multipart` con único campo `file`, "Subiendo…", inválido en cliente → "Solo se aceptan fotos JPG/PNG o PDF" sin request, `415`/`413`/`422` del servidor → mensajes claros y lista sin cambios, `201` → primero en la lista + "Adjunto subido". Verificar con tests de "Subida de adjuntos con validación" en verde.

## 10. Demo reproducible y documentación

- [x] 10.1 Crear `backend/scripts/seed_demo_clinica.py` (D11, idempotente): reutiliza `seed_core` + `seed_catalogo`; crea `odontologo@clinica-piloto.test` vinculado al profesional seed y `recepcion@clinica-piloto.test`; 3 pacientes `es_seed = true` obviamente ficticios (uno sin consentimiento); contraseñas desde `SEED_DEMO_PASSWORD` con fallback dev-only. Verificar corriéndolo dos veces contra la base de dev sin duplicar filas y con `ruff check backend/scripts` limpio (regla dura 5, 14).
- [x] 10.2 Actualizar `README.md` raíz: levantar backend + frontend juntos (DB, migraciones, seed de demo, `COOKIE_SECURE=false` en dev, `uvicorn`, `npm run dev`), usuarios de demo por rol y qué ve cada uno. Verificar siguiendo el README desde cero hasta loguearse con los 3 roles.

## 11. Integración y verificación final

- [x] 11.1 Gates: `npm test` (todo verde), `npx tsc --noEmit` sin errores, `npm run build` limpio, `npx biome check .` limpio, y `grep` sin `any` explícito ni accesos a storage en `src/`. Registrar las salidas en `verify.md`.
- [x] 11.2 Auditoría con la skill `web-design-guidelines` sobre `src/features/auth/`, `src/features/clinica/` y `src/shared/ui/` (teclado, foco, contraste, estados vacío/error/carga, mensajes de formulario, 360 px sin scroll horizontal de página); corregir hallazgos con test cuando sean de comportamiento. Verificar con la lista de hallazgos y su resolución en `verify.md`.
- [x] 11.3 E2E real con la skill `webapp-testing` (`scripts/e2e/clinica_demo.py`, `with_server.py` con backend + frontend, C-09 implementado): login odontólogo → `/pacientes` → paciente → odontograma (marcar 16 O caries a realizar, guardar) → evolución → corrección (la original queda "Corregida") → adjunto inválido muestra error → logout; login recepcionista → paciente → odontograma muestra "Sin acceso clínico". Capturas en `openspec/changes/clinica-frontend/evidencias/` y consola del navegador sin errores. Si C-09 no está implementado, marcar el E2E como bloqueado en `verify.md` (no simularlo).
- [x] 11.4 Actualizar la matriz de `dominio-clinica` (RN-CL-01/02/03 lado UI → specs `*-web` y tests de C-10) en `.claude/skills/`, `.github/skills/` y `.opencode/skills/` con copias idénticas. Verificar con `diff` entre las 3 copias vacío.
- [x] 11.5 Escribir `openspec/changes/clinica-frontend/verify.md`: escenario de cada spec → test que lo cubre, gates, auditoría, E2E con capturas, desvíos y tabla TDD. Verificar que todo escenario de `specs/` tenga fila y que `openspec validate clinica-frontend --strict` siga pasando.

## Workflow follow-up

- Revisión del usuario y commit con conventional commits (`feat(clinica-frontend): …`) cuando lo pida (regla dura 1 y 3).
- `/opsx:archive clinica-frontend` y marcar `[x]` en la ficha C-10 de `CHANGES.md`.
- Avisar a Matheo (C-07) que el shell de sesión y el router de datos ya existen para reutilizarlos.
