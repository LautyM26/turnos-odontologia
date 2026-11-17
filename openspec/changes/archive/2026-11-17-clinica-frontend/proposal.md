# Proposal — clinica-frontend (C-10)

## Why

C-08 (pacientes, ficha, adjuntos) y C-09 (odontograma FDI, evoluciones append-only, historia consolidada) dejan la historia clínica completa **solo por API**. El odontólogo no tiene dónde abrir la ficha, marcar el odontograma ni escribir la evolución del Flujo 5 (`knowledge-base/07_flujos_principales.md`), y US-007/008/009 siguen sin lado UI. Además el frontend es todavía el scaffold de C-01: **no hay pantalla de login** ni sesión, así que ninguna pantalla autenticada puede existir.

C-10 es el último paso de la FASE 3 y lo que se muestra en el video de demo: tiene que ser usable, accesible y respetar en pantalla las garantías legales del backend (HC append-only, recepción sin acceso clínico, consentimiento).

## What Changes

- **Shell de sesión web (adelantado de C-07)**: pantalla `/login` contra `POST /api/auth/login`; access token solo en memoria; renovación silenciosa con la cookie HttpOnly (`POST /api/auth/refresh`, una sola en vuelo); rutas protegidas que redirigen a `/login` y vuelven a la ruta pedida; `GET /api/auth/me` para roles; logout; un `401` reintenta una vez tras renovar. Layout autenticado con navegación (Pacientes), usuario y rol visibles. C-07 (`agenda-frontend`, de Matheo) lo **reutiliza** en vez de duplicarlo. No se construye ninguna pantalla de agenda.
- **Cliente HTTP endurecido**: lee el `detail` del error del backend, no fuerza `Content-Type` JSON en subidas `multipart`, y **no envía `X-Clinica-Id` vacío** (hoy un header vacío responde `422`): usa `VITE_CLINICA_ID` si está configurado y, si no, el `tenant_id` de la sesión.
- **`/pacientes`**: listado paginado ("Cargar más") con búsqueda por nombre/apellido (≥ 3 caracteres), DNI o teléfono; estados vacío, cargando y error.
- **`/pacientes/:id`** con encabezado del paciente (nombre, DNI, obra social, estado del consentimiento) y pestañas enlazables por URL:
  - **Ficha**: datos administrativos editables (`PATCH`, todo el staff) y anamnesis/alergias/antecedentes versionados (`PUT` con `version_esperada`, solo odontólogo), con autor, fecha, historial de versiones y aviso de recarga ante `409`.
  - **Odontograma**: SVG FDI clickeable por pieza y por cara, dentición permanente (32), temporal (20) o mixta (52) con selector, catálogo cerrado DC-3 (estados de pieza y de cara, `existente`/`a_realizar`), tabla textual de hallazgos, guardado como versión nueva con `version_esperada` (`409` → aviso "hay una versión más nueva, recargá"), autor/fecha de la versión vigente e historial de versiones de solo lectura.
  - **Evoluciones**: alta con texto y pieza FDI opcional; timeline descendente paginada; **sin botón editar ni borrar**; "Corregir" (solo el autor, solo la evolución vigente) crea una evolución nueva con motivo obligatorio y deja la original visible y marcada como corregida.
  - **Adjuntos**: listado con metadatos y descarga autenticada; subida de JPEG/PNG/PDF con validación previa de tipo y tamaño y mensajes claros para `413`/`415`/`422`.
- **Permisos y estados legales en la UI**: `403` de recepción → mensaje "Sin acceso clínico" (regla dura 16) en las pestañas clínicas, sin romper la página; acciones de escritura ocultas para quien no es odontólogo (solo display: la autoridad es el servidor); paciente sin consentimiento → aviso y formularios clínicos deshabilitados; `404` → "Paciente no encontrado".
- **Demo reproducible**: script de seed sintético (admin, odontólogo vinculado a profesional, recepcionista y pacientes `es_seed = true`, claramente ficticios) y README con cómo levantar backend + frontend juntos.
- **Verificación**: TDD estricto con Vitest + Testing Library por componente/hook; `tsc --noEmit` estricto, `vite build` y `biome check` limpios; E2E real con Playwright (skill `webapp-testing`) contra el backend corriendo, con capturas guardadas en el change.

## Non-goals

- Link "generar presupuesto" desde el odontograma (C-11 `presupuesto-plan`): **excluido**, el backend no existe todavía. El odontograma deja las marcas `a_realizar` listas para que C-11 las consuma.
- Pantallas de agenda, mostrador o turnos (C-07), alta de pacientes (la hace el mostrador en C-07; la demo usa el seed) y vincular adjuntos a evoluciones (`evolucion_id` sigue `422`, DC-9 de C-09).
- Trazabilidad fina "quién marcó cada cara": el backend versiona por snapshot (DC-1), así que la UI muestra autor y fecha **por versión**; el versionado fino por marca es F2.
- Firma electrónica de evoluciones y consentimientos (C-18), recetas (C-19), recall (C-11/C-14), dentición mixta fina/periodontograma (F2).
- Cambios de backend de C-08/C-09: C-10 solo consume sus contratos (el único archivo backend nuevo es el script de seed de demo).

## Capabilities

### New Capabilities

- `web-session`: sesión del staff en el navegador: login, token en memoria, renovación silenciosa por cookie HttpOnly, rutas protegidas, logout y expiración.
- `patients-web`: listado y búsqueda de pacientes, encabezado del paciente y edición de datos administrativos y consentimiento.
- `clinical-record-web`: pestañas clínicas del paciente (ficha de anamnesis versionada, adjuntos) y los estados transversales de acceso clínico (`403` recepción, consentimiento, `404`).
- `odontogram-web`: editor visual del odontograma FDI por pieza y cara, selector de dentición, guardado versionado con manejo de `409` e historial.
- `evolutions-web`: timeline de evoluciones append-only con alta, corrección como entrada nueva y paginación.

### Modified Capabilities

- `platform-config`: el requirement "Tenant header en cliente HTTP" pasa a: header desde `VITE_CLINICA_ID` o, si no está configurado, desde el `tenant_id` de la sesión; nunca un header vacío.

## Impact

- Frontend (`frontend/`):
  - `src/main.tsx` y `src/App.tsx` pasan a router de datos (`createBrowserRouter` + `RouterProvider`); se conservan las rutas públicas `/`, `/reservar/:token`, `/cumplimiento`, `/comprobantes/:id`.
  - Nuevo `src/features/auth/` (sesión, login, guard), `src/features/clinica/` (pacientes, ficha, odontograma, evoluciones, adjuntos), `src/shared/ui/` (layout, estados vacío/cargando/error, avisos).
  - `src/shared/api/client.ts`: errores con `detail`, `FormData`, tenant header, reintento único por `401`.
  - Dependencias de desarrollo nuevas: `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom` (setup de Vitest). Sin librerías de datos ni de UI nuevas.
- Backend: solo un script nuevo de seed de demo (sin tocar `app/` de C-08/C-09).
- Docs: `README.md` (backend + frontend juntos, usuarios de demo), `frontend/README.md`, `CHANGES.md` (fichas C-10 y C-07).
- Depende de que C-09 (`odontograma-evolucion`, ya archivado en `openspec/changes/archive/2026-11-17-odontograma-evolucion/`) termine con el contrato de sus specs; los tests de C-10 mockean ese contrato y el E2E necesita C-09 corriendo.
